"""Residual Damage 분석 — Attr-Aware propagation의 ~15% 잔여 damage 분류

Attr-Aware propagation이 BFS 대비 damage를 대폭 줄이지만,
여전히 ~15% 수준의 residual damage가 발생한다.
이 스크립트는 각 damaged memory를 아래 두 범주로 분류한다:

  1. Legitimate Cascade: 변경된 fact에 실제로 의존하는 메모리
     (예: "Russia의 president가 Putin" 변경 → "Putin was born in Leningrad" decay)
  2. False Positive: 변경된 fact와 무관하지만 entity graph 연결로 인해 damage

분석 방법:
  - 6K scale memorization 후 5-fact white-box 공격
  - Attr-Aware propagation으로 발생한 모든 damaged memory 수집
  - 각 damaged memory에 대해:
    a. 트리거한 attack fact 및 subject_key 식별
    b. propagation 경로 (어떤 entity chain으로 연결되었는지)
    c. subject entity 매칭 여부 (legitimate dependency signal)
    d. 의미적 의존성 판단 (object entity가 damaged memory의 subject인지)

사용법:
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/residual_analysis.py

  # DooGPU 엔드포인트 지정
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/residual_analysis.py \
    --llm_url https://... --embed_url https://...
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_adapter import MemoryModuleAdapter, DooGPULLMClient
from storage.vector_store import DooGPUEmbeddingProvider
from adversarial_attack import (
    load_data, chunk_text, identify_hub_entities,
    find_high_impact_keys, generate_attack_facts_from_registry,
    snapshot_memory_state, evaluate_queries,
    DEFAULT_LLM_MODEL, DEFAULT_EMBED_MODEL, FAKE_VALUES,
)

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
    "wl-831a629b-4336-480d-8e5e-13f45a796ae6/reserved3/v1"
)
DOOGPU_EMBED_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-831a629b-4336-480d-8e5e-13f45a796ae6/reserved9/v1"
)


def _find_entity_for_memory(graph_store, memory_id: str) -> list[str]:
    """메모리가 연결된 모든 entity 반환"""
    entities = []
    for node_id in graph_store.entity_graph.nodes:
        mem_ids = graph_store.get_memory_ids_for_entity(node_id)
        if memory_id in mem_ids:
            entities.append(node_id)
    return entities


def _find_subject_key_for_memory(fact_registry: dict[str, str], memory_id: str) -> str | None:
    """fact_registry에서 해당 memory_id의 subject_key 찾기"""
    for key, mid in fact_registry.items():
        if mid == memory_id:
            return key
    return None


def _trace_propagation_path(
    graph_store,
    source_entities: set[str],
    target_entities: set[str],
    max_depth: int = 3,
) -> list[str]:
    """source entity에서 target entity까지의 entity graph 경로 추적

    BFS로 source_entities에서 시작하여 target_entities에 도달하는
    최단 경로를 반환한다.
    """
    from collections import deque

    for src in source_entities:
        visited = {src}
        queue = deque([(src, [src])])

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth + 1:
                break

            # target entity에 도달했는지 확인
            if current in target_entities and current != src:
                return path

            for neighbor in graph_store.entity_graph.successors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
            for neighbor in graph_store.entity_graph.predecessors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

    return []


def _classify_damage(
    damaged_mem_content: str,
    damaged_mem_id: str,
    damaged_mem_entities: list[str],
    damaged_mem_subject_key: str | None,
    attack_subject_key: str,
    attack_fact_text: str,
    object_entities: set[str],
    propagation_path: list[str],
) -> dict:
    """개별 damaged memory를 legitimate/false-positive로 분류

    분류 기준:
    1. Legitimate Cascade (True Positive):
       - damaged memory의 subject entity가 attack fact의 object entity와 일치
       - 즉, attack fact에서 변경된 값(object)이 damaged memory의 주어(subject)
       - 예: attack "Russia:president → Mickey Mouse" →
             damaged "Putin:birthplace" (Putin은 기존 president 값)

    2. Co-reference Cascade (Borderline):
       - damaged memory가 attack fact와 동일 entity를 공유하지만
         다른 attribute에 대한 것
       - 예: attack "Russia:president" → damaged "Russia:capital"은 무관

    3. False Positive:
       - graph 연결만으로 전파되었고, 의미적 의존성 없음
    """
    # attack subject_key에서 entity/attribute 분리
    if ":" in attack_subject_key:
        attack_entity, attack_attribute = attack_subject_key.split(":", 1)
    else:
        attack_entity = attack_subject_key
        attack_attribute = ""

    # --- 기준 1: object entity → subject entity 의존성 ---
    # damaged memory의 subject entity가 attack의 object entity와 매칭되는지 확인
    subject_matches_object = False
    if damaged_mem_subject_key and ":" in damaged_mem_subject_key:
        damaged_subject = damaged_mem_subject_key.split(":")[0]
        for obj_ent in object_entities:
            if damaged_subject.lower() == obj_ent.lower():
                subject_matches_object = True
                break

    # --- 기준 2: 동일 entity의 다른 attribute (co-reference) ---
    same_entity_different_attr = False
    if damaged_mem_subject_key and ":" in damaged_mem_subject_key:
        damaged_subject = damaged_mem_subject_key.split(":")[0]
        damaged_attribute = damaged_mem_subject_key.split(":", 1)[1]
        if damaged_subject.lower() == attack_entity.lower() and damaged_attribute != attack_attribute:
            same_entity_different_attr = True

    # --- 기준 3: damaged memory content에 object entity가 직접 언급되는지 ---
    content_mentions_object = False
    for obj_ent in object_entities:
        if obj_ent.lower() in damaged_mem_content.lower():
            content_mentions_object = True
            break

    # --- 분류 결정 ---
    if subject_matches_object:
        classification = "legitimate_cascade"
        reason = (
            f"damaged memory의 subject '{damaged_mem_subject_key}' 가 "
            f"attack fact의 object entity와 일치 — 실제 의존 관계"
        )
    elif content_mentions_object:
        classification = "legitimate_cascade"
        reason = (
            f"damaged memory 내용에 attack fact의 object entity가 "
            f"직접 언급됨 — 의미적 의존 관계"
        )
    elif same_entity_different_attr:
        classification = "false_positive"
        reason = (
            f"동일 entity '{attack_entity}' 의 다른 attribute — "
            f"'{attack_attribute}' 변경이 '{damaged_mem_subject_key}' 에 영향 없음"
        )
    elif propagation_path:
        # propagation 경로가 있지만 위 기준에 해당하지 않으면 borderline
        classification = "borderline"
        reason = (
            f"entity graph 경로로 연결되지만 직접적 의존성 불확실: "
            f"{' → '.join(propagation_path)}"
        )
    else:
        classification = "false_positive"
        reason = "entity graph 연결도 의미적 관련성도 확인 불가"

    return {
        "classification": classification,
        "reason": reason,
        "subject_matches_object": subject_matches_object,
        "content_mentions_object": content_mentions_object,
        "same_entity_different_attr": same_entity_different_attr,
    }


async def run_residual_analysis(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """Attr-Aware propagation의 residual damage 상세 분석

    1. memorization (propagation OFF)
    2. pre-attack memory snapshot (각 memory의 원본 weight 기록)
    3. 5-fact white-box attack (Attr-Aware propagation ON)
    4. damaged memory 식별 및 분류
    """

    # --- Phase 1: Memorization (propagation OFF) ---
    logger.info("Phase 1: Memorization (propagation OFF)")
    adapter = MemoryModuleAdapter(
        graph_propagation=False,
        semantic_filter=True,
        attribute_aware=True,
        propagation_depth=2,
        decay_per_hop=0.5,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )

    chunks = chunk_text(context, chunk_size)
    for chunk in chunks:
        await adapter.async_send_message(chunk, memorizing=True)

    # --- Phase 1.5: Pre-attack 상태 기록 ---
    logger.info("Phase 1.5: Pre-attack state snapshot")
    pre_state = await snapshot_memory_state(adapter)
    all_mems_pre = await adapter._metadata_store.get_all_memories_unfiltered()

    # 각 memory의 원본 weight 저장
    pre_weights: dict[str, float] = {}
    pre_contents: dict[str, str] = {}
    pre_validity: dict[str, bool] = {}
    for mem in all_mems_pre:
        pre_weights[mem.id] = mem.decay_weight
        pre_contents[mem.id] = mem.content
        pre_validity[mem.id] = mem.is_valid

    logger.info(f"  Pre-attack: {pre_state['valid']} valid memories")

    # fact_registry, graph 상태 스냅샷
    fact_registry_snapshot = dict(adapter._fact_registry)
    logger.info(f"  Fact registry: {len(fact_registry_snapshot)} entries")

    # hub entity 정보
    hubs = identify_hub_entities(adapter._graph_store, top_k=5)
    logger.info(f"  Top hub: '{hubs[0]['entity']}' (degree={hubs[0]['degree']})" if hubs else "  No hubs")

    # --- Phase 2: 5-fact White-box Attack (Attr-Aware) ---
    logger.info("Phase 2: 5-fact White-box Attack (Attr-Aware propagation)")
    adapter.graph_propagation = True

    high_impact = find_high_impact_keys(
        adapter._fact_registry, adapter._graph_store, top_k=10
    )
    matching_keys = [k for k, _ in high_impact]
    max_serial = max(adapter._serial_registry.keys()) if adapter._serial_registry else 0

    num_attack_facts = 5
    attack_facts = generate_attack_facts_from_registry(
        matching_keys, num_attack_facts, max_serial
    )

    # 공격 fact별 상세 정보 수집
    attack_details: list[dict] = []
    for fact_line, target_key in attack_facts:
        logger.info(f"  Injecting: {fact_line} (target: {target_key})")

        # 공격 전 해당 target_key의 old_memory_id 확인
        old_memory_id = adapter._fact_registry.get(target_key)
        old_memory_content = pre_contents.get(old_memory_id, "N/A") if old_memory_id else "N/A"

        # object entity 수집 (attack fact의 값/대상 entity)
        # 공격 전에 entity graph에서 old_memory가 연결된 entity 중 subject가 아닌 것
        object_entities_for_attack: set[str] = set()
        if old_memory_id:
            old_mem_entities = _find_entity_for_memory(adapter._graph_store, old_memory_id)
            subject_entity = target_key.split(":")[0] if ":" in target_key else ""
            for ent in old_mem_entities:
                if ent.lower() != subject_entity.lower():
                    object_entities_for_attack.add(ent)

        await adapter.async_send_message(fact_line, memorizing=True)

        attack_details.append({
            "fact_line": fact_line,
            "target_key": target_key,
            "old_memory_id": old_memory_id,
            "old_memory_content": old_memory_content,
            "object_entities": list(object_entities_for_attack),
        })

    # --- Phase 3: Damaged memory 식별 ---
    logger.info("Phase 3: Identifying damaged memories")
    all_mems_post = await adapter._metadata_store.get_all_memories_unfiltered()

    # 새로 추가된 attack memory의 ID 수집 (이들은 damage 대상에서 제외)
    attack_memory_ids: set[str] = set()
    for mem in all_mems_post:
        if mem.id not in pre_weights:
            attack_memory_ids.add(mem.id)

    # damaged = weight가 감소했거나 invalidated된 메모리
    damaged_memories: list[dict] = []
    for mem in all_mems_post:
        if mem.id in attack_memory_ids:
            continue  # 공격 fact 자체는 제외

        orig_weight = pre_weights.get(mem.id, 1.0)
        orig_valid = pre_validity.get(mem.id, True)

        # weight 감소 또는 invalidated
        weight_decreased = mem.decay_weight < orig_weight
        was_invalidated = orig_valid and not mem.is_valid

        if weight_decreased or was_invalidated:
            damaged_memories.append({
                "memory_id": mem.id,
                "content": mem.content,
                "original_weight": orig_weight,
                "current_weight": mem.decay_weight,
                "weight_drop": orig_weight - mem.decay_weight,
                "was_invalidated": was_invalidated,
                "is_killed": mem.decay_weight < 0.1 and not was_invalidated,
            })

    logger.info(f"  Total damaged: {len(damaged_memories)} memories")
    logger.info(f"  Invalidated (direct conflict): {sum(1 for d in damaged_memories if d['was_invalidated'])}")
    logger.info(f"  Weight decreased (propagation): {sum(1 for d in damaged_memories if not d['was_invalidated'])}")

    # --- Phase 4: 각 damaged memory 분류 ---
    logger.info("Phase 4: Classifying each damaged memory")
    classified_results: list[dict] = []

    for dmg in damaged_memories:
        mem_id = dmg["memory_id"]
        mem_content = dmg["content"]

        # 이 memory가 연결된 entity 목록
        mem_entities = _find_entity_for_memory(adapter._graph_store, mem_id)

        # 이 memory의 subject_key (fact_registry에서)
        mem_subject_key = _find_subject_key_for_memory(fact_registry_snapshot, mem_id)

        # 어떤 attack fact가 이 damage를 트리거했는지 찾기
        triggering_attack = None
        for atk in attack_details:
            if dmg["was_invalidated"] and atk["old_memory_id"] == mem_id:
                # 직접 충돌로 invalidated된 경우
                triggering_attack = atk
                break

            # propagation으로 damaged된 경우: object entity chain 확인
            # attack의 object_entities가 damaged memory의 entity와 겹치는지
            if not dmg["was_invalidated"]:
                atk_objects = set(atk["object_entities"])
                mem_ents_set = set(mem_entities)

                # damaged memory의 subject entity가 attack의 object entity인지
                if mem_subject_key and ":" in mem_subject_key:
                    damaged_subject = mem_subject_key.split(":")[0]
                    for obj_ent in atk_objects:
                        if damaged_subject.lower() == obj_ent.lower():
                            triggering_attack = atk
                            break

                # entity 겹침으로 찾기
                if triggering_attack is None and atk_objects & mem_ents_set:
                    triggering_attack = atk

        if triggering_attack is None and attack_details:
            # fallback: 첫 번째 attack으로 귀속 (경로 불명)
            triggering_attack = attack_details[0]

        # propagation 경로 추적
        propagation_path = []
        if triggering_attack and not dmg["was_invalidated"]:
            source_entities = set(triggering_attack.get("object_entities", []))
            target_entities = set(mem_entities)
            propagation_path = _trace_propagation_path(
                adapter._graph_store, source_entities, target_entities, max_depth=3
            )

        # 분류
        object_entities = set(triggering_attack.get("object_entities", [])) if triggering_attack else set()
        classification = _classify_damage(
            damaged_mem_content=mem_content,
            damaged_mem_id=mem_id,
            damaged_mem_entities=mem_entities,
            damaged_mem_subject_key=mem_subject_key,
            attack_subject_key=triggering_attack["target_key"] if triggering_attack else "",
            attack_fact_text=triggering_attack["fact_line"] if triggering_attack else "",
            object_entities=object_entities,
            propagation_path=propagation_path,
        )

        classified_results.append({
            "memory_id": mem_id,
            "memory_content": mem_content,
            "memory_subject_key": mem_subject_key,
            "memory_entities": mem_entities,
            "original_weight": dmg["original_weight"],
            "current_weight": dmg["current_weight"],
            "weight_drop": dmg["weight_drop"],
            "was_invalidated": dmg["was_invalidated"],
            "is_killed": dmg["is_killed"],
            "triggering_attack": {
                "fact_line": triggering_attack["fact_line"] if triggering_attack else "unknown",
                "target_key": triggering_attack["target_key"] if triggering_attack else "unknown",
                "old_memory_content": triggering_attack["old_memory_content"] if triggering_attack else "unknown",
                "object_entities": list(object_entities),
            },
            "propagation_path": propagation_path,
            "classification": classification["classification"],
            "classification_reason": classification["reason"],
            "classification_details": {
                "subject_matches_object": classification["subject_matches_object"],
                "content_mentions_object": classification["content_mentions_object"],
                "same_entity_different_attr": classification["same_entity_different_attr"],
            },
        })

    # --- Phase 5: 집계 ---
    logger.info("Phase 5: Aggregation")

    # 직접 충돌 (invalidated) 제외하고 propagation damage만 분석
    propagation_damaged = [r for r in classified_results if not r["was_invalidated"]]

    total_propagation = len(propagation_damaged)
    legitimate_count = sum(1 for r in propagation_damaged if r["classification"] == "legitimate_cascade")
    borderline_count = sum(1 for r in propagation_damaged if r["classification"] == "borderline")
    false_positive_count = sum(1 for r in propagation_damaged if r["classification"] == "false_positive")

    logger.info(f"  Propagation-damaged memories: {total_propagation}")
    logger.info(f"    Legitimate cascade: {legitimate_count} ({legitimate_count / max(total_propagation, 1) * 100:.1f}%)")
    logger.info(f"    Borderline: {borderline_count} ({borderline_count / max(total_propagation, 1) * 100:.1f}%)")
    logger.info(f"    False positive: {false_positive_count} ({false_positive_count / max(total_propagation, 1) * 100:.1f}%)")

    # Post-attack EM 평가
    post_metrics = await evaluate_queries(adapter, questions, answers, max_queries)
    logger.info(f"  Post-attack EM: {post_metrics['exact_match']:.1f}%")

    await adapter.reset()

    return {
        "config": {
            "context_size": "6k",
            "num_attack_facts": num_attack_facts,
            "propagation_mode": "attr_aware",
            "propagation_depth": 2,
            "decay_per_hop": 0.5,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "pre_attack_state": {k: v for k, v in pre_state.items() if k != "weights"},
        "attack_details": attack_details,
        "hub_entities": [
            {"entity": h["entity"], "degree": h["degree"], "memory_count": h["memory_count"]}
            for h in hubs[:5]
        ],
        "fact_registry_size": len(fact_registry_snapshot),
        "damage_summary": {
            "total_memories": pre_state["valid"],
            "total_damaged": len(damaged_memories),
            "directly_invalidated": sum(1 for d in damaged_memories if d["was_invalidated"]),
            "propagation_damaged": total_propagation,
            "damage_ratio_pct": round(len(damaged_memories) / max(pre_state["valid"], 1) * 100, 2),
            "propagation_damage_ratio_pct": round(total_propagation / max(pre_state["valid"], 1) * 100, 2),
        },
        "classification_summary": {
            "total_propagation_damaged": total_propagation,
            "legitimate_cascade": legitimate_count,
            "legitimate_cascade_pct": round(legitimate_count / max(total_propagation, 1) * 100, 2),
            "borderline": borderline_count,
            "borderline_pct": round(borderline_count / max(total_propagation, 1) * 100, 2),
            "false_positive": false_positive_count,
            "false_positive_pct": round(false_positive_count / max(total_propagation, 1) * 100, 2),
        },
        "post_attack_metrics": {
            "exact_match": round(post_metrics["exact_match"], 2),
            "f1": round(post_metrics["f1"], 2),
        },
        "classified_damages": classified_results,
    }


def print_report(result: dict):
    """콘솔에 상세 리포트 출력"""
    print("\n" + "=" * 90)
    print("RESIDUAL DAMAGE ANALYSIS — Attr-Aware Propagation")
    print("=" * 90)

    ds = result["damage_summary"]
    cs = result["classification_summary"]

    print(f"\n### Damage Overview")
    print(f"  Total memories (pre-attack): {ds['total_memories']}")
    print(f"  Total damaged:               {ds['total_damaged']} ({ds['damage_ratio_pct']:.1f}%)")
    print(f"    Directly invalidated:      {ds['directly_invalidated']} (conflict resolution)")
    print(f"    Propagation damaged:       {ds['propagation_damaged']} ({ds['propagation_damage_ratio_pct']:.1f}%)")

    print(f"\n### Classification of Propagation Damage")
    print(f"  {'Category':<24} | {'Count':>6} | {'Percent':>8}")
    print(f"  {'-'*24}-+-{'-'*6}-+-{'-'*8}")
    print(f"  {'Legitimate Cascade':<24} | {cs['legitimate_cascade']:>6} | {cs['legitimate_cascade_pct']:>7.1f}%")
    print(f"  {'Borderline':<24} | {cs['borderline']:>6} | {cs['borderline_pct']:>7.1f}%")
    print(f"  {'False Positive':<24} | {cs['false_positive']:>6} | {cs['false_positive_pct']:>7.1f}%")

    pm = result["post_attack_metrics"]
    print(f"\n### Post-attack Retrieval")
    print(f"  EM:  {pm['exact_match']:.1f}%")
    print(f"  F1:  {pm['f1']:.1f}%")

    # 각 attack fact의 상세
    print(f"\n### Attack Facts ({len(result['attack_details'])})")
    for i, atk in enumerate(result["attack_details"]):
        print(f"\n  [{i+1}] {atk['fact_line']}")
        print(f"      Target key:     {atk['target_key']}")
        print(f"      Old content:    {atk['old_memory_content'][:80]}...")
        print(f"      Object entities: {atk['object_entities']}")

    # 각 damaged memory의 상세 (propagation damaged만)
    prop_damaged = [r for r in result["classified_damages"] if not r["was_invalidated"]]
    print(f"\n### Propagation-Damaged Memories ({len(prop_damaged)})")
    for i, dmg in enumerate(prop_damaged):
        cls_marker = {
            "legitimate_cascade": "[LEGIT]",
            "borderline": "[BORDER]",
            "false_positive": "[FALSE+]",
        }.get(dmg["classification"], "[???]")

        print(f"\n  {cls_marker} #{i+1}")
        print(f"    Content:       {dmg['memory_content'][:100]}")
        print(f"    Subject key:   {dmg['memory_subject_key']}")
        print(f"    Entities:      {dmg['memory_entities'][:5]}")
        print(f"    Weight:        {dmg['original_weight']:.4f} → {dmg['current_weight']:.4f} (Δ={dmg['weight_drop']:.4f})")
        print(f"    Triggered by:  {dmg['triggering_attack']['target_key']}")
        print(f"    Path:          {' → '.join(dmg['propagation_path']) if dmg['propagation_path'] else 'N/A'}")
        print(f"    Reason:        {dmg['classification_reason']}")
        print(f"    Details:       sub=obj: {dmg['classification_details']['subject_matches_object']}, "
              f"content_mentions: {dmg['classification_details']['content_mentions_object']}, "
              f"same_ent_diff_attr: {dmg['classification_details']['same_entity_different_attr']}")

    print("\n" + "=" * 90)


async def main(args):
    """Residual damage 분석 실행"""

    sub_dataset = f"factconsolidation_mh_{args.context_size}"
    samples = load_data(sub_dataset, max_contexts=1)
    if not samples:
        logger.error(f"데이터 없음: {sub_dataset}")
        return

    sample = samples[0]
    context = sample["context"]
    questions = sample["questions"]
    answers = sample["answers"]

    llm_url = args.llm_url or DOOGPU_LLM_BASE
    embed_url = args.embed_url or DOOGPU_EMBED_BASE
    llm_client = DooGPULLMClient(base_url=llm_url, model=DEFAULT_LLM_MODEL)
    embedding_provider = DooGPUEmbeddingProvider(
        base_url=embed_url, model=DEFAULT_EMBED_MODEL
    )

    result = await run_residual_analysis(
        context=context,
        questions=questions,
        answers=answers,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        chunk_size=args.chunk_size,
        max_queries=args.max_queries,
    )

    # --- 결과 저장 ---
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / "residual_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"\n결과 저장: {out_path}")

    # --- 콘솔 리포트 ---
    print_report(result)

    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Residual damage 분석")
    parser.add_argument("--context_size", type=str, default="6k")
    parser.add_argument("--chunk_size", type=int, default=4096)
    parser.add_argument("--max_queries", type=int, default=10)
    parser.add_argument("--llm_url", type=str, default=None)
    parser.add_argument("--embed_url", type=str, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
