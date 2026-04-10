"""MemoryAgentBench 벤치마크 러너 — FactConsolidation 태스크

HuggingFace에서 FactConsolidation 데이터를 로드하고,
Baseline(graph_propagation=OFF) vs Experiment(graph_propagation=ON)을
비교하여 Graph-aware Selective Forgetting의 효과를 측정한다.

사용법:
  # 기본 실행 (multi-hop 6K)
  python experiments/benchmark_runner.py

  # single-hop 6K
  python experiments/benchmark_runner.py --sub_dataset factconsolidation_sh_6k

  # 쿼리 수 제한 (빠른 테스트)
  python experiments/benchmark_runner.py --max_queries 10

  # DooGPU 엔드포인트 지정
  python experiments/benchmark_runner.py --llm_url http://10.0.0.1:8080/v1 --embed_url http://10.0.0.1:8081/v1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import string
import sys
import time
from collections import Counter
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_adapter import MemoryModuleAdapter, DooGPULLMClient

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


# --- 평가 유틸 (MemoryAgentBench eval_other_utils.py에서 핵심만 추출) ---

def normalize_answer(text: str) -> str:
    """소문자 + 구두점 제거 + 관사(a/an/the) 제거 + 공백 정규화"""
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
    """여러 정답 중 최대 스코어 반환"""
    if isinstance(ground_truths, str):
        ground_truths = [ground_truths]
    return max(metric_fn(prediction, gt) for gt in ground_truths)


# --- 데이터 로딩 ---

def load_factconsolidation_data(sub_dataset: str, max_samples: int | None = None):
    """HuggingFace에서 FactConsolidation 데이터 로드

    Returns:
        list[dict]: 각 dict는 context, questions, answers 포함
    """
    from datasets import load_dataset

    logger.info(f"HuggingFace에서 {sub_dataset} 로딩 중...")
    raw = load_dataset("ai-hyz/MemoryAgentBench", split="Conflict_Resolution", revision="main")
    filtered = raw.filter(lambda s: s.get("metadata", {}).get("source", "") == sub_dataset)
    logger.info(f"로드 완료: {len(filtered)} 컨텍스트, 소스={sub_dataset}")

    if max_samples and len(filtered) > max_samples:
        filtered = filtered.select(range(max_samples))

    samples = []
    for item in filtered:
        samples.append({
            "context": item["context"],
            "questions": item["questions"] if isinstance(item["questions"], list) else [item["questions"]],
            "answers": item["answers"] if isinstance(item["answers"], list) else [item["answers"]],
        })
    return samples


# --- 청킹 ---

def chunk_text_simple(text: str, chunk_size: int = 4096) -> list[str]:
    """줄 단위 청킹 — tiktoken 의존성 없이 대략적 토큰 수 기반

    FactConsolidation의 fact 리스트는 줄 단위로 깔끔하게 나뉘므로
    문장 토크나이저 대신 줄 기반으로 청킹한다.
    1 토큰 ≈ 4 characters (영어 기준 근사)
    """
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_chars = 0
    char_limit = chunk_size * 4  # 대략적 토큰→문자 변환

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


# --- 벤치마크 실행 ---

async def run_single_arm(
    adapter: MemoryModuleAdapter,
    samples: list[dict],
    chunk_size: int,
    max_queries: int | None,
    arm_name: str,
) -> dict:
    """하나의 실험 팔(Baseline 또는 Experiment) 실행

    Returns:
        dict: metrics, per_query_results, timing 포함
    """
    all_results = []
    total_em = 0.0
    total_sub_em = 0.0
    total_f1 = 0.0
    total_queries = 0
    total_memorize_time = 0.0
    total_query_time = 0.0

    for ctx_idx, sample in enumerate(samples):
        logger.info(f"[{arm_name}] 컨텍스트 {ctx_idx + 1}/{len(samples)} 처리 중...")

        # 어댑터 초기화 (컨텍스트 간 독립)
        await adapter.reset()

        # --- Memorize 단계 ---
        context = sample["context"]
        chunks = chunk_text_simple(context, chunk_size)
        logger.info(f"  청크 {len(chunks)}개로 분할, 총 {len(context)} chars")

        mem_start = time.time()
        for chunk_idx, chunk in enumerate(chunks):
            await adapter.async_send_message(chunk, memorizing=True)
            if (chunk_idx + 1) % 5 == 0:
                logger.info(f"  memorize: {chunk_idx + 1}/{len(chunks)} 청크 완료")
        mem_time = time.time() - mem_start
        total_memorize_time += mem_time
        logger.info(f"  memorize 완료: {mem_time:.1f}s")

        # --- Query 단계 ---
        questions = sample["questions"]
        answers = sample["answers"]
        n_queries = len(questions)
        if max_queries and max_queries < n_queries:
            n_queries = max_queries

        for q_idx in range(n_queries):
            question = questions[q_idx]
            ground_truth = answers[q_idx]
            if isinstance(ground_truth, list):
                gt_list = ground_truth
            else:
                gt_list = [ground_truth]

            q_start = time.time()
            result = await adapter.async_send_message(
                question, memorizing=False,
                query_id=q_idx, context_id=ctx_idx,
            )
            q_time = time.time() - q_start
            total_query_time += q_time

            # 답변 추출
            if isinstance(result, dict):
                output = result.get("output", "")
            else:
                output = str(result)

            # 메트릭 계산
            em = max_over_ground_truths(exact_match, output, gt_list)
            sub = max_over_ground_truths(substring_exact_match, output, gt_list)
            f1 = max_over_ground_truths(f1_score, output, gt_list)

            total_em += float(em)
            total_sub_em += float(sub)
            total_f1 += f1
            total_queries += 1

            all_results.append({
                "context_id": ctx_idx,
                "query_id": q_idx,
                "question": question,
                "ground_truth": gt_list,
                "prediction": output,
                "exact_match": float(em),
                "substring_exact_match": float(sub),
                "f1": f1,
                "query_time": q_time,
            })

            if (q_idx + 1) % 10 == 0:
                running_em = total_em / total_queries * 100
                running_f1 = total_f1 / total_queries * 100
                logger.info(
                    f"  [{arm_name}] query {q_idx + 1}/{n_queries}: "
                    f"EM={running_em:.1f}%, F1={running_f1:.1f}%"
                )

    # 최종 집계
    metrics = {}
    if total_queries > 0:
        metrics = {
            "exact_match": total_em / total_queries * 100,
            "substring_exact_match": total_sub_em / total_queries * 100,
            "f1": total_f1 / total_queries * 100,
            "total_queries": total_queries,
            "avg_query_time": total_query_time / total_queries,
            "total_memorize_time": total_memorize_time,
            "total_query_time": total_query_time,
        }

    return {
        "arm": arm_name,
        "metrics": metrics,
        "results": all_results,
    }


async def run_benchmark(args):
    """Baseline vs Experiment 비교 벤치마크 실행"""

    # --- 데이터 로드 ---
    samples = load_factconsolidation_data(args.sub_dataset)
    logger.info(f"데이터 로드 완료: {len(samples)} 컨텍스트")

    for i, s in enumerate(samples):
        logger.info(f"  컨텍스트 {i}: {len(s['context'])} chars, {len(s['questions'])} 질문")

    # --- LLM/Embedding 클라이언트 ---
    llm_url = args.llm_url or DOOGPU_LLM_BASE
    llm_model = args.llm_model or DEFAULT_LLM_MODEL
    embed_url = args.embed_url or DOOGPU_EMBED_BASE
    embed_model = args.embed_model or DEFAULT_EMBED_MODEL

    logger.info(f"LLM: {llm_url} / {llm_model}")
    logger.info(f"Embedding: {embed_url} / {embed_model}")

    llm_client = DooGPULLMClient(base_url=llm_url, model=llm_model)

    from storage.vector_store import DooGPUEmbeddingProvider
    embedding_provider = DooGPUEmbeddingProvider(
        base_url=embed_url, model=embed_model
    )

    # --- Baseline 실행 (graph_propagation=OFF) ---
    logger.info("=" * 60)
    logger.info("BASELINE 실행 (graph_propagation=OFF)")
    logger.info("=" * 60)

    baseline_adapter = MemoryModuleAdapter(
        graph_propagation=False,
        semantic_filter=False,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )
    baseline_result = await run_single_arm(
        baseline_adapter, samples, args.chunk_size, args.max_queries, "Baseline"
    )

    # --- Experiment 실행 (graph_propagation=ON) ---
    logger.info("=" * 60)
    logger.info("EXPERIMENT 실행 (graph_propagation=ON, semantic_filter=ON)")
    logger.info("=" * 60)

    experiment_adapter = MemoryModuleAdapter(
        graph_propagation=True,
        semantic_filter=True,
        propagation_depth=args.propagation_depth,
        decay_per_hop=args.decay_per_hop,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )
    experiment_result = await run_single_arm(
        experiment_adapter, samples, args.chunk_size, args.max_queries, "Experiment"
    )

    # --- 결과 비교 ---
    logger.info("=" * 60)
    logger.info("결과 비교")
    logger.info("=" * 60)

    b_metrics = baseline_result["metrics"]
    e_metrics = experiment_result["metrics"]

    comparison = {}
    for key in ["exact_match", "substring_exact_match", "f1"]:
        b_val = b_metrics.get(key, 0)
        e_val = e_metrics.get(key, 0)
        delta = e_val - b_val
        comparison[key] = {"baseline": b_val, "experiment": e_val, "delta": delta}
        logger.info(f"  {key}: Baseline={b_val:.2f}%, Experiment={e_val:.2f}%, Δ={delta:+.2f}%")

    logger.info(f"  Memorize time: Baseline={b_metrics.get('total_memorize_time', 0):.1f}s, "
                f"Experiment={e_metrics.get('total_memorize_time', 0):.1f}s")
    logger.info(f"  Query time (avg): Baseline={b_metrics.get('avg_query_time', 0):.3f}s, "
                f"Experiment={e_metrics.get('avg_query_time', 0):.3f}s")

    # --- 결과 저장 ---
    output = {
        "config": {
            "sub_dataset": args.sub_dataset,
            "chunk_size": args.chunk_size,
            "max_queries": args.max_queries,
            "propagation_depth": args.propagation_depth,
            "decay_per_hop": args.decay_per_hop,
            "llm_url": args.llm_url,
            "llm_model": args.llm_model,
            "embed_url": args.embed_url,
            "embed_model": args.embed_model,
        },
        "comparison": comparison,
        "baseline": baseline_result,
        "experiment": experiment_result,
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / f"benchmark_{args.sub_dataset}_{int(time.time())}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"결과 저장: {output_path}")

    return output


def parse_args():
    parser = argparse.ArgumentParser(description="MemoryAgentBench 벤치마크 러너")

    # 데이터 설정
    parser.add_argument("--sub_dataset", type=str, default="factconsolidation_mh_6k",
                        help="FactConsolidation 하위 데이터셋 (sh/mh × 6k/32k/64k/262k)")
    parser.add_argument("--chunk_size", type=int, default=4096,
                        help="context 청킹 사이즈 (토큰 단위 근사)")
    parser.add_argument("--max_queries", type=int, default=None,
                        help="최대 쿼리 수 제한 (None=전체)")

    # Graph propagation 설정
    parser.add_argument("--propagation_depth", type=int, default=2,
                        help="전파 깊이")
    parser.add_argument("--decay_per_hop", type=float, default=0.5,
                        help="홉당 감쇄율")

    # DooGPU 엔드포인트
    parser.add_argument("--llm_url", type=str, default=None,
                        help="LLM API base URL (기본: config.py의 llm_base_url)")
    parser.add_argument("--llm_model", type=str, default=None,
                        help="LLM 모델명 (기본: config.py의 llm_model)")
    parser.add_argument("--embed_url", type=str, default=None,
                        help="Embedding API base URL (기본: config.py의 embedding_base_url)")
    parser.add_argument("--embed_model", type=str, default=None,
                        help="Embedding 모델명 (기본: config.py의 embedding_model)")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_benchmark(args))
