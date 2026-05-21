"""Support-retrieval diagnostics for propagation damage.

This diagnostic intentionally avoids LLM generation.  It asks whether memories
containing an answer string remain in a decay-weighted vector-retrieval top-k
set after a propagation event.  That separates retrieval-side harm from prompt
or decoder failures in LongMemEval.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from statistics import mean, pstdev

from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_adapter import DooGPULLMClient, MemoryModuleAdapter
from experiments.benchmark_accurate_retrieval import (
    DOOGPU_EMBED_BASE,
    DOOGPU_LLM_BASE,
    DEFAULT_EMBED_MODEL,
    chunk_text_simple,
    find_fact_for_entity,
    find_high_degree_entities,
    trigger_propagation,
)
from experiments.preprint_hubs import select_actionable_hubs
from experiments.structured_graph_gate import build_structured_context
from storage.vector_store import DooGPUEmbeddingProvider

logger = logging.getLogger(__name__)

CURRENT_WORKLOAD_LLM_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-831a629b-4336-480d-8e5e-13f45a796ae6/reserved3/v1"
)
CURRENT_WORKLOAD_EMBED_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-831a629b-4336-480d-8e5e-13f45a796ae6/reserved9/v1"
)
CURRENT_LLM_MODEL = "google/gemma-4-26B-A4B-it"


def _ground_truths(answer: object) -> list[str]:
    if isinstance(answer, list):
        return [str(a) for a in answer]
    return [str(answer)]


def _contains_answer(text: str, answers: list[str]) -> bool:
    lowered = text.lower()
    return any(ans.lower() in lowered for ans in answers if ans)


async def _decay_weighted_vector_hits(
    adapter: MemoryModuleAdapter,
    questions: list[str],
    answers: list[object],
    top_k_values: list[int],
    vector_pool: int,
    max_queries: int | None,
) -> dict:
    n_queries = len(questions)
    if max_queries is not None:
        n_queries = min(n_queries, max_queries)

    hits = {k: 0 for k in top_k_values}
    support_ranks = []
    per_query = []
    max_k = max(max(top_k_values), vector_pool)

    for q_idx in range(n_queries):
        question = questions[q_idx]
        answer_list = _ground_truths(answers[q_idx])
        vector_rows = await adapter._vector_store.search(
            question, user_id="benchmark", top_k=max_k
        )
        memory_ids = [mid for mid, _score in vector_rows]
        memories = await adapter._metadata_store.get_memories_by_ids(memory_ids)
        memory_map = {m.id: m for m in memories}

        ranked = []
        for memory_id, vector_score in vector_rows:
            memory = memory_map.get(memory_id)
            if not memory or not memory.is_valid:
                continue
            final_score = float(vector_score) * float(memory.decay_weight)
            ranked.append((memory_id, final_score, float(vector_score), memory))
        ranked.sort(key=lambda row: row[1], reverse=True)

        answer_rank = None
        answer_weight = None
        for rank, (_mid, final_score, _vector_score, memory) in enumerate(ranked, 1):
            if _contains_answer(memory.content, answer_list):
                answer_rank = rank
                answer_weight = memory.decay_weight
                break

        for k in top_k_values:
            if answer_rank is not None and answer_rank <= k:
                hits[k] += 1
        if answer_rank is not None:
            support_ranks.append(answer_rank)

        per_query.append({
            "query_id": q_idx,
            "question": question,
            "answers": answer_list,
            "answer_support_rank": answer_rank,
            "answer_support_weight": answer_weight,
            "top1": ranked[0][3].content if ranked else None,
        })

    metrics = {
        "total_queries": n_queries,
        "answer_support_found": len(support_ranks),
        "mean_answer_support_rank": round(mean(support_ranks), 2)
        if support_ranks else None,
    }
    for k in top_k_values:
        metrics[f"support_hit_at_{k}"] = round(hits[k] / n_queries * 100, 2) if n_queries else 0.0

    return {"metrics": metrics, "per_query": per_query}


async def _build_adapter(
    context: str,
    args: argparse.Namespace,
    llm_client: DooGPULLMClient,
    embedding_provider: DooGPUEmbeddingProvider,
) -> MemoryModuleAdapter:
    adapter = MemoryModuleAdapter(
        graph_propagation=True,
        semantic_filter=True,
        attribute_aware=True,
        propagation_depth=args.propagation_depth,
        decay_per_hop=args.decay_per_hop,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )
    for chunk in chunk_text_simple(context, args.chunk_size):
        await adapter.async_send_message(chunk, memorizing=True)
    return adapter


async def run(args: argparse.Namespace) -> dict:
    llm_url = args.llm_url or CURRENT_WORKLOAD_LLM_BASE or DOOGPU_LLM_BASE
    embed_url = args.embed_url or CURRENT_WORKLOAD_EMBED_BASE or DOOGPU_EMBED_BASE
    llm_model = args.llm_model or CURRENT_LLM_MODEL
    embed_model = args.embed_model or DEFAULT_EMBED_MODEL

    raw = load_dataset(
        "ai-hyz/MemoryAgentBench", split="Accurate_Retrieval", revision="main"
    )
    filtered = raw.filter(
        lambda sample: sample.get("metadata", {}).get("source", "") == args.sub_dataset
    )
    if args.max_samples is not None:
        filtered = filtered.select(range(min(args.max_samples, len(filtered))))

    llm_client = DooGPULLMClient(base_url=llm_url, model=llm_model)
    embedding_provider = DooGPUEmbeddingProvider(base_url=embed_url, model=embed_model)

    top_k_values = [int(v) for v in args.top_k.split(",") if v.strip()]
    per_sample = []
    for sample_idx, item in enumerate(filtered):
        context = build_structured_context(item, args.structured_context_mode)
        questions = item["questions"] if isinstance(item["questions"], list) else [item["questions"]]
        answers = item["answers"] if isinstance(item["answers"], list) else [item["answers"]]

        logger.info("Sample %s: building memory from %s chars", sample_idx, len(context))
        adapter = await _build_adapter(context, args, llm_client, embedding_provider)

        raw_hubs = find_high_degree_entities(adapter, top_k=args.num_hubs * 10)
        hub_dicts = [{"entity": entity, "degree": degree} for entity, degree in raw_hubs]
        hubs = select_actionable_hubs(
            hub_dicts,
            top_k=args.num_hubs,
            has_trigger_fact=lambda entity: find_fact_for_entity(adapter, entity) is not None,
        )
        hubs = [{"entity": str(h["entity"]), "degree": int(h["degree"])} for h in hubs]
        logger.info("Sample %s hubs: %s", sample_idx, hubs)

        baseline = await _decay_weighted_vector_hits(
            adapter, questions, answers, top_k_values, args.vector_pool, args.max_queries
        )

        snapshot = await adapter._metadata_store.snapshot_weights()
        hub_runs = []
        for hub in hubs:
            row = {"hub": hub}
            for mode in ["bfs", "attribute_aware"]:
                await adapter._metadata_store.restore_weights(snapshot)
                propagation = await trigger_propagation(adapter, hub["entity"], mode)
                support = await _decay_weighted_vector_hits(
                    adapter, questions, answers, top_k_values, args.vector_pool, args.max_queries
                )
                row[mode] = {
                    "propagation": {
                        "affected_count": propagation.get("affected_count", 0),
                        "trigger_subject_key": propagation.get("trigger_subject_key"),
                    },
                    "support": support["metrics"],
                }
            await adapter._metadata_store.restore_weights(snapshot)
            hub_runs.append(row)

        per_sample.append({
            "sample_idx": sample_idx,
            "context_chars": len(context),
            "num_questions": len(questions),
            "hubs": hubs,
            "baseline": baseline["metrics"],
            "hub_runs": hub_runs,
        })
        await adapter.reset()

    summary = _summarize(per_sample, top_k_values)
    return {
        "config": {
            "sub_dataset": args.sub_dataset,
            "max_samples": args.max_samples,
            "max_queries": args.max_queries,
            "structured_context_mode": args.structured_context_mode,
            "num_hubs": args.num_hubs,
            "top_k": top_k_values,
            "vector_pool": args.vector_pool,
            "propagation_depth": args.propagation_depth,
            "decay_per_hop": args.decay_per_hop,
            "llm_model": llm_model,
            "embed_model": embed_model,
        },
        "summary": summary,
        "per_sample": per_sample,
    }


def _summarize(per_sample: list[dict], top_k_values: list[int]) -> dict:
    rows = []
    for sample in per_sample:
        for run in sample["hub_runs"]:
            row = {"sample_idx": sample["sample_idx"], "hub": run["hub"]["entity"]}
            for mode in ["bfs", "attribute_aware"]:
                row[f"{mode}_affected"] = run[mode]["propagation"]["affected_count"]
                for k in top_k_values:
                    metric = f"support_hit_at_{k}"
                    row[f"{mode}_{metric}"] = run[mode]["support"][metric]
                    row[f"baseline_{metric}"] = sample["baseline"][metric]
            rows.append(row)

    summary: dict[str, object] = {"num_hub_runs": len(rows)}
    for k in top_k_values:
        metric = f"support_hit_at_{k}"
        base_vals = [row[f"baseline_{metric}"] for row in rows]
        summary[f"baseline_{metric}_mean"] = round(mean(base_vals), 2) if base_vals else 0.0
        for mode in ["bfs", "attribute_aware"]:
            vals = [row[f"{mode}_{metric}"] for row in rows]
            deltas = [row[f"{mode}_{metric}"] - row[f"baseline_{metric}"] for row in rows]
            summary[f"{mode}_{metric}_mean"] = round(mean(vals), 2) if vals else 0.0
            summary[f"{mode}_{metric}_delta_mean"] = round(mean(deltas), 2) if deltas else 0.0
            summary[f"{mode}_{metric}_delta_std"] = round(pstdev(deltas), 2) if len(deltas) > 1 else 0.0
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sub_dataset", default="longmemeval_s*")
    parser.add_argument("--max_samples", type=int, default=1)
    parser.add_argument("--max_queries", type=int, default=20)
    parser.add_argument("--structured_context_mode", default="answer_session_user_turns")
    parser.add_argument("--num_hubs", type=int, default=2)
    parser.add_argument("--top_k", default="5,20")
    parser.add_argument("--vector_pool", type=int, default=100)
    parser.add_argument("--chunk_size", type=int, default=4096)
    parser.add_argument("--propagation_depth", type=int, default=2)
    parser.add_argument("--decay_per_hop", type=float, default=0.5)
    parser.add_argument("--llm_url", default=None)
    parser.add_argument("--llm_model", default=None)
    parser.add_argument("--embed_url", default=None)
    parser.add_argument("--embed_model", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO,
    )
    args = parse_args()
    result = asyncio.run(run(args))
    output_path = args.output
    if output_path is None:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        output_path = str(results_dir / f"support_retrieval_{int(time.time())}.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    logger.info("Saved %s", output_path)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
