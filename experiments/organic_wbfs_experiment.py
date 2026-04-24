"""Organic WBFS 실험 — Table 3 (tab:scale)에 WBFS θ=0.3 추가

NR2 요청: "Table 3에 WBFS 넣어야"
기존 Table 3은 BFS와 ATTR-AWARE만 보여줌.
이 스크립트는 organic memorization 중 WBFS θ=0.3를 적용하여
자연적 conflict에서의 damage를 측정한다.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_adapter import MemoryModuleAdapter
from experiments.reviewer3_experiments import (
    DOOGPU_LLM_BASE,
    DOOGPU_EMBED_BASE,
)
from experiments.adversarial_attack import (
    load_data,
    chunk_text,
    snapshot_memory_state,
    identify_hub_entities,
    evaluate_queries,
    DEFAULT_LLM_MODEL,
    DEFAULT_EMBED_MODEL,
)
from benchmark_adapter import DooGPULLMClient
from storage.vector_store import DooGPUEmbeddingProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_organic_wbfs(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 100,
    context_size: str = "6k",
) -> dict:
    """Organic memorization에서 BFS / WBFS θ=0.3 / ATTR-AWARE 비교"""

    strategies = [
        {"name": "bfs_standard", "semantic_filter": False, "attribute_aware": False, "wbfs_params": {}},
        {"name": "weighted_bfs_0.3", "semantic_filter": False, "attribute_aware": False, "wbfs_params": {"edge_weight_threshold": 0.3}},
        {"name": "attr_aware", "semantic_filter": True, "attribute_aware": True, "wbfs_params": {}},
    ]

    results = {}

    for strategy in strategies:
        name = strategy["name"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Organic {context_size} / {name}")
        logger.info(f"{'='*60}")

        adapter = MemoryModuleAdapter(
            graph_propagation=True,  # organic: 처음부터 ON
            semantic_filter=strategy["semantic_filter"],
            attribute_aware=strategy["attribute_aware"],
            propagation_depth=2,
            decay_per_hop=0.5,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
        )

        # WBFS monkeypatch
        wbfs_params = strategy["wbfs_params"]
        if wbfs_params:
            original_propagate = adapter._decay_engine.propagate_invalidation

            async def patched_propagate(_params=wbfs_params, **kwargs):
                kwargs.update(_params)
                return await original_propagate(**kwargs)

            adapter._decay_engine.propagate_invalidation = lambda **kw: patched_propagate(**kw)

        # Memorize (organic conflicts happen naturally)
        chunks = chunk_text(context, chunk_size)
        t0 = time.time()
        for i, chunk in enumerate(chunks):
            await adapter.async_send_message(chunk, memorizing=True)
            if (i + 1) % 10 == 0:
                logger.info(f"  memorize: {i+1}/{len(chunks)} chunks")
        mem_time = time.time() - t0
        logger.info(f"  memorize done: {mem_time:.1f}s")

        # Snapshot
        state = await snapshot_memory_state(adapter)
        hubs = identify_hub_entities(adapter._graph_store, top_k=5)
        top_hub = hubs[0] if hubs else {"entity": "N/A", "degree": 0}

        valid = state["valid"]
        decayed = state["decayed_below_1.0"]
        killed = state["decayed_below_0.1"]
        damage_pct = decayed / max(valid + decayed, 1) * 100
        kill_pct = killed / max(valid + decayed, 1) * 100

        # Evaluate
        metrics = await evaluate_queries(adapter, questions, answers, max_queries)

        results[name] = {
            "strategy": name,
            "context_size": context_size,
            "valid": valid,
            "total_memories": valid + decayed,
            "decayed": decayed,
            "killed": killed,
            "damage_pct": round(damage_pct, 1),
            "kill_pct": round(kill_pct, 1),
            "post_em": round(metrics["exact_match"], 2),
            "post_f1": round(metrics["f1"], 2),
            "top_hub_degree": top_hub["degree"],
            "memorize_time_s": round(mem_time, 1),
        }

        logger.info(
            f"  {name}: valid={valid}, damage={damage_pct:.1f}%, "
            f"kill={kill_pct:.1f}%, EM={metrics['exact_match']:.1f}%"
        )

        await adapter.reset()

    return {"experiment": f"organic_wbfs_{context_size}", "results": results}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context_size", default="6k", choices=["6k", "32k", "64k"])
    parser.add_argument("--max_queries", type=int, default=100)
    parser.add_argument("--llm_url", default=None)
    parser.add_argument("--embed_url", default=None)
    args = parser.parse_args()

    sub_dataset = f"factconsolidation_mh_{args.context_size}"
    samples = load_data(sub_dataset)
    logger.info(f"Loaded {len(samples)} contexts for {sub_dataset}")

    llm_url = args.llm_url or DOOGPU_LLM_BASE
    embed_url = args.embed_url or DOOGPU_EMBED_BASE

    llm_client = DooGPULLMClient(base_url=llm_url, model=DEFAULT_LLM_MODEL)
    embedding_provider = DooGPUEmbeddingProvider(base_url=embed_url, model=DEFAULT_EMBED_MODEL)

    sample = samples[0]
    result = await run_organic_wbfs(
        context=sample["context"],
        questions=sample["questions"],
        answers=sample["answers"],
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        max_queries=args.max_queries,
        context_size=args.context_size,
    )

    # Save
    ts = int(time.time())
    outpath = Path(__file__).parent / "results" / f"organic_wbfs_{args.context_size}_{ts}.json"
    outpath.parent.mkdir(exist_ok=True)
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Results saved to {outpath}")

    # Summary
    print("\n" + "=" * 70)
    print(f"Organic WBFS Experiment — {args.context_size}")
    print("=" * 70)
    for name, r in result["results"].items():
        print(f"  {name:20s}: damage={r['damage_pct']:5.1f}%  kill={r['kill_pct']:5.1f}%  "
              f"EM={r['post_em']:5.1f}%  F1={r['post_f1']:5.1f}%  hub={r['top_hub_degree']}")


if __name__ == "__main__":
    asyncio.run(main())
