"""Cross-task 벤치마크 — Accurate_Retrieval에서 collateral damage의 검색 정확도 영향

FactConsolidation(Conflict_Resolution)에서 BFS 전파가 68-79%의 유효 메모리를
파괴한다는 것을 확인했다. 이 실험은 **다른 태스크 유형**(Accurate_Retrieval)에서도
collateral damage가 검색 정확도를 저하시키는지 측정한다.

실험 설계:
  각 sample에 대해 3개 arm을 비교:
  1. Baseline: 모든 fact 기억 → 질문 → EM/F1 측정
  2. Post-BFS: fact update 트리거 → BFS 전파 → 질문 → EM/F1 측정
  3. Post-Attribute-aware: fact update 트리거 → Attribute-aware 전파 → 질문 → EM/F1 측정

핵심 가설:
  BFS collateral damage가 정확한 검색에 필요한 메모리를 파괴하여 EM이 하락한다.
  Attribute-aware는 관련 메모리만 선택적으로 갱신하여 EM을 보존한다.

사용법:
  # 기본 실행 (eventqa_65536, 5 샘플)
  python experiments/benchmark_accurate_retrieval.py

  # 다른 sub_dataset
  python experiments/benchmark_accurate_retrieval.py --sub_dataset eventqa_131072

  # 샘플 수 제한
  python experiments/benchmark_accurate_retrieval.py --max_samples 2

  # DooGPU 엔드포인트 지정
  python experiments/benchmark_accurate_retrieval.py \\
    --llm_url http://10.0.0.1:8080/v1 \\
    --embed_url http://10.0.0.1:8081/v1
"""

from __future__ import annotations

import argparse
import asyncio
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
from config import settings
from experiments.preprint_hubs import select_actionable_hubs
from storage.vector_store import DooGPUEmbeddingProvider, MockEmbeddingProvider

logger = logging.getLogger(__name__)

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

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


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
    precision = num_common / len(pred_tokens) if pred_tokens else 0.0
    recall = num_common / len(gt_tokens) if gt_tokens else 0.0
    if precision + recall == 0:
        return 0.0
    return (2 * precision * recall) / (precision + recall)


def max_over_ground_truths(metric_fn, prediction: str, ground_truths: list[str]):
    """여러 정답 중 최대 스코어 반환"""
    if isinstance(ground_truths, str):
        ground_truths = [ground_truths]
    return max(metric_fn(prediction, gt) for gt in ground_truths)


# --- 데이터 로딩 ---

def load_accurate_retrieval_data(
    sub_dataset: str, max_samples: int | None = None
) -> list[dict]:
    """HuggingFace에서 Accurate_Retrieval 데이터 로드

    Args:
        sub_dataset: 하위 데이터셋 이름 (eventqa_65536, eventqa_131072, etc.)
        max_samples: 최대 샘플 수

    Returns:
        list[dict]: 각 dict는 context, questions, answers 포함
    """
    from datasets import load_dataset

    logger.info(f"HuggingFace에서 Accurate_Retrieval / {sub_dataset} 로딩 중...")
    raw = load_dataset(
        "ai-hyz/MemoryAgentBench", split="Accurate_Retrieval", revision="main"
    )

    # sub_dataset 필터링 — metadata.source 필드 기준
    filtered = raw.filter(
        lambda s: s.get("metadata", {}).get("source", "") == sub_dataset
    )
    logger.info(f"로드 완료: {len(filtered)} 샘플, 소스={sub_dataset}")

    if max_samples and len(filtered) > max_samples:
        filtered = filtered.select(range(max_samples))

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


# --- 청킹 ---

def chunk_text_simple(text: str, chunk_size: int = 4096) -> list[str]:
    """줄 단위 청킹 — 1 토큰 ≈ 4 characters 근사"""
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_chars = 0
    char_limit = chunk_size * 4

    for line in lines:
        line_chars = len(line)
        if current_chars + line_chars > char_limit and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_chars = line_chars
        else:
            current_chunk.append(line)
            current_chars += line_chars

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


# --- 그래프 분석 유틸 ---

def find_high_degree_entity(adapter: MemoryModuleAdapter) -> tuple[str, int] | None:
    """그래프에서 가장 degree가 높은 entity를 찾는다 (hub entity)

    Returns:
        (entity_name, degree) 또는 None
    """
    result = find_high_degree_entities(adapter, top_k=1)
    return result[0] if result else None


def find_high_degree_entities(
    adapter: MemoryModuleAdapter, top_k: int = 5
) -> list[tuple[str, int]]:
    """그래프에서 degree 기준 상위 N개 hub entity 반환

    Returns:
        [(entity_name, degree), ...] degree 내림차순
    """
    graph = adapter._graph_store.entity_graph
    if graph.number_of_nodes() == 0:
        return []

    node_degrees = []
    for node in graph.nodes:
        degree = graph.in_degree(node) + graph.out_degree(node)
        node_degrees.append((node, degree))

    node_degrees.sort(key=lambda x: x[1], reverse=True)
    return node_degrees[:top_k]


def find_fact_for_entity(
    adapter: MemoryModuleAdapter, entity_name: str
) -> tuple[str, str] | None:
    """특정 entity를 subject로 가지는 fact의 (subject_key, memory_id)를 찾는다

    fact_registry에서 entity_name을 subject로 가지는 첫 번째 항목 반환
    """
    for reg_key, mem_id in adapter._fact_registry.items():
        if ":" not in reg_key:
            continue
        subject, _attr = reg_key.split(":", 1)
        if subject.lower() == entity_name.lower():
            return (reg_key, mem_id)
    return None


async def count_memory_stats(adapter: MemoryModuleAdapter) -> dict:
    """현재 메모리 상태 통계 수집"""
    all_memories = await adapter._metadata_store.get_all_memories_unfiltered()
    valid = [m for m in all_memories if m.is_valid]
    invalid = [m for m in all_memories if not m.is_valid]

    # decay_weight 기반 분류 (retrieval에 실질적으로 사용 가능한지)
    RETRIEVAL_THRESHOLD = 0.3
    retrievable = [m for m in valid if m.decay_weight >= RETRIEVAL_THRESHOLD]
    decayed_below_threshold = [
        m for m in valid if m.decay_weight < RETRIEVAL_THRESHOLD
    ]

    return {
        "total": len(all_memories),
        "valid": len(valid),
        "invalid": len(invalid),
        "retrievable": len(retrievable),
        "decayed_below_threshold": len(decayed_below_threshold),
        "avg_weight_valid": (
            sum(m.decay_weight for m in valid) / len(valid) if valid else 0.0
        ),
    }


# --- 전파 트리거 ---

async def trigger_propagation(
    adapter: MemoryModuleAdapter,
    hub_entity: str,
    mode: str,
) -> dict:
    """hub entity에 대한 fact update를 트리거하여 전파 실행

    Args:
        adapter: 이미 memorize가 완료된 어댑터
        hub_entity: 전파를 트리거할 hub entity 이름
        mode: "bfs" 또는 "attribute_aware"

    Returns:
        dict: 전파 결과 통계
    """
    # hub entity를 subject로 가지는 fact 찾기
    fact_info = find_fact_for_entity(adapter, hub_entity)
    if not fact_info:
        logger.warning(f"  hub entity '{hub_entity}'에 대한 fact를 찾을 수 없음")
        return {"affected_count": 0, "error": "no_fact_found"}

    subject_key, old_memory_id = fact_info
    entity_part, attr_part = subject_key.split(":", 1)

    # 새로운 fact 생성 (기존 fact의 값을 변경)
    old_mem = await adapter._metadata_store.get_memory(old_memory_id)
    if not old_mem:
        return {"affected_count": 0, "error": "memory_not_found"}

    # 기존 fact를 무효화
    await adapter._metadata_store.invalidate_memory(old_memory_id)

    # 전파 실행
    if mode == "bfs":
        # BFS 모드: subject_key=None → legacy BFS 경로
        affected = await adapter._decay_engine.propagate_invalidation(
            invalidated_memory_id=old_memory_id,
            graph_store=adapter._graph_store,
            metadata_store=adapter._metadata_store,
            propagation_depth=adapter.propagation_depth,
            decay_per_hop=adapter.decay_per_hop,
            semantic_filter=False,  # BFS는 semantic filter 없이 전파
            new_content=None,
            subject_key=None,
            fact_registry=None,
        )
    elif mode == "attribute_aware":
        # Attribute-aware 모드: subject_key 전달
        affected = await adapter._decay_engine.propagate_invalidation(
            invalidated_memory_id=old_memory_id,
            graph_store=adapter._graph_store,
            metadata_store=adapter._metadata_store,
            propagation_depth=adapter.propagation_depth,
            decay_per_hop=adapter.decay_per_hop,
            semantic_filter=True,
            new_content=f"The {attr_part} of {entity_part} has changed.",
            subject_key=subject_key,
            fact_registry=adapter._fact_registry,
        )
    else:
        raise ValueError(f"Unknown propagation mode: {mode}")

    return {
        "affected_count": len(affected),
        "affected_memory_ids": affected,
        "trigger_subject_key": subject_key,
        "trigger_memory_id": old_memory_id,
        "trigger_content": old_mem.content,
    }


# --- 쿼리 평가 ---

async def evaluate_queries(
    adapter: MemoryModuleAdapter,
    questions: list[str],
    answers: list,
    max_queries: int | None = None,
) -> dict:
    """질문 리스트에 대해 EM/F1 평가

    Returns:
        dict: metrics + per_query_results
    """
    n_queries = len(questions)
    if max_queries is not None and max_queries < n_queries:
        n_queries = max_queries

    total_em = 0.0
    total_sub_em = 0.0
    total_f1 = 0.0
    per_query = []

    for q_idx in range(n_queries):
        question = questions[q_idx]
        ground_truth = answers[q_idx]
        gt_list = ground_truth if isinstance(ground_truth, list) else [ground_truth]

        result = await adapter.async_send_message(
            question, memorizing=False, query_id=q_idx, context_id=0
        )

        output = result.get("output", "") if isinstance(result, dict) else str(result)

        em = max_over_ground_truths(exact_match, output, gt_list)
        sub = max_over_ground_truths(substring_exact_match, output, gt_list)
        f1 = max_over_ground_truths(f1_score, output, gt_list)

        total_em += float(em)
        total_sub_em += float(sub)
        total_f1 += f1

        per_query.append({
            "query_id": q_idx,
            "question": question,
            "ground_truth": gt_list,
            "prediction": output,
            "exact_match": float(em),
            "substring_exact_match": float(sub),
            "f1": f1,
        })

    metrics = {}
    if n_queries > 0:
        metrics = {
            "exact_match": total_em / n_queries * 100,
            "substring_exact_match": total_sub_em / n_queries * 100,
            "f1": total_f1 / n_queries * 100,
            "total_queries": n_queries,
        }

    return {"metrics": metrics, "per_query": per_query}


# --- 단일 샘플 실행 ---

async def run_sample(
    sample: dict,
    sample_idx: int,
    llm_client: DooGPULLMClient,
    embedding_provider: DooGPUEmbeddingProvider,
    chunk_size: int,
    max_queries: int | None,
    propagation_depth: int,
    decay_per_hop: float,
    num_hubs: int = 1,
    named_entity_hubs: bool = False,
) -> dict:
    """하나의 sample에 대해 3개 arm(Baseline, BFS, Attribute-aware) 실행

    Args:
        num_hubs: 실험할 hub entity 수. 1이면 기존 단일 hub 실험,
                  >1이면 상위 N개 hub 각각에서 propagation → measure → restore 루프.

    Returns:
        dict: 각 arm의 메트릭 + collateral damage 통계
    """
    context = sample["context"]
    questions = sample["questions"]
    answers = sample["answers"]
    chunks = chunk_text_simple(context, chunk_size)

    logger.info(f"[Sample {sample_idx}] {len(context)} chars, "
                f"{len(chunks)} 청크, {len(questions)} 질문")

    results = {"sample_idx": sample_idx, "n_chunks": len(chunks),
               "n_questions": len(questions), "context_chars": len(context)}

    # ================================================================
    # ARM 1: Baseline — 전파 없이 memorize + query
    # ================================================================
    logger.info(f"[Sample {sample_idx}] ARM 1: Baseline (전파 없음)")

    baseline_adapter = MemoryModuleAdapter(
        graph_propagation=False,
        semantic_filter=False,
        attribute_aware=False,
        propagation_depth=propagation_depth,
        decay_per_hop=decay_per_hop,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )

    # Memorize
    mem_start = time.time()
    for chunk_idx, chunk in enumerate(chunks):
        await baseline_adapter.async_send_message(chunk, memorizing=True)
        if (chunk_idx + 1) % 10 == 0:
            logger.info(f"  memorize: {chunk_idx + 1}/{len(chunks)} 청크")
    baseline_mem_time = time.time() - mem_start
    logger.info(f"  memorize 완료: {baseline_mem_time:.1f}s")

    # Baseline 메모리 상태
    baseline_stats = await count_memory_stats(baseline_adapter)
    logger.info(f"  메모리: total={baseline_stats['total']}, "
                f"valid={baseline_stats['valid']}, "
                f"retrievable={baseline_stats['retrievable']}")

    # Hub entity 식별 (BFS/Attr-aware에서 사용)
    raw_hub_limit = num_hubs * 10 if named_entity_hubs else num_hubs
    all_hubs = find_high_degree_entities(baseline_adapter, top_k=raw_hub_limit)
    if named_entity_hubs:
        hub_dicts = [
            {"entity": entity, "degree": degree}
            for entity, degree in all_hubs
        ]
        filtered_hubs = select_actionable_hubs(
            hub_dicts,
            top_k=num_hubs,
            has_trigger_fact=lambda entity: (
                find_fact_for_entity(baseline_adapter, entity) is not None
            ),
        )
        all_hubs = [
            (str(hub["entity"]), int(hub["degree"]))
            for hub in filtered_hubs
        ]
    hub_entity = all_hubs[0][0] if all_hubs else None
    hub_degree = all_hubs[0][1] if all_hubs else 0
    logger.info(f"  Top hub: {hub_entity} (degree={hub_degree})")
    if num_hubs > 1:
        logger.info(f"  Multi-hub: {len(all_hubs)} hubs → "
                     f"{[(h[0], h[1]) for h in all_hubs]}")

    # Baseline query 평가
    q_start = time.time()
    baseline_eval = await evaluate_queries(
        baseline_adapter, questions, answers, max_queries
    )
    baseline_query_time = time.time() - q_start

    results["baseline"] = {
        "metrics": baseline_eval["metrics"],
        "per_query": baseline_eval["per_query"],
        "memory_stats": baseline_stats,
        "memorize_time": baseline_mem_time,
        "query_time": baseline_query_time,
        "hub_entity": hub_entity,
        "hub_degree": hub_degree,
        "all_hubs": [{"entity": h[0], "degree": h[1]} for h in all_hubs],
    }
    logger.info(f"  Baseline EM={baseline_eval['metrics'].get('exact_match', 0):.1f}%, "
                f"F1={baseline_eval['metrics'].get('f1', 0):.1f}%")

    if not hub_entity:
        logger.warning(f"[Sample {sample_idx}] hub entity가 없어 전파 실험 스킵")
        results["bfs"] = {"error": "no_hub_entity", "metrics": {}, "per_query": []}
        results["attribute_aware"] = {"error": "no_hub_entity", "metrics": {}, "per_query": []}
        return results

    # ================================================================
    # Multi-hub 또는 단일 hub 실험
    # ================================================================
    hubs_to_test = all_hubs if num_hubs > 1 else [(hub_entity, hub_degree)]

    # --- ARM 2 & 3: BFS / Attribute-aware (hub별 snapshot-restore 루프) ---
    for arm_name, arm_config in [
        ("bfs", {"semantic_filter": False, "attribute_aware": False}),
        ("attribute_aware", {"semantic_filter": True, "attribute_aware": True}),
    ]:
        arm_label = arm_name.upper().replace("_", "-")
        arm_idx = 2 if arm_name == "bfs" else 3
        logger.info(f"[Sample {sample_idx}] ARM {arm_idx}: Post-{arm_label} 전파")

        adapter = MemoryModuleAdapter(
            graph_propagation=True,
            semantic_filter=arm_config["semantic_filter"],
            attribute_aware=arm_config["attribute_aware"],
            propagation_depth=propagation_depth,
            decay_per_hop=decay_per_hop,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
        )

        # Memorize (동일 데이터)
        for chunk in chunks:
            await adapter.async_send_message(chunk, memorizing=True)

        # Weight 스냅샷 (multi-hub restore용)
        weight_snapshot = await adapter._metadata_store.snapshot_weights()

        per_hub_results = []
        for hub_idx, (h_entity, h_degree) in enumerate(hubs_to_test):
            if hub_idx > 0:
                # 이전 hub의 전파 효과 복원
                await adapter._metadata_store.restore_weights(weight_snapshot)

            logger.info(f"  [{arm_label}] Hub {hub_idx+1}/{len(hubs_to_test)}: "
                        f"'{h_entity}' (degree={h_degree})")

            pre_stats = await count_memory_stats(adapter)
            propagation = await trigger_propagation(adapter, h_entity, mode=arm_name)
            post_stats = await count_memory_stats(adapter)
            collateral = pre_stats["retrievable"] - post_stats["retrievable"]

            logger.info(f"    전파: {propagation.get('affected_count', 0)}개 영향, "
                        f"collateral={collateral}")

            # Query 평가
            eval_result = await evaluate_queries(
                adapter, questions, answers, max_queries
            )
            em = eval_result["metrics"].get("exact_match", 0)
            f1 = eval_result["metrics"].get("f1", 0)
            logger.info(f"    EM={em:.1f}%, F1={f1:.1f}%")

            per_hub_results.append({
                "hub_entity": h_entity,
                "hub_degree": h_degree,
                "metrics": eval_result["metrics"],
                "per_query": eval_result["per_query"],
                "memory_stats_pre": pre_stats,
                "memory_stats_post": post_stats,
                "propagation": {
                    "affected_count": propagation.get("affected_count", 0),
                    "trigger_subject_key": propagation.get("trigger_subject_key"),
                    "trigger_content": propagation.get("trigger_content"),
                },
                "collateral_damage": collateral,
            })

        # 집계: 단일 hub이면 기존 형식 유지, multi-hub이면 평균+분산 추가
        if len(per_hub_results) == 1:
            results[arm_name] = per_hub_results[0]
        else:
            # Multi-hub 평균 메트릭
            avg_em = sum(r["metrics"].get("exact_match", 0) for r in per_hub_results) / len(per_hub_results)
            avg_f1 = sum(r["metrics"].get("f1", 0) for r in per_hub_results) / len(per_hub_results)
            avg_collateral = sum(r["collateral_damage"] for r in per_hub_results) / len(per_hub_results)

            import statistics
            em_values = [r["metrics"].get("exact_match", 0) for r in per_hub_results]
            f1_values = [r["metrics"].get("f1", 0) for r in per_hub_results]
            collateral_values = [r["collateral_damage"] for r in per_hub_results]

            std_em = statistics.stdev(em_values) if len(em_values) > 1 else 0
            std_f1 = statistics.stdev(f1_values) if len(f1_values) > 1 else 0
            std_collateral = statistics.stdev(collateral_values) if len(collateral_values) > 1 else 0

            results[arm_name] = {
                "metrics": {
                    "exact_match": avg_em,
                    "f1": avg_f1,
                    "total_queries": per_hub_results[0]["metrics"].get("total_queries", 0),
                },
                "per_query": per_hub_results[0]["per_query"],  # 첫 hub 기준
                "memory_stats_pre": per_hub_results[0]["memory_stats_pre"],
                "memory_stats_post": per_hub_results[-1]["memory_stats_post"],
                "collateral_damage": avg_collateral,
                "multi_hub": {
                    "num_hubs": len(per_hub_results),
                    "avg_em": round(avg_em, 2),
                    "std_em": round(std_em, 2),
                    "avg_f1": round(avg_f1, 2),
                    "std_f1": round(std_f1, 2),
                    "avg_collateral": round(avg_collateral, 2),
                    "std_collateral": round(std_collateral, 2),
                    "per_hub": [
                        {
                            "hub_entity": r["hub_entity"],
                            "hub_degree": r["hub_degree"],
                            "em": r["metrics"].get("exact_match", 0),
                            "f1": r["metrics"].get("f1", 0),
                            "collateral": r["collateral_damage"],
                            "affected": r["propagation"]["affected_count"],
                        }
                        for r in per_hub_results
                    ],
                },
            }
            logger.info(f"  [{arm_label}] Multi-hub 평균: "
                        f"EM={avg_em:.1f}±{std_em:.1f}%, "
                        f"F1={avg_f1:.1f}±{std_f1:.1f}%, "
                        f"collateral={avg_collateral:.1f}±{std_collateral:.1f}")

        await adapter.reset()

    # Baseline 어댑터 정리
    await baseline_adapter.reset()

    return results


# --- 메인 벤치마크 ---

async def run_benchmark(args):
    """Cross-task 벤치마크 실행: Accurate_Retrieval에서 collateral damage 영향 측정"""
    if args.disable_graph_persist:
        settings.graph_serialize_interval = 10**12

    # --- 데이터 로드 ---
    samples = load_accurate_retrieval_data(args.sub_dataset, args.max_samples)
    if not samples:
        logger.error(f"데이터를 찾을 수 없음: {args.sub_dataset}")
        logger.info("사용 가능한 sub_dataset: eventqa_65536, eventqa_131072, "
                     "eventqa_full, longmemeval_s*, ruler_qa1_197K, ruler_qa2_421K")
        return

    logger.info(f"데이터 로드 완료: {len(samples)} 샘플")
    for i, s in enumerate(samples):
        logger.info(f"  샘플 {i}: {len(s['context'])} chars, {len(s['questions'])} 질문")

    # --- LLM/Embedding 클라이언트 ---
    llm_url = args.llm_url or DOOGPU_LLM_BASE
    embed_url = args.embed_url or DOOGPU_EMBED_BASE

    llm_model = args.llm_model or DEFAULT_LLM_MODEL
    embed_model = args.embed_model or DEFAULT_EMBED_MODEL

    logger.info(f"LLM: {llm_url} / {llm_model}")
    logger.info(
        "Embedding: "
        + (
            "MockEmbeddingProvider (smoke only, not paper-valid)"
            if args.mock_embedding
            else f"{embed_url} / {embed_model}"
        )
    )

    llm_client = DooGPULLMClient(base_url=llm_url, model=llm_model)
    if args.mock_embedding:
        embedding_provider = MockEmbeddingProvider(dim=1024)
    else:
        embedding_provider = DooGPUEmbeddingProvider(
            base_url=embed_url, model=embed_model
        )

    # --- 샘플별 실행 ---
    all_results = []
    for idx, sample in enumerate(samples):
        logger.info("=" * 60)
        logger.info(f"샘플 {idx + 1}/{len(samples)} 처리 시작")
        logger.info("=" * 60)

        sample_result = await run_sample(
            sample=sample,
            sample_idx=idx,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
            propagation_depth=args.propagation_depth,
            decay_per_hop=args.decay_per_hop,
            num_hubs=args.num_hubs,
            named_entity_hubs=args.named_entity_hubs,
        )
        all_results.append(sample_result)

    # --- 전체 집계 ---
    logger.info("=" * 60)
    logger.info("전체 결과 집계")
    logger.info("=" * 60)

    aggregate = _compute_aggregate(all_results)

    for arm_name in ["baseline", "bfs", "attribute_aware"]:
        arm_agg = aggregate.get(arm_name, {})
        logger.info(
            f"  {arm_name:20s}: "
            f"EM={arm_agg.get('exact_match', 0):.1f}%  "
            f"SubEM={arm_agg.get('substring_exact_match', 0):.1f}%  "
            f"F1={arm_agg.get('f1', 0):.1f}%  "
            f"Collateral={arm_agg.get('avg_collateral_damage', 0):.1f}"
        )

    # --- delta 분석 ---
    b_em = aggregate.get("baseline", {}).get("exact_match", 0)
    bfs_em = aggregate.get("bfs", {}).get("exact_match", 0)
    attr_em = aggregate.get("attribute_aware", {}).get("exact_match", 0)

    logger.info(f"\n  EM 변화:")
    logger.info(f"    Baseline → BFS:          {bfs_em - b_em:+.1f}%")
    logger.info(f"    Baseline → Attr-aware:   {attr_em - b_em:+.1f}%")
    logger.info(f"    BFS → Attr-aware:        {attr_em - bfs_em:+.1f}% (개선)")

    # --- 결과 저장 ---
    output = {
        "config": {
            "sub_dataset": args.sub_dataset,
            "chunk_size": args.chunk_size,
            "max_samples": args.max_samples,
            "max_queries": args.max_queries,
            "propagation_depth": args.propagation_depth,
            "decay_per_hop": args.decay_per_hop,
            "num_hubs": args.num_hubs,
            "named_entity_hubs": args.named_entity_hubs,
            "llm_url": llm_url,
            "llm_model": llm_model,
            "embed_url": embed_url,
            "embed_model": embed_model,
            "mock_embedding": args.mock_embedding,
        },
        "aggregate": aggregate,
        "per_sample": all_results,
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / (
        f"accurate_retrieval_{args.sub_dataset}_{int(time.time())}.json"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"결과 저장: {output_path}")

    return output


def _compute_aggregate(all_results: list[dict]) -> dict:
    """전체 샘플에 대한 집계 메트릭 계산"""
    aggregate = {}

    for arm_name in ["baseline", "bfs", "attribute_aware"]:
        total_em = 0.0
        total_sub_em = 0.0
        total_f1 = 0.0
        total_queries = 0
        total_collateral = 0
        n_samples_with_data = 0

        for result in all_results:
            arm_data = result.get(arm_name, {})
            metrics = arm_data.get("metrics", {})
            if not metrics:
                continue

            n_q = metrics.get("total_queries", 0)
            if n_q == 0:
                continue

            # per-query 합산 (비율이 아닌 raw count 기준)
            total_em += metrics.get("exact_match", 0) * n_q / 100
            total_sub_em += metrics.get("substring_exact_match", 0) * n_q / 100
            total_f1 += metrics.get("f1", 0) * n_q / 100
            total_queries += n_q
            total_collateral += arm_data.get("collateral_damage", 0)
            n_samples_with_data += 1

        if total_queries > 0:
            aggregate[arm_name] = {
                "exact_match": total_em / total_queries * 100,
                "substring_exact_match": total_sub_em / total_queries * 100,
                "f1": total_f1 / total_queries * 100,
                "total_queries": total_queries,
                "n_samples": n_samples_with_data,
                "avg_collateral_damage": (
                    total_collateral / n_samples_with_data
                    if n_samples_with_data > 0
                    else 0
                ),
            }
        else:
            aggregate[arm_name] = {
                "exact_match": 0, "substring_exact_match": 0, "f1": 0,
                "total_queries": 0, "n_samples": 0, "avg_collateral_damage": 0,
            }

    return aggregate


# --- CLI ---

def parse_args():
    parser = argparse.ArgumentParser(
        description="Cross-task 벤치마크: Accurate_Retrieval에서 collateral damage 영향 측정"
    )

    # 데이터 설정
    parser.add_argument(
        "--sub_dataset", type=str, default="eventqa_65536",
        help="Accurate_Retrieval 하위 데이터셋 "
             "(eventqa_65536, eventqa_131072, eventqa_full, longmemeval_s*, ruler_qa*)"
    )
    parser.add_argument(
        "--max_samples", type=int, default=None,
        help="최대 샘플 수 (None=전체)"
    )
    parser.add_argument(
        "--max_queries", type=int, default=None,
        help="샘플당 최대 쿼리 수 (None=전체, 0=LLM query 평가 스킵)"
    )
    parser.add_argument(
        "--chunk_size", type=int, default=4096,
        help="context 청킹 사이즈 (토큰 단위 근사)"
    )

    # Graph propagation 설정
    parser.add_argument(
        "--propagation_depth", type=int, default=2,
        help="전파 깊이"
    )
    parser.add_argument(
        "--decay_per_hop", type=float, default=0.5,
        help="홉당 감쇄율"
    )
    parser.add_argument(
        "--num_hubs", type=int, default=1,
        help="실험할 hub entity 수 (1=기존 단일 hub, >1=multi-hub 평균±std)"
    )
    parser.add_argument(
        "--named_entity_hubs", action="store_true",
        help="headline cross-task claims용: stopword/pronoun/function-word hub를 제외하고 named-entity-like hub만 사용"
    )

    # DooGPU 엔드포인트
    parser.add_argument(
        "--llm_url", type=str, default=None,
        help="LLM API base URL"
    )
    parser.add_argument(
        "--llm_model", type=str, default=None,
        help=f"LLM 모델명 (기본: {DEFAULT_LLM_MODEL})"
    )
    parser.add_argument(
        "--embed_url", type=str, default=None,
        help="Embedding API base URL"
    )
    parser.add_argument(
        "--embed_model", type=str, default=None,
        help=f"Embedding 모델명 (기본: {DEFAULT_EMBED_MODEL})"
    )
    parser.add_argument(
        "--mock_embedding", action="store_true",
        help="임베딩 endpoint 없이 smoke run만 수행한다. 논문 결과로 사용하면 안 됨."
    )
    parser.add_argument(
        "--disable_graph_persist", action="store_true",
        help="benchmark smoke run에서 background graph persistence를 비활성화한다."
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_benchmark(args))
