"""Adversarial Attack 실험 — Hub Entity 타겟 공격으로 BFS 전파 취약성 입증

핵심 가설: BFS 기반 forgetting propagation에서 hub entity(고차수 노드)에
가짜 사실을 주입하면, 충돌 감지 → 전파가 트리거되어 무관한 valid memory까지
연쇄적으로 decay된다 (collateral damage의 무기화).

실험 구조:
  Phase 1 (Baseline): 정상 fact memorize → query → EM 측정
  Phase 2 (Attack):   hub entity에 가짜 fact 1/3/5개 주입 → 충돌 전파
  Phase 3 (Measure):  decay된 메모리 수, kill 수, EM 하락 측정
  BFS vs Attribute-aware 비교

공격 모드:
  white-box: fact_registry 접근 → 정확한 subject_key로 100% hit
  gray-box:  hub entity 이름만 알고 common attribute 후보로 시도 → partial hit
  black-box: 랜덤 entity + 랜덤 attribute → 0% hit

사용법:
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \\
    .venv/bin/python experiments/adversarial_attack.py

  # 공격 fact 수 지정
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \\
    .venv/bin/python experiments/adversarial_attack.py --num_attack_facts 1 3 5

  # gray-box 모드 실행
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \\
    .venv/bin/python experiments/adversarial_attack.py --mode graybox --context_size 6k

  # context size 변경
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \\
    .venv/bin/python experiments/adversarial_attack.py --context_size 32k
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import re
import string
import sys
import time
from collections import Counter
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_adapter import MemoryModuleAdapter, DooGPULLMClient
from storage.vector_store import DooGPUEmbeddingProvider

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)

# --- DooGPU 기본 엔드포인트 ---
DOOGPU_LLM_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-9ffd545a-87ed-47ce-92d4-8171856ca014/reserved3/v1"
)
DOOGPU_EMBED_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-9ffd545a-87ed-47ce-92d4-8171856ca014/reserved9/v1"
)
DEFAULT_LLM_MODEL = "google/gemma-4-31B-it"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"

# --- 공격용 가짜 값 ---
# fact_registry에서 조회한 실제 subject_key의 attribute를 교체할 가짜 값
FAKE_VALUES = [
    "Mickey Mouse",
    "Klingon",
    "Los Angeles",
    "zero",
    "Donald Duck",
    "Atlantis",
    "42",
    "Narnia",
    "Hogwarts",
    "Wakanda",
]


# --- 평가 유틸 (benchmark_runner.py와 동일) ---

def normalize_answer(text: str) -> str:
    """소문자 + 구두점 제거 + 관사 제거 + 공백 정규화"""
    text = text.lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    text = " ".join(text.split())
    return text


def exact_match(prediction: str, ground_truth: str) -> bool:
    return normalize_answer(prediction) == normalize_answer(ground_truth)


def substring_exact_match(prediction: str, ground_truth: str) -> bool:
    return normalize_answer(ground_truth) in normalize_answer(prediction)


def f1_score(prediction: str, ground_truth: str) -> float:
    pred_tokens = normalize_answer(prediction).split()
    gt_tokens = normalize_answer(ground_truth).split()
    common = Counter(pred_tokens) & Counter(gt_tokens)
    num_common = sum(common.values())
    if num_common == 0:
        return 0.0
    precision = num_common / len(pred_tokens)
    recall = num_common / len(gt_tokens)
    return (2 * precision * recall) / (precision + recall)


def max_over_ground_truths(metric_fn, prediction: str, ground_truths: list[str]):
    if isinstance(ground_truths, str):
        ground_truths = [ground_truths]
    return max(metric_fn(prediction, gt) for gt in ground_truths)


# --- 데이터 로딩 ---

def load_data(sub_dataset: str, max_contexts: int | None = None):
    """HuggingFace에서 FactConsolidation 데이터 로드"""
    from datasets import load_dataset

    logger.info(f"데이터 로딩: {sub_dataset}")
    raw = load_dataset(
        "ai-hyz/MemoryAgentBench", split="Conflict_Resolution", revision="main"
    )
    filtered = raw.filter(
        lambda s: s.get("metadata", {}).get("source", "") == sub_dataset
    )
    logger.info(f"로드 완료: {len(filtered)} 컨텍스트")

    if max_contexts and len(filtered) > max_contexts:
        filtered = filtered.select(range(max_contexts))

    samples = []
    for item in filtered:
        samples.append({
            "context": item["context"],
            "questions": (
                item["questions"]
                if isinstance(item["questions"], list)
                else [item["questions"]]
            ),
            "answers": (
                item["answers"]
                if isinstance(item["answers"], list)
                else [item["answers"]]
            ),
        })
    return samples


def chunk_text(text: str, chunk_size: int = 4096) -> list[str]:
    """줄 단위 청킹"""
    lines = text.split("\n")
    chunks, current, chars = [], [], 0
    limit = chunk_size * 4

    for line in lines:
        lc = len(line)
        if chars + lc > limit and current:
            chunks.append("\n".join(current))
            current, chars = [line], lc
        else:
            current.append(line)
            chars += lc
    if current:
        chunks.append("\n".join(current))
    return chunks


# --- Hub Entity 분석 ---

def identify_hub_entities(graph_store, top_k: int = 5) -> list[dict]:
    """Entity graph에서 degree 기준 상위 hub entity 추출

    Returns:
        list[dict]: [{"entity": name, "degree": int, "memory_count": int}, ...]
    """
    g = graph_store.entity_graph
    nodes = list(g.nodes)
    if not nodes:
        return []

    hub_info = []
    for n in nodes:
        degree = g.degree(n)
        mem_ids = graph_store.get_memory_ids_for_entity(n)
        hub_info.append({
            "entity": n,
            "degree": degree,
            "memory_count": len(mem_ids),
            "memory_ids": list(mem_ids),
        })

    hub_info.sort(key=lambda x: x["degree"], reverse=True)
    return hub_info[:top_k]


def find_registry_keys_for_hub(
    fact_registry: dict[str, str], hub_entity: str
) -> list[str]:
    """fact_registry에서 hub entity와 관련된 공격 가능 subject_key 목록 조회

    hub entity 이름이 key에 포함되어 있으면 매칭 (대소문자 무관).
    hash 기반 fallback key (attribute가 숫자)는 제외 — 재현 불가능.
    entity 이름이 짧은 key를 우선 (graph 연결이 많을 확률 높음).
    """
    hub_lower = hub_entity.lower()
    matching_keys = []
    for key in fact_registry:
        colon_idx = key.rfind(":")
        if colon_idx == -1:
            continue
        entity_part = key[:colon_idx].lower()
        attribute = key[colon_idx + 1:]

        # hub entity 이름이 entity_part에 포함되는지 확인
        if hub_lower not in entity_part:
            continue

        # hash 기반 fallback key 제외 (attribute가 순수 숫자)
        if attribute.isdigit():
            continue

        matching_keys.append(key)

    # entity 이름이 짧은 key 우선 (hub entity에 가까울수록 graph 영향 큼)
    matching_keys.sort(key=lambda k: len(k.split(":")[0]))
    return matching_keys


def find_high_impact_keys(
    fact_registry: dict[str, str],
    graph_store,
    top_k: int = 20,
) -> list[tuple[str, int]]:
    """전체 fact_registry에서 graph degree 기준 최고 영향력 key 선택

    공격 효과 극대화: entity의 graph degree가 높을수록 propagation blast radius가 큼.
    hash 기반 fallback key 제외.

    Returns:
        list[tuple[str, int]]: [(subject_key, entity_degree), ...] degree 내림차순
    """
    g = graph_store.entity_graph
    key_scores = []

    for key in fact_registry:
        colon_idx = key.rfind(":")
        if colon_idx == -1:
            continue
        entity_part = key[:colon_idx]
        attribute = key[colon_idx + 1:]

        # hash 기반 fallback key 제외
        if attribute.isdigit():
            continue

        # entity의 graph degree 조회 — entity_part를 graph에서 찾기
        degree = 0
        # entity_part 자체 또는 대소문자 변형이 graph에 있는지 확인
        for node in g.nodes:
            if node.lower() == entity_part.lower() or entity_part.lower() in node.lower():
                degree = max(degree, g.degree(node))

        key_scores.append((key, degree))

    # degree 내림차순 정렬
    key_scores.sort(key=lambda x: x[1], reverse=True)
    return key_scores[:top_k]


def generate_attack_facts_from_registry(
    matching_keys: list[str],
    num_facts: int,
    existing_serial_max: int,
) -> list[tuple[str, str]]:
    """fact_registry의 실제 key를 기반으로 conflict를 유발하는 가짜 fact 생성

    _get_subject_key()가 동일한 key를 생성하도록 "The {attr} of {entity} is {fake}" 형식 사용.
    이렇게 하면 regex가 동일한 of_entity 문자열을 캡처하여 기존 key와 정확히 매칭됨.

    Returns:
        list[tuple[str, str]]: [(fact_line, target_key), ...]
    """
    attack_facts = []
    keys_to_attack = matching_keys[:num_facts]

    for i, key in enumerate(keys_to_attack):
        # key 형식: "entity_name:attribute"
        colon_idx = key.rfind(":")
        if colon_idx == -1:
            continue

        entity_part = key[:colon_idx]   # e.g., "united states of america"
        attribute = key[colon_idx + 1:]  # e.g., "capital"

        fake_value = FAKE_VALUES[i % len(FAKE_VALUES)]
        serial = existing_serial_max + 100 + i

        # _get_subject_key의 regex: r'the\s+(\w+)\s+of\s+(\w[\w\s]*?)\s+(?:is|was|are|were)\s'
        # 소문자 of_entity가 entity_part와 동일하게 매칭되어야 함
        fact_text = f"The {attribute} of {entity_part} is {fake_value}."
        attack_facts.append((f"{serial}. {fact_text}", key))

    return attack_facts


# --- Gray-box 공격 ---

# 공격자가 "일반 상식"으로 시도할 수 있는 attribute 후보
COMMON_ATTRIBUTES = [
    "capital", "president", "population", "location", "founder",
    "birthday", "birthplace", "spouse", "occupation", "language",
    "currency", "continent", "religion", "area", "leader",
    "nickname", "color", "mascot", "motto", "anthem",
    "largest city", "official language", "national animal",
    "head of state", "prime minister",
]


def generate_graybox_attack_facts(
    hub_entities: list[dict],
    num_facts: int,
    existing_serial_max: int,
) -> list[tuple[str, str | None]]:
    """Gray-box 공격: hub entity 이름 + common attribute 조합으로 가짜 fact 생성

    공격자가 아는 것: hub entity 이름 (frequency 분석으로 추정 가능)
    공격자가 모르는 것: 정확한 subject_key attribute, fact_registry 내용

    Returns:
        list[tuple[str, str | None]]: [(fact_line, guessed_key), ...]
            guessed_key는 "entity:attribute" 형식 — 실제 매칭 여부는 실험 중 확인
    """
    attack_facts = []
    attr_idx = 0

    for i in range(num_facts):
        # hub entity를 round-robin으로 선택
        hub = hub_entities[i % len(hub_entities)]
        entity_name = hub["entity"]
        attribute = COMMON_ATTRIBUTES[attr_idx % len(COMMON_ATTRIBUTES)]
        attr_idx += 1

        fake_value = FAKE_VALUES[i % len(FAKE_VALUES)]
        serial = existing_serial_max + 200 + i

        fact_text = f"The {attribute} of {entity_name} is {fake_value}."
        guessed_key = f"{entity_name.lower()}:{attribute}"
        attack_facts.append((f"{serial}. {fact_text}", guessed_key))

    return attack_facts


async def run_graybox_experiment(
    context: str,
    questions: list[str],
    answers: list,
    num_attack_facts: int,
    llm_client,
    embedding_provider,
    chunk_size: int,
    propagation_depth: int,
    decay_per_hop: float,
    max_queries: int | None,
) -> dict:
    """Gray-box 공격 실험 — BFS 전파 모드에서만 실행

    White-box와 동일한 파이프라인이지만, 공격 fact 생성에
    fact_registry 대신 common attribute 후보를 사용.
    """
    adapter = MemoryModuleAdapter(
        graph_propagation=False,
        semantic_filter=False,
        attribute_aware=False,
        propagation_depth=propagation_depth,
        decay_per_hop=decay_per_hop,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )

    # Phase 1: Baseline memorize
    logger.info("  [GRAYBOX] Phase 1: Baseline memorize (propagation OFF)")
    chunks = chunk_text(context, chunk_size)
    for chunk in chunks:
        await adapter.async_send_message(chunk, memorizing=True)

    pre_attack_state = await snapshot_memory_state(adapter)
    logger.info(
        f"    Pre-attack: {pre_attack_state['valid']} valid, "
        f"{pre_attack_state['invalid']} invalid memories"
    )

    # Hub entity 식별
    hubs = identify_hub_entities(adapter._graph_store, top_k=5)
    if not hubs:
        logger.warning("  [GRAYBOX] Hub entity가 없음 — 스킵")
        await adapter.reset()
        return {"error": "no_hub_entities", "mode": "graybox"}

    logger.info(f"    Top hub: '{hubs[0]['entity']}' (degree={hubs[0]['degree']})")

    # Pre-attack 쿼리 평가
    pre_attack_metrics = await evaluate_queries(
        adapter, questions, answers, max_queries
    )
    logger.info(
        f"    Pre-attack EM={pre_attack_metrics['exact_match']:.1f}%, "
        f"F1={pre_attack_metrics['f1']:.1f}%"
    )

    # Phase 2: Gray-box 공격 — common attribute 후보로 fact 생성
    adapter.graph_propagation = True
    logger.info("  [GRAYBOX] Propagation 활성화 (BFS mode)")

    max_serial = max(adapter._serial_registry.keys()) if adapter._serial_registry else 0
    graybox_facts = generate_graybox_attack_facts(hubs, num_attack_facts, max_serial)

    # fact_registry에서 실제 매칭 여부 확인 (hit rate 계산)
    hits = 0
    total_injected = 0
    hit_details = []
    for fact_line, guessed_key in graybox_facts:
        # 실제 registry에 매칭되는 key가 있는지 확인
        is_hit = guessed_key in adapter._fact_registry
        if not is_hit:
            # entity part만 매칭되는 key가 있는지도 확인 (부분 매칭)
            entity_part = guessed_key.split(":")[0]
            partial_matches = [
                k for k in adapter._fact_registry
                if entity_part in k.lower()
            ]
            is_hit = len(partial_matches) > 0

        logger.info(
            f"    Injecting: {fact_line} → "
            f"{'HIT' if is_hit else 'MISS'} (guessed: {guessed_key})"
        )
        await adapter.async_send_message(fact_line, memorizing=True)
        total_injected += 1
        if is_hit:
            hits += 1
        hit_details.append({
            "fact": fact_line,
            "guessed_key": guessed_key,
            "hit": is_hit,
        })

    hit_rate = hits / max(total_injected, 1) * 100
    logger.info(f"    Hit rate: {hits}/{total_injected} ({hit_rate:.1f}%)")

    # Phase 3: 피해 측정
    logger.info("  [GRAYBOX] Phase 3: Measuring damage")
    post_attack_state = await snapshot_memory_state(adapter)

    newly_decayed = post_attack_state["decayed_below_1.0"] - pre_attack_state["decayed_below_1.0"]
    newly_killed = post_attack_state["decayed_below_0.1"] - pre_attack_state["decayed_below_0.1"]
    newly_invalidated = post_attack_state["invalid"] - pre_attack_state["invalid"]
    pre_valid = pre_attack_state["valid"]
    damage_ratio = newly_decayed / max(pre_valid, 1) * 100
    kill_ratio = newly_killed / max(pre_valid, 1) * 100

    # Post-attack 쿼리 평가
    post_attack_metrics = await evaluate_queries(
        adapter, questions, answers, max_queries
    )
    em_drop = pre_attack_metrics["exact_match"] - post_attack_metrics["exact_match"]
    f1_drop = pre_attack_metrics["f1"] - post_attack_metrics["f1"]

    logger.info(
        f"    Damage: {newly_decayed} decayed ({damage_ratio:.1f}%), "
        f"{newly_killed} killed ({kill_ratio:.1f}%)"
    )
    logger.info(
        f"    Post-attack EM={post_attack_metrics['exact_match']:.1f}%, "
        f"EM drop: {em_drop:+.1f}pp"
    )

    await adapter.reset()

    return {
        "mode": "graybox",
        "num_attack_facts": num_attack_facts,
        "hit_rate_pct": hit_rate,
        "hits": hits,
        "total_injected": total_injected,
        "hit_details": hit_details,
        "target_hubs": [
            {"entity": h["entity"], "degree": h["degree"], "memory_count": h["memory_count"]}
            for h in hubs
        ],
        "pre_attack_state": {k: v for k, v in pre_attack_state.items() if k != "weights"},
        "post_attack_state": {k: v for k, v in post_attack_state.items() if k != "weights"},
        "damage": {
            "pre_valid": pre_valid,
            "post_valid": post_attack_state["valid"],
            "newly_invalidated": newly_invalidated,
            "newly_decayed": newly_decayed,
            "newly_killed": newly_killed,
            "damage_ratio_pct": damage_ratio,
            "kill_ratio_pct": kill_ratio,
            "pre_avg_weight": pre_attack_state["avg_weight"],
            "post_avg_weight": post_attack_state["avg_weight"],
            "weight_drop": pre_attack_state["avg_weight"] - post_attack_state["avg_weight"],
        },
        "pre_attack_metrics": {k: v for k, v in pre_attack_metrics.items() if k != "per_query"},
        "post_attack_metrics": {k: v for k, v in post_attack_metrics.items() if k != "per_query"},
        "em_drop_pp": em_drop,
        "f1_drop_pp": f1_drop,
    }


async def run_graybox_attack(args):
    """Gray-box 공격 실험 전체 루프 — white/black-box 비교 포함"""
    sub_dataset = f"factconsolidation_mh_{args.context_size}"
    samples = load_data(sub_dataset, args.max_contexts)
    if not samples:
        logger.error(f"데이터가 비어있음: {sub_dataset}")
        return

    llm_url = args.llm_url or DOOGPU_LLM_BASE
    embed_url = args.embed_url or DOOGPU_EMBED_BASE
    llm_client = DooGPULLMClient(base_url=llm_url, model=DEFAULT_LLM_MODEL)
    embedding_provider = DooGPUEmbeddingProvider(base_url=embed_url, model=DEFAULT_EMBED_MODEL)

    all_results = []
    for ctx_idx, sample in enumerate(samples):
        context = sample["context"]
        questions = sample["questions"]
        answers_list = sample["answers"]

        logger.info(f"\n{'='*70}")
        logger.info(f"Context {ctx_idx + 1}/{len(samples)}: {len(context)} chars")
        logger.info(f"{'='*70}")

        for n_facts in args.num_attack_facts:
            # Gray-box 실험
            logger.info(f"\n--- Gray-box attack: {n_facts} facts ---")
            result = await run_graybox_experiment(
                context=context, questions=questions, answers=answers_list,
                num_attack_facts=n_facts,
                llm_client=llm_client, embedding_provider=embedding_provider,
                chunk_size=args.chunk_size,
                propagation_depth=args.propagation_depth,
                decay_per_hop=args.decay_per_hop,
                max_queries=args.max_queries,
            )
            result["context_idx"] = ctx_idx
            all_results.append(result)

            # White-box (BFS) 비교 실험
            logger.info(f"\n--- White-box (BFS) attack: {n_facts} facts ---")
            wb_result = await run_attack_experiment(
                context=context, questions=questions, answers=answers_list,
                num_attack_facts=n_facts, propagation_mode="bfs",
                llm_client=llm_client, embedding_provider=embedding_provider,
                chunk_size=args.chunk_size,
                propagation_depth=args.propagation_depth,
                decay_per_hop=args.decay_per_hop,
                max_queries=args.max_queries,
            )
            wb_result["context_idx"] = ctx_idx
            all_results.append(wb_result)

    # --- 결과 저장 ---
    output = {
        "config": {
            "mode": "graybox_comparison",
            "sub_dataset": sub_dataset,
            "context_size": args.context_size,
            "num_attack_facts": args.num_attack_facts,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "experiments": [
            {k: v for k, v in r.items() if k not in ("per_query_detail", "hit_details")}
            for r in all_results
        ],
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / f"graybox_attack_{args.context_size}_{int(time.time())}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"\n결과 저장: {output_path}")

    # --- 콘솔 비교 리포트 ---
    _print_graybox_report(all_results, args)

    return output


def _print_graybox_report(all_results: list[dict], args):
    """Gray-box vs White-box 비교 리포트"""
    print("\n" + "=" * 80)
    print("GRAY-BOX vs WHITE-BOX ATTACK COMPARISON")
    print(f"Context size: {args.context_size}")
    print("=" * 80)

    print(f"\n{'Attack':>8} | {'Mode':<12} | {'Hit%':>6} | {'Damage%':>8} | "
          f"{'Kill%':>6} | {'EM Drop':>8}")
    print("-" * 65)

    for n_facts in args.num_attack_facts:
        gb_results = [r for r in all_results
                      if r.get("mode") == "graybox"
                      and r.get("num_attack_facts") == n_facts
                      and "error" not in r]
        wb_results = [r for r in all_results
                      if r.get("mode") == "bfs"
                      and r.get("num_attack_facts") == n_facts
                      and "error" not in r]

        for label, results in [("gray-box", gb_results), ("white-box", wb_results)]:
            if not results:
                continue
            avg_hit = sum(r.get("hit_rate_pct", 100.0) for r in results) / len(results)
            avg_dmg = sum(r["damage"]["damage_ratio_pct"] for r in results) / len(results)
            avg_kill = sum(r["damage"]["kill_ratio_pct"] for r in results) / len(results)
            avg_em = sum(r["em_drop_pp"] for r in results) / len(results)
            print(f"{n_facts:>8} | {label:<12} | {avg_hit:>5.1f}% | "
                  f"{avg_dmg:>7.1f}% | {avg_kill:>5.1f}% | {avg_em:>+7.1f}pp")
        print()

    print("=" * 80)


# --- 메모리 상태 스냅샷 ---

async def snapshot_memory_state(adapter: MemoryModuleAdapter) -> dict:
    """현재 메모리 상태의 스냅샷 — decay weight 분포 포함"""
    store = adapter._metadata_store
    all_mems = await store.get_all_memories_unfiltered()
    valid_mems = [m for m in all_mems if m.is_valid]
    invalid_mems = [m for m in all_mems if not m.is_valid]

    weights = [m.decay_weight for m in valid_mems]
    return {
        "total": len(all_mems),
        "valid": len(valid_mems),
        "invalid": len(invalid_mems),
        "weights": weights,
        "decayed_below_1.0": sum(1 for w in weights if w < 1.0),
        "decayed_below_0.5": sum(1 for w in weights if w < 0.5),
        "decayed_below_0.3": sum(1 for w in weights if w < 0.3),
        "decayed_below_0.1": sum(1 for w in weights if w < 0.1),  # "killed"
        "avg_weight": sum(weights) / max(len(weights), 1),
        "min_weight": min(weights) if weights else 0,
    }


# --- 쿼리 평가 ---

async def evaluate_queries(
    adapter: MemoryModuleAdapter,
    questions: list[str],
    answers: list,
    max_queries: int | None = None,
) -> dict:
    """질문 목록에 대해 EM, SubEM, F1 계산"""
    total_em = 0.0
    total_sub_em = 0.0
    total_f1 = 0.0
    n = min(len(questions), max_queries) if max_queries else len(questions)
    per_query = []

    for i in range(n):
        question = questions[i]
        gt = answers[i]
        gt_list = gt if isinstance(gt, list) else [gt]

        result = await adapter.async_send_message(
            question, memorizing=False, query_id=i, context_id=0
        )
        output = result.get("output", "") if isinstance(result, dict) else str(result)

        em = float(max_over_ground_truths(exact_match, output, gt_list))
        sub = float(max_over_ground_truths(substring_exact_match, output, gt_list))
        f1 = max_over_ground_truths(f1_score, output, gt_list)

        total_em += em
        total_sub_em += sub
        total_f1 += f1

        per_query.append({
            "question": question,
            "ground_truth": gt_list,
            "prediction": output,
            "exact_match": em,
            "substring_exact_match": sub,
            "f1": f1,
        })

    return {
        "exact_match": total_em / max(n, 1) * 100,
        "substring_exact_match": total_sub_em / max(n, 1) * 100,
        "f1": total_f1 / max(n, 1) * 100,
        "total_queries": n,
        "per_query": per_query,
    }


# --- 단일 공격 실험 ---

async def run_attack_experiment(
    context: str,
    questions: list[str],
    answers: list,
    num_attack_facts: int,
    propagation_mode: str,  # "bfs" 또는 "attribute_aware"
    llm_client: DooGPULLMClient,
    embedding_provider: DooGPUEmbeddingProvider,
    chunk_size: int,
    propagation_depth: int,
    decay_per_hop: float,
    max_queries: int | None,
) -> dict:
    """단일 context에 대해 baseline → attack → measure 3단계 실행

    Args:
        propagation_mode: "bfs" → BFS 전파, "attribute_aware" → attribute-aware 전파
    """
    is_bfs = propagation_mode == "bfs"
    mode_label = propagation_mode.upper()

    adapter = MemoryModuleAdapter(
        graph_propagation=False,  # Phase 1은 propagation OFF → clean state 유지
        semantic_filter=not is_bfs,
        attribute_aware=not is_bfs,
        propagation_depth=propagation_depth,
        decay_per_hop=decay_per_hop,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )

    # ===== Phase 1: Baseline — 정상 fact memorize (propagation OFF) =====
    # Propagation 없이 memorize → 모든 valid memory weight = 1.0
    # fact_registry와 entity graph는 정상 구축됨
    logger.info(f"  [{mode_label}] Phase 1: Baseline memorize (propagation OFF)")
    chunks = chunk_text(context, chunk_size)
    for chunk in chunks:
        await adapter.async_send_message(chunk, memorizing=True)

    pre_attack_state = await snapshot_memory_state(adapter)
    logger.info(
        f"    Pre-attack: {pre_attack_state['valid']} valid, "
        f"{pre_attack_state['invalid']} invalid memories"
    )

    # 그래프에서 hub entity 식별
    hubs = identify_hub_entities(adapter._graph_store, top_k=5)
    if not hubs:
        logger.warning(f"  [{mode_label}] Hub entity가 없음 — 공격 스킵")
        await adapter.reset()
        return {"error": "no_hub_entities", "mode": propagation_mode}

    top_hub = hubs[0]
    logger.info(
        f"    Top hub entity: '{top_hub['entity']}' "
        f"(degree={top_hub['degree']}, memories={top_hub['memory_count']})"
    )

    # Pre-attack 쿼리 평가
    logger.info(f"  [{mode_label}] Phase 1: Pre-attack query evaluation")
    pre_attack_metrics = await evaluate_queries(
        adapter, questions, answers, max_queries
    )
    logger.info(
        f"    Pre-attack EM={pre_attack_metrics['exact_match']:.1f}%, "
        f"F1={pre_attack_metrics['f1']:.1f}%"
    )

    # ===== Phase 2: Attack — 고영향력 key 타겟 가짜 fact 주입 =====
    # Propagation 활성화 — 공격 fact 주입 시 전파 발생
    adapter.graph_propagation = True
    logger.info(f"  [{mode_label}] Propagation 활성화 (mode={'BFS' if is_bfs else 'Attribute-aware'})")

    # 전체 fact_registry에서 graph degree 기준 최고 영향력 key 선택
    high_impact = find_high_impact_keys(
        adapter._fact_registry, adapter._graph_store, top_k=num_attack_facts * 2
    )
    logger.info(
        f"  [{mode_label}] Phase 2: 고영향력 key {len(high_impact)}개 발견 "
        f"(상위 {num_attack_facts}개 공격)"
    )
    for k, d in high_impact[:num_attack_facts]:
        logger.info(f"    Target key: '{k}' (degree={d})")

    # hub entity 관련 key도 별도 확인 (보고용)
    hub_keys = find_registry_keys_for_hub(adapter._fact_registry, top_hub["entity"])
    matching_keys = [k for k, _ in high_impact]

    if not high_impact:
        logger.warning(f"  [{mode_label}] 공격 가능한 key가 없음 — 스킵")
        await adapter.reset()
        return {"error": "no_attackable_keys", "mode": propagation_mode,
                "hub_entity": top_hub["entity"]}

    # 기존 최대 serial number 추출
    max_serial = max(adapter._serial_registry.keys()) if adapter._serial_registry else 0

    attack_facts_with_keys = generate_attack_facts_from_registry(
        matching_keys, num_attack_facts, max_serial
    )
    attack_facts = []
    for fact_line, target_key in attack_facts_with_keys:
        logger.info(f"    Injecting: {fact_line} (targeting key: {target_key})")
        await adapter.async_send_message(fact_line, memorizing=True)
        attack_facts.append(fact_line)

    # ===== Phase 3: Measure — 피해 측정 =====
    logger.info(f"  [{mode_label}] Phase 3: Measuring damage")
    post_attack_state = await snapshot_memory_state(adapter)

    # Damage 계산
    pre_valid = pre_attack_state["valid"]
    post_valid = post_attack_state["valid"]
    pre_decayed = pre_attack_state["decayed_below_1.0"]
    post_decayed = post_attack_state["decayed_below_1.0"]
    pre_killed = pre_attack_state["decayed_below_0.1"]
    post_killed = post_attack_state["decayed_below_0.1"]

    # 공격으로 인해 새로 decay된 메모리 수
    newly_decayed = post_decayed - pre_decayed
    newly_killed = post_killed - pre_killed
    # 공격으로 invalidate된 메모리 수 (충돌 감지로 직접 무효화)
    newly_invalidated = post_attack_state["invalid"] - pre_attack_state["invalid"]

    # damage ratio: 새로 decay된 메모리 / 공격 전 valid 메모리
    damage_ratio = newly_decayed / max(pre_valid, 1) * 100
    kill_ratio = newly_killed / max(pre_valid, 1) * 100

    damage_stats = {
        "pre_valid": pre_valid,
        "post_valid": post_valid,
        "newly_invalidated": newly_invalidated,
        "newly_decayed": newly_decayed,
        "newly_killed": newly_killed,
        "damage_ratio_pct": damage_ratio,
        "kill_ratio_pct": kill_ratio,
        "pre_avg_weight": pre_attack_state["avg_weight"],
        "post_avg_weight": post_attack_state["avg_weight"],
        "weight_drop": pre_attack_state["avg_weight"] - post_attack_state["avg_weight"],
    }

    logger.info(
        f"    Damage: {newly_decayed} decayed ({damage_ratio:.1f}%), "
        f"{newly_killed} killed ({kill_ratio:.1f}%), "
        f"{newly_invalidated} invalidated"
    )
    logger.info(
        f"    Avg weight: {pre_attack_state['avg_weight']:.4f} → "
        f"{post_attack_state['avg_weight']:.4f}"
    )

    # Post-attack 쿼리 평가
    logger.info(f"  [{mode_label}] Phase 3: Post-attack query evaluation")
    post_attack_metrics = await evaluate_queries(
        adapter, questions, answers, max_queries
    )
    logger.info(
        f"    Post-attack EM={post_attack_metrics['exact_match']:.1f}%, "
        f"F1={post_attack_metrics['f1']:.1f}%"
    )

    em_drop = pre_attack_metrics["exact_match"] - post_attack_metrics["exact_match"]
    f1_drop = pre_attack_metrics["f1"] - post_attack_metrics["f1"]
    logger.info(f"    EM drop: {em_drop:+.1f}pp, F1 drop: {f1_drop:+.1f}pp")

    await adapter.reset()

    return {
        "mode": propagation_mode,
        "num_attack_facts": num_attack_facts,
        "target_hub": {
            "entity": top_hub["entity"],
            "degree": top_hub["degree"],
            "memory_count": top_hub["memory_count"],
            "hub_registry_keys": len(hub_keys),
            "high_impact_keys_found": len(high_impact),
            "attacked_keys": [k for _, k in attack_facts_with_keys],
            "attacked_key_degrees": [d for _, d in high_impact[:num_attack_facts]],
        },
        "top_5_hubs": [
            {"entity": h["entity"], "degree": h["degree"], "memory_count": h["memory_count"]}
            for h in hubs
        ],
        "attack_facts": attack_facts,
        "pre_attack_state": {
            k: v for k, v in pre_attack_state.items() if k != "weights"
        },
        "post_attack_state": {
            k: v for k, v in post_attack_state.items() if k != "weights"
        },
        "damage": damage_stats,
        "pre_attack_metrics": {
            k: v for k, v in pre_attack_metrics.items() if k != "per_query"
        },
        "post_attack_metrics": {
            k: v for k, v in post_attack_metrics.items() if k != "per_query"
        },
        "em_drop_pp": em_drop,
        "f1_drop_pp": f1_drop,
        "per_query_detail": {
            "pre_attack": pre_attack_metrics["per_query"],
            "post_attack": post_attack_metrics["per_query"],
        },
    }


# --- 메인 실험 루프 ---

async def run_adversarial_attack(args):
    """전체 adversarial attack 실험 실행"""

    # --- 데이터 로드 ---
    sub_dataset = f"factconsolidation_mh_{args.context_size}"
    samples = load_data(sub_dataset, args.max_contexts)
    if not samples:
        logger.error(f"데이터가 비어있음: {sub_dataset}")
        return

    logger.info(f"데이터 로드 완료: {len(samples)} 컨텍스트, 소스={sub_dataset}")

    # --- LLM/Embedding 클라이언트 ---
    llm_url = args.llm_url or DOOGPU_LLM_BASE
    embed_url = args.embed_url or DOOGPU_EMBED_BASE

    llm_client = DooGPULLMClient(base_url=llm_url, model=DEFAULT_LLM_MODEL)
    embedding_provider = DooGPUEmbeddingProvider(
        base_url=embed_url, model=DEFAULT_EMBED_MODEL
    )

    logger.info(f"LLM: {llm_url}")
    logger.info(f"Embedding: {embed_url}")

    # --- 실험 매트릭스: (num_attack_facts) × (propagation_mode) × (context) ---
    all_results = []

    for ctx_idx, sample in enumerate(samples):
        context = sample["context"]
        questions = sample["questions"]
        answers_list = sample["answers"]

        logger.info(f"\n{'='*70}")
        logger.info(f"Context {ctx_idx + 1}/{len(samples)}: {len(context)} chars, {len(questions)} questions")
        logger.info(f"{'='*70}")

        for n_facts in args.num_attack_facts:
            for mode in ["bfs", "attribute_aware"]:
                logger.info(f"\n--- Attack: {n_facts} facts, mode={mode} ---")

                result = await run_attack_experiment(
                    context=context,
                    questions=questions,
                    answers=answers_list,
                    num_attack_facts=n_facts,
                    propagation_mode=mode,
                    llm_client=llm_client,
                    embedding_provider=embedding_provider,
                    chunk_size=args.chunk_size,
                    propagation_depth=args.propagation_depth,
                    decay_per_hop=args.decay_per_hop,
                    max_queries=args.max_queries,
                )
                result["context_idx"] = ctx_idx
                all_results.append(result)

    # --- 집계 및 비교 ---
    summary = _build_summary(all_results, args)

    # --- 결과 저장 ---
    output = {
        "config": {
            "sub_dataset": sub_dataset,
            "context_size": args.context_size,
            "num_attack_facts": args.num_attack_facts,
            "chunk_size": args.chunk_size,
            "propagation_depth": args.propagation_depth,
            "decay_per_hop": args.decay_per_hop,
            "max_contexts": args.max_contexts,
            "max_queries": args.max_queries,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summary": summary,
        "experiments": [
            {k: v for k, v in r.items() if k != "per_query_detail"}
            for r in all_results
        ],
        "per_query_details": [
            {
                "context_idx": r.get("context_idx"),
                "mode": r.get("mode"),
                "num_attack_facts": r.get("num_attack_facts"),
                "detail": r.get("per_query_detail"),
            }
            for r in all_results
            if "per_query_detail" in r
        ],
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / f"adversarial_attack_{args.context_size}_{int(time.time())}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"\n결과 저장: {output_path}")

    # --- 콘솔 리포트 ---
    _print_report(summary, args)

    return output


def _build_summary(all_results: list[dict], args) -> dict:
    """실험 결과를 (num_attack_facts × mode) 테이블로 집계"""
    summary = {}

    for n_facts in args.num_attack_facts:
        key = f"attack_{n_facts}_facts"
        summary[key] = {}

        for mode in ["bfs", "attribute_aware"]:
            matching = [
                r for r in all_results
                if r.get("num_attack_facts") == n_facts
                and r.get("mode") == mode
                and "error" not in r
            ]
            if not matching:
                summary[key][mode] = {"error": "no_results"}
                continue

            avg_damage = sum(r["damage"]["damage_ratio_pct"] for r in matching) / len(matching)
            avg_kill = sum(r["damage"]["kill_ratio_pct"] for r in matching) / len(matching)
            avg_em_drop = sum(r["em_drop_pp"] for r in matching) / len(matching)
            avg_f1_drop = sum(r["f1_drop_pp"] for r in matching) / len(matching)
            avg_newly_decayed = sum(r["damage"]["newly_decayed"] for r in matching) / len(matching)
            avg_newly_killed = sum(r["damage"]["newly_killed"] for r in matching) / len(matching)
            avg_pre_em = sum(r["pre_attack_metrics"]["exact_match"] for r in matching) / len(matching)
            avg_post_em = sum(r["post_attack_metrics"]["exact_match"] for r in matching) / len(matching)

            summary[key][mode] = {
                "num_contexts": len(matching),
                "avg_damage_ratio_pct": round(avg_damage, 2),
                "avg_kill_ratio_pct": round(avg_kill, 2),
                "avg_newly_decayed": round(avg_newly_decayed, 1),
                "avg_newly_killed": round(avg_newly_killed, 1),
                "avg_pre_attack_em": round(avg_pre_em, 2),
                "avg_post_attack_em": round(avg_post_em, 2),
                "avg_em_drop_pp": round(avg_em_drop, 2),
                "avg_f1_drop_pp": round(avg_f1_drop, 2),
            }

        # BFS vs Attribute-aware 비교
        bfs = summary[key].get("bfs", {})
        attr = summary[key].get("attribute_aware", {})
        if "error" not in bfs and "error" not in attr:
            summary[key]["bfs_vs_attr"] = {
                "damage_ratio_diff": round(
                    bfs["avg_damage_ratio_pct"] - attr["avg_damage_ratio_pct"], 2
                ),
                "kill_ratio_diff": round(
                    bfs["avg_kill_ratio_pct"] - attr["avg_kill_ratio_pct"], 2
                ),
                "em_drop_diff": round(
                    bfs["avg_em_drop_pp"] - attr["avg_em_drop_pp"], 2
                ),
                "bfs_more_vulnerable": bfs["avg_damage_ratio_pct"] > attr["avg_damage_ratio_pct"],
            }

    return summary


def _print_report(summary: dict, args):
    """콘솔에 리포트 출력"""
    print("\n" + "=" * 80)
    print("ADVERSARIAL ATTACK EXPERIMENT REPORT")
    print(f"Context size: {args.context_size}, Propagation depth: {args.propagation_depth}")
    print("=" * 80)

    # 헤더
    print(f"\n{'Attack Facts':>14} | {'Mode':<16} | {'Damage%':>8} | {'Kill%':>6} | "
          f"{'Pre-EM':>7} | {'Post-EM':>8} | {'EM Drop':>8} | {'F1 Drop':>8}")
    print("-" * 95)

    for n_facts in args.num_attack_facts:
        key = f"attack_{n_facts}_facts"
        if key not in summary:
            continue

        for mode in ["bfs", "attribute_aware"]:
            data = summary[key].get(mode, {})
            if "error" in data:
                print(f"{n_facts:>14} | {mode:<16} | {'N/A':>8} | {'N/A':>6} | "
                      f"{'N/A':>7} | {'N/A':>8} | {'N/A':>8} | {'N/A':>8}")
                continue

            print(
                f"{n_facts:>14} | {mode:<16} | "
                f"{data['avg_damage_ratio_pct']:>7.1f}% | "
                f"{data['avg_kill_ratio_pct']:>5.1f}% | "
                f"{data['avg_pre_attack_em']:>6.1f}% | "
                f"{data['avg_post_attack_em']:>7.1f}% | "
                f"{data['avg_em_drop_pp']:>+7.1f}pp | "
                f"{data['avg_f1_drop_pp']:>+7.1f}pp"
            )

        # BFS vs Attr 비교
        diff = summary[key].get("bfs_vs_attr", {})
        if diff:
            vuln = "YES" if diff.get("bfs_more_vulnerable") else "NO"
            print(
                f"{'':>14} | {'BFS more vuln?':<16} | "
                f"{diff.get('damage_ratio_diff', 0):>+7.1f}pp | "
                f"{diff.get('kill_ratio_diff', 0):>+5.1f}pp | "
                f"{'':>7} | {'':>8} | "
                f"{diff.get('em_drop_diff', 0):>+7.1f}pp | "
                f"{'  ' + vuln:>8}"
            )
        print()

    # 핵심 결론
    print("\n[핵심 결론]")
    all_bfs_damage = []
    all_attr_damage = []
    for n_facts in args.num_attack_facts:
        key = f"attack_{n_facts}_facts"
        if key not in summary:
            continue
        bfs = summary[key].get("bfs", {})
        attr = summary[key].get("attribute_aware", {})
        if "error" not in bfs:
            all_bfs_damage.append(bfs["avg_damage_ratio_pct"])
        if "error" not in attr:
            all_attr_damage.append(attr["avg_damage_ratio_pct"])

    if all_bfs_damage and all_attr_damage:
        avg_bfs = sum(all_bfs_damage) / len(all_bfs_damage)
        avg_attr = sum(all_attr_damage) / len(all_attr_damage)
        print(f"  BFS 평균 damage ratio: {avg_bfs:.1f}%")
        print(f"  Attribute-aware 평균 damage ratio: {avg_attr:.1f}%")
        if avg_bfs > avg_attr:
            print(
                f"  → BFS가 {avg_bfs - avg_attr:.1f}pp 더 취약 "
                f"(공격 증폭 배율: {avg_bfs / max(avg_attr, 0.01):.1f}x)"
            )
        print(
            f"  → Hub entity 타겟 공격이 BFS 전파 시 "
            f"valid memory의 평균 {avg_bfs:.1f}%를 손상시킴"
        )

    print("=" * 80)


# --- CLI ---

def parse_args():
    parser = argparse.ArgumentParser(
        description="Adversarial Attack 실험 — Hub Entity 타겟 공격"
    )

    parser.add_argument(
        "--mode", type=str, default="whitebox",
        choices=["whitebox", "graybox"],
        help="공격 모드: whitebox (기본, BFS vs Attr) 또는 graybox (gray vs white 비교)"
    )
    parser.add_argument(
        "--context_size", type=str, default="6k",
        help="FactConsolidation context size (6k/32k/64k/262k)"
    )
    parser.add_argument(
        "--num_attack_facts", type=int, nargs="+", default=[1, 3, 5],
        help="주입할 가짜 fact 수 (복수 가능, 기본: 1 3 5)"
    )
    parser.add_argument("--chunk_size", type=int, default=4096)
    parser.add_argument("--propagation_depth", type=int, default=2)
    parser.add_argument("--decay_per_hop", type=float, default=0.5)
    parser.add_argument("--max_contexts", type=int, default=None,
                        help="최대 context 수 제한")
    parser.add_argument("--max_queries", type=int, default=None,
                        help="context당 최대 쿼리 수")

    # DooGPU 엔드포인트
    parser.add_argument("--llm_url", type=str, default=None)
    parser.add_argument("--embed_url", type=str, default=None)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "graybox":
        asyncio.run(run_graybox_attack(args))
    else:
        asyncio.run(run_adversarial_attack(args))
