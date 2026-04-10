"""Collateral Damage 정량 분석 — BFS vs Attribute-aware Propagation

BFS 기반 전파가 hub entity를 통해 무관한 fact까지 decay시키는
collateral damage 현상을 정량적으로 분석한다.

측정 지표:
  1. 전파된 메모리 수: BFS vs Attribute-aware
  2. Hub entity 분석: degree 분포, 메모리 연결 수
  3. Weight 분포: decay 후 retrieval threshold 미달 메모리 비율
  4. Collateral damage ratio: 무관한 fact가 decay된 비율

사용법:
  python experiments/analyze_collateral_damage.py
  python experiments/analyze_collateral_damage.py --sub_dataset factconsolidation_mh_32k
  python experiments/analyze_collateral_damage.py --sub_dataset factconsolidation_sh_6k --max_contexts 5

출력:
  experiments/results/collateral_damage_{dataset}_{timestamp}.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import copy

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


def load_data(sub_dataset: str, max_contexts: int | None = None):
    """HuggingFace에서 데이터 로드"""
    from datasets import load_dataset

    logger.info(f"데이터 로딩: {sub_dataset}")
    raw = load_dataset("ai-hyz/MemoryAgentBench", split="Conflict_Resolution", revision="main")
    filtered = raw.filter(lambda s: s.get("metadata", {}).get("source", "") == sub_dataset)
    logger.info(f"로드 완료: {len(filtered)} 컨텍스트")

    if max_contexts and len(filtered) > max_contexts:
        filtered = filtered.select(range(max_contexts))

    samples = []
    for item in filtered:
        samples.append({
            "context": item["context"],
            "questions": item["questions"] if isinstance(item["questions"], list) else [item["questions"]],
            "answers": item["answers"] if isinstance(item["answers"], list) else [item["answers"]],
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


async def analyze_single_context(
    context: str,
    ctx_idx: int,
    llm_client: DooGPULLMClient,
    embedding_provider: DooGPUEmbeddingProvider,
    chunk_size: int,
    propagation_depth: int,
    decay_per_hop: float,
) -> dict:
    """단일 context에 대해 BFS vs Attribute-aware 전파의 collateral damage 비교

    Returns:
        dict: 분석 결과
    """
    chunks = chunk_text(context, chunk_size)
    logger.info(f"  Context {ctx_idx}: {len(context)} chars, {len(chunks)} chunks")

    results = {}

    for mode_name, mode_config in [
        ("baseline", {"graph_propagation": False, "attribute_aware": False}),
        ("bfs", {"graph_propagation": True, "attribute_aware": False, "semantic_filter": False}),
        ("attribute_aware", {"graph_propagation": True, "attribute_aware": True, "semantic_filter": True}),
    ]:
        adapter = MemoryModuleAdapter(
            graph_propagation=mode_config["graph_propagation"],
            semantic_filter=mode_config.get("semantic_filter", False),
            attribute_aware=mode_config.get("attribute_aware", True),
            propagation_depth=propagation_depth,
            decay_per_hop=decay_per_hop,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
        )

        # --- Memorize ---
        for chunk in chunks:
            await adapter.async_send_message(chunk, memorizing=True)

        # --- 분석 ---
        store = adapter._metadata_store
        graph = adapter._graph_store

        # 모든 메모리 가져오기 (valid + invalid)
        all_mems = await store.get_all_memories_unfiltered()
        valid_mems = [m for m in all_mems if m.is_valid]
        invalid_mems = [m for m in all_mems if not m.is_valid]

        # decay weight 분포 분석
        weight_distribution = {
            "total": len(all_mems),
            "valid": len(valid_mems),
            "invalid": len(invalid_mems),
            "decayed_below_1": 0,  # weight < 1.0 (decay 적용됨)
            "decayed_below_0.5": 0,
            "decayed_below_0.3": 0,
            "decayed_below_0.1": 0,
            "weights": [],
        }

        for mem in valid_mems:
            w = mem.decay_weight
            weight_distribution["weights"].append(w)
            if w < 1.0:
                weight_distribution["decayed_below_1"] += 1
            if w < 0.5:
                weight_distribution["decayed_below_0.5"] += 1
            if w < 0.3:
                weight_distribution["decayed_below_0.3"] += 1
            if w < 0.1:
                weight_distribution["decayed_below_0.1"] += 1

        # Graph 분석 (BFS와 attribute_aware 모드에서만)
        graph_stats = {}
        if graph and hasattr(graph, 'entity_graph'):
            g = graph.entity_graph
            nodes = list(g.nodes)
            degrees = [g.degree(n) for n in nodes]
            in_degrees = [g.in_degree(n) for n in nodes]

            # Hub entity 분석
            node_mem_counts = {}
            for n in nodes:
                mem_ids = graph.get_memory_ids_for_entity(n)
                node_mem_counts[n] = len(mem_ids)

            # Top-10 hub entities
            top_hubs = sorted(
                [(n, g.degree(n), node_mem_counts.get(n, 0)) for n in nodes],
                key=lambda x: x[1],
                reverse=True,
            )[:10]

            graph_stats = {
                "num_nodes": len(nodes),
                "num_edges": g.number_of_edges(),
                "avg_degree": sum(degrees) / max(len(degrees), 1),
                "max_degree": max(degrees) if degrees else 0,
                "degree_distribution": dict(Counter(degrees)),
                "top_hubs": [
                    {"entity": h[0], "degree": h[1], "memory_count": h[2]}
                    for h in top_hubs
                ],
            }

        # 충돌 감지 통계
        fact_registry = dict(adapter._fact_registry)
        conflict_stats = {
            "total_subject_keys": len(fact_registry),
            "unique_entities": len(set(k.split(":")[0] for k in fact_registry if ":" in k)),
            "unique_attributes": len(set(k.split(":", 1)[1] for k in fact_registry if ":" in k)),
        }

        results[mode_name] = {
            "weight_distribution": {
                k: v for k, v in weight_distribution.items() if k != "weights"
            },
            "weight_values": weight_distribution["weights"],
            "graph_stats": graph_stats,
            "conflict_stats": conflict_stats,
        }

        logger.info(
            f"    [{mode_name}] valid={len(valid_mems)}, invalid={len(invalid_mems)}, "
            f"decayed(<1.0)={weight_distribution['decayed_below_1']}, "
            f"decayed(<0.3)={weight_distribution['decayed_below_0.3']}"
        )

        await adapter.reset()

    # --- 비교 분석 ---
    bfs_decayed = results["bfs"]["weight_distribution"]["decayed_below_1"]
    attr_decayed = results["attribute_aware"]["weight_distribution"]["decayed_below_1"]
    baseline_valid = results["baseline"]["weight_distribution"]["valid"]

    comparison = {
        "baseline_valid_memories": baseline_valid,
        "bfs_decayed_count": bfs_decayed,
        "attr_aware_decayed_count": attr_decayed,
        "reduction": bfs_decayed - attr_decayed,
        "reduction_pct": (
            ((bfs_decayed - attr_decayed) / max(bfs_decayed, 1)) * 100
        ),
        "bfs_collateral_ratio": bfs_decayed / max(baseline_valid, 1) * 100,
        "attr_collateral_ratio": attr_decayed / max(baseline_valid, 1) * 100,
    }

    return {
        "context_idx": ctx_idx,
        "context_chars": len(context),
        "num_chunks": len(chunks),
        "modes": {k: {kk: vv for kk, vv in v.items() if kk != "weight_values"}
                  for k, v in results.items()},
        "weight_values": {k: v["weight_values"] for k, v in results.items()},
        "comparison": comparison,
    }


async def run_analysis(args):
    """전체 분석 실행"""
    samples = load_data(args.sub_dataset, args.max_contexts)

    llm_client = DooGPULLMClient(
        base_url=args.llm_url or DOOGPU_LLM_BASE,
        model="google/gemma-4-31B-it",
    )
    embedding_provider = DooGPUEmbeddingProvider(
        base_url=args.embed_url or DOOGPU_EMBED_BASE,
        model="BAAI/bge-m3",
    )

    all_results = []
    for ctx_idx, sample in enumerate(samples):
        logger.info(f"Context {ctx_idx + 1}/{len(samples)} 분석 중...")
        result = await analyze_single_context(
            context=sample["context"],
            ctx_idx=ctx_idx,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            propagation_depth=args.propagation_depth,
            decay_per_hop=args.decay_per_hop,
        )
        all_results.append(result)

    # --- 집계 ---
    agg = {
        "total_contexts": len(all_results),
        "bfs_total_decayed": sum(r["comparison"]["bfs_decayed_count"] for r in all_results),
        "attr_total_decayed": sum(r["comparison"]["attr_aware_decayed_count"] for r in all_results),
        "total_valid_memories": sum(r["comparison"]["baseline_valid_memories"] for r in all_results),
    }
    agg["total_reduction"] = agg["bfs_total_decayed"] - agg["attr_total_decayed"]
    agg["total_reduction_pct"] = (
        (agg["total_reduction"] / max(agg["bfs_total_decayed"], 1)) * 100
    )
    agg["bfs_collateral_ratio"] = (
        agg["bfs_total_decayed"] / max(agg["total_valid_memories"], 1) * 100
    )
    agg["attr_collateral_ratio"] = (
        agg["attr_total_decayed"] / max(agg["total_valid_memories"], 1) * 100
    )

    # Weight 분포 집계
    all_bfs_weights = []
    all_attr_weights = []
    for r in all_results:
        all_bfs_weights.extend(r["weight_values"].get("bfs", []))
        all_attr_weights.extend(r["weight_values"].get("attribute_aware", []))

    weight_buckets = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    def bucket_dist(weights):
        dist = {f"<{b}": 0 for b in weight_buckets}
        dist["=1.0"] = 0
        for w in weights:
            if w >= 1.0:
                dist["=1.0"] += 1
            else:
                for b in weight_buckets:
                    if w < b:
                        dist[f"<{b}"] += 1
                        break
        return dist

    agg["bfs_weight_distribution"] = bucket_dist(all_bfs_weights)
    agg["attr_weight_distribution"] = bucket_dist(all_attr_weights)

    # Hub entity 집계
    all_hubs = []
    for r in all_results:
        bfs_stats = r["modes"].get("bfs", {}).get("graph_stats", {})
        if "top_hubs" in bfs_stats:
            all_hubs.extend(bfs_stats["top_hubs"])
    # entity별 최대 degree
    hub_max = {}
    for h in all_hubs:
        name = h["entity"]
        if name not in hub_max or h["degree"] > hub_max[name]["degree"]:
            hub_max[name] = h
    agg["top_global_hubs"] = sorted(
        hub_max.values(), key=lambda x: x["degree"], reverse=True
    )[:15]

    # --- 출력 ---
    output = {
        "config": {
            "sub_dataset": args.sub_dataset,
            "chunk_size": args.chunk_size,
            "propagation_depth": args.propagation_depth,
            "decay_per_hop": args.decay_per_hop,
        },
        "aggregate": agg,
        "per_context": [{k: v for k, v in r.items() if k != "weight_values"}
                        for r in all_results],
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"collateral_damage_{args.sub_dataset}_{int(time.time())}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"결과 저장: {out_path}")

    # --- 콘솔 리포트 ---
    print("\n" + "=" * 70)
    print(f"Collateral Damage 분석 리포트: {args.sub_dataset}")
    print("=" * 70)

    print(f"\n[전체 집계]")
    print(f"  총 Context: {agg['total_contexts']}")
    print(f"  총 Valid 메모리: {agg['total_valid_memories']}")
    print(f"  BFS 전파로 decay된 메모리: {agg['bfs_total_decayed']} ({agg['bfs_collateral_ratio']:.1f}%)")
    print(f"  Attribute-aware 전파로 decay된 메모리: {agg['attr_total_decayed']} ({agg['attr_collateral_ratio']:.1f}%)")
    print(f"  감소: {agg['total_reduction']}개 ({agg['total_reduction_pct']:.1f}%)")

    print(f"\n[Weight 분포 비교]")
    print(f"  {'Bucket':<12} {'BFS':>8} {'Attr-aware':>12} {'Δ':>8}")
    for bucket in weight_buckets:
        bk = f"<{bucket}"
        bfs_v = agg["bfs_weight_distribution"].get(bk, 0)
        attr_v = agg["attr_weight_distribution"].get(bk, 0)
        print(f"  {bk:<12} {bfs_v:>8} {attr_v:>12} {attr_v - bfs_v:>+8}")
    bfs_full = agg["bfs_weight_distribution"].get("=1.0", 0)
    attr_full = agg["attr_weight_distribution"].get("=1.0", 0)
    print(f"  {'=1.0':<12} {bfs_full:>8} {attr_full:>12} {attr_full - bfs_full:>+8}")

    print(f"\n[Top Hub Entities]")
    for h in agg["top_global_hubs"][:10]:
        print(f"  {h['entity']:<30} degree={h['degree']:>3} memories={h['memory_count']:>3}")

    print(f"\n[Context별 비교]")
    for r in all_results:
        c = r["comparison"]
        print(
            f"  Ctx {r['context_idx']}: "
            f"valid={c['baseline_valid_memories']}, "
            f"BFS decay={c['bfs_decayed_count']} ({c['bfs_collateral_ratio']:.1f}%), "
            f"Attr decay={c['attr_aware_decayed_count']} ({c['attr_collateral_ratio']:.1f}%), "
            f"감소={c['reduction']}개 ({c['reduction_pct']:.1f}%)"
        )

    print(f"\n결과 저장: {out_path}")
    print("=" * 70)

    return output


def parse_args():
    parser = argparse.ArgumentParser(description="Collateral Damage 정량 분석")
    parser.add_argument("--sub_dataset", type=str, default="factconsolidation_mh_6k")
    parser.add_argument("--chunk_size", type=int, default=4096)
    parser.add_argument("--max_contexts", type=int, default=None)
    parser.add_argument("--propagation_depth", type=int, default=2)
    parser.add_argument("--decay_per_hop", type=float, default=0.5)
    parser.add_argument("--llm_url", type=str, default=None)
    parser.add_argument("--embed_url", type=str, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_analysis(args))
