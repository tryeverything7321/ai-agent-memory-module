"""Reviewer 3 Response 실험 — Typed-relation graph, Organic residual, WBFS at scale

Reviewer 3의 핵심 지적사항에 대한 실증 데이터 수집:

  Q1: Typed-relation graph에서 BFS damage 측정 (co-occurrence clique과 비교)
  W5: Organic (비적대적) ATTR-AWARE 잔여 damage 전수 분류
  Q2: Weighted BFS θ=0.3 at 32K/64K (ATTR-AWARE와 scale 비교)

사용법:
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/reviewer3_experiments.py \
    --experiments typed_relation organic_residual wbfs_at_scale \
    --context_size 6k
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
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
from residual_analysis import (
    _find_entity_for_memory,
    _find_subject_key_for_memory,
    _trace_propagation_path,
    _classify_damage,
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


# ============================================================
# Q1: Typed-relation graph vs Co-occurrence graph
# ============================================================

async def run_typed_relation_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """Typed-relation graph에서 BFS damage를 co-occurrence graph과 비교

    Reviewer 3 Q1: "What is the damage rate if BFS is run on the
    typed-relation subgraph rather than the full co-occurrence clique graph?"
    """
    results = {}

    for graph_mode in ["cooccurrence", "typed_relation"]:
        logger.info(f"\n{'='*60}")
        logger.info(f"Q1: Graph mode = {graph_mode}")
        logger.info(f"{'='*60}")

        # --- Phase 1: Memorize (propagation OFF) ---
        adapter = MemoryModuleAdapter(
            graph_propagation=False,
            semantic_filter=False,
            attribute_aware=False,
            propagation_depth=2,
            decay_per_hop=0.5,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
            graph_mode=graph_mode,
        )

        chunks = chunk_text(context, chunk_size)
        for chunk in chunks:
            await adapter.async_send_message(chunk, memorizing=True)

        pre_state = await snapshot_memory_state(adapter)
        hubs = identify_hub_entities(adapter._graph_store, top_k=5)
        top_hub = hubs[0] if hubs else {"entity": "N/A", "degree": 0}

        graph_nodes = len(adapter._graph_store.entity_graph.nodes())
        graph_edges = len(adapter._graph_store.entity_graph.edges())

        # degree 분포 통계
        degrees = [d for _, d in adapter._graph_store.entity_graph.degree()]
        avg_degree = statistics.mean(degrees) if degrees else 0
        max_degree = max(degrees) if degrees else 0

        logger.info(f"  Graph: {graph_nodes} nodes, {graph_edges} edges")
        logger.info(f"  Avg degree: {avg_degree:.2f}, Max degree: {max_degree}")
        logger.info(f"  Pre-attack valid: {pre_state['valid']} memories")

        # --- Phase 2: BFS 5-fact white-box attack ---
        adapter.graph_propagation = True
        # BFS mode (not attr_aware)
        adapter.attribute_aware = False

        high_impact = find_high_impact_keys(
            adapter._fact_registry, adapter._graph_store, top_k=10
        )
        matching_keys = [k for k, _ in high_impact]
        max_serial = max(adapter._serial_registry.keys()) if adapter._serial_registry else 0
        attack_facts = generate_attack_facts_from_registry(
            matching_keys, 5, max_serial
        )

        for fact_line, target_key in attack_facts:
            logger.info(f"  Attack: {fact_line}")
            await adapter.async_send_message(fact_line, memorizing=True)

        post_state = await snapshot_memory_state(adapter)
        newly_decayed = post_state["decayed_below_1.0"] - pre_state["decayed_below_1.0"]
        newly_killed = post_state["decayed_below_0.1"] - pre_state["decayed_below_0.1"]
        damage_ratio = newly_decayed / max(pre_state["valid"], 1) * 100
        kill_ratio = newly_killed / max(pre_state["valid"], 1) * 100

        post_metrics = await evaluate_queries(adapter, questions, answers, max_queries)

        results[graph_mode] = {
            "graph_mode": graph_mode,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "avg_degree": round(avg_degree, 2),
            "max_degree": max_degree,
            "pre_valid": pre_state["valid"],
            "newly_decayed": newly_decayed,
            "newly_killed": newly_killed,
            "damage_ratio_pct": round(damage_ratio, 2),
            "kill_ratio_pct": round(kill_ratio, 2),
            "post_em": round(post_metrics["exact_match"], 2),
            "post_f1": round(post_metrics["f1"], 2),
            "top_hub": top_hub["entity"],
            "top_hub_degree": top_hub["degree"],
            "top_5_hubs": [
                {"entity": h["entity"], "degree": h["degree"]}
                for h in hubs[:5]
            ],
        }

        logger.info(f"  BFS damage: {damage_ratio:.1f}%, kill: {kill_ratio:.1f}%")
        await adapter.reset()

    # --- 비교 요약 ---
    co = results["cooccurrence"]
    tr = results["typed_relation"]
    results["comparison"] = {
        "edge_reduction_pct": round(
            (1 - tr["graph_edges"] / max(co["graph_edges"], 1)) * 100, 1
        ),
        "damage_reduction_pct": round(
            (1 - tr["damage_ratio_pct"] / max(co["damage_ratio_pct"], 0.01)) * 100, 1
        ),
        "max_degree_reduction_pct": round(
            (1 - tr["max_degree"] / max(co["max_degree"], 1)) * 100, 1
        ),
    }

    return {"experiment": "typed_relation_comparison", "results": results}


# ============================================================
# W5: Organic Residual Classification
# ============================================================

async def run_organic_residual_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """Organic (비적대적) ATTR-AWARE 잔여 damage 전수 분류

    Reviewer 3 W5: "At 6K, ATTR-AWARE's 14.8% damage rate corresponds
    to ~51 memories. Inspecting one out of 51 is not an analysis."

    organic memorization 중 발생하는 자연적 conflict에 의한
    ATTR-AWARE propagation damage를 전수 분류한다.
    """
    logger.info(f"\n{'='*60}")
    logger.info("W5: Organic Residual Classification")
    logger.info(f"{'='*60}")

    # --- Phase 1: Memorize with ATTR-AWARE ON + conflict logging ---
    adapter = MemoryModuleAdapter(
        graph_propagation=True,
        semantic_filter=True,
        attribute_aware=True,
        propagation_depth=2,
        decay_per_hop=0.5,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
        db_path=":memory:",
    )

    # conflict event 로그 수집
    conflict_log: list[dict] = []
    original_send = adapter.async_send_message

    # fact_registry 스냅샷을 매 conflict 전에 저장하기 위해
    # memorize 과정에서 conflict 발생 시 로깅
    _original_propagate = adapter._decay_engine.propagate_invalidation

    async def _logging_propagate(**kwargs):
        """propagation 호출을 로깅하는 wrapper"""
        mem_id = kwargs.get("invalidated_memory_id")
        subject_key = kwargs.get("subject_key")

        # propagation 전 상태
        old_mem = None
        if mem_id:
            old_mem = await adapter._metadata_store.get_memory(mem_id)

        # 원본 propagation 실행
        affected = await _original_propagate(**kwargs)

        # 로깅
        old_content = old_mem.content if old_mem else "N/A"
        object_entities = []
        if mem_id and subject_key and ":" in subject_key:
            subj_ent = subject_key.split(":")[0]
            for node_id in adapter._graph_store.entity_graph.nodes:
                mem_ids = adapter._graph_store.get_memory_ids_for_entity(node_id)
                if mem_id in mem_ids and node_id.lower() != subj_ent.lower():
                    object_entities.append(node_id)

        conflict_log.append({
            "invalidated_memory_id": mem_id,
            "subject_key": subject_key,
            "old_content": old_content,
            "object_entities": object_entities,
            "affected_ids": affected,
        })

        return affected

    adapter._decay_engine.propagate_invalidation = lambda **kw: _logging_propagate(**kw)

    chunks = chunk_text(context, chunk_size)
    for chunk in chunks:
        await adapter.async_send_message(chunk, memorizing=True)

    logger.info(f"  Total conflict events: {len(conflict_log)}")
    logger.info(f"  Total propagation-affected memories: {sum(len(c['affected_ids']) for c in conflict_log)}")

    # --- Phase 2: 전체 damaged memory 식별 ---
    all_mems = await adapter._metadata_store.get_all_memories_unfiltered()
    valid_mems = [m for m in all_mems if m.is_valid]
    damaged_mems = [m for m in valid_mems if m.decay_weight < 1.0]

    logger.info(f"  Valid memories: {len(valid_mems)}")
    logger.info(f"  Damaged (w < 1.0): {len(damaged_mems)} ({len(damaged_mems)/max(len(valid_mems),1)*100:.1f}%)")

    # --- Phase 3: 각 damaged memory 분류 ---
    fact_registry_snapshot = dict(adapter._fact_registry)
    classified_results: list[dict] = []

    for dmg_mem in damaged_mems:
        mem_entities = _find_entity_for_memory(adapter._graph_store, dmg_mem.id)
        mem_subject_key = _find_subject_key_for_memory(fact_registry_snapshot, dmg_mem.id)

        # 어떤 conflict event가 이 damage를 야기했는지 찾기
        triggering_conflict = None
        for conflict in conflict_log:
            if dmg_mem.id in conflict["affected_ids"]:
                triggering_conflict = conflict
                break

        # conflict를 못 찾으면 entity overlap으로 추정
        if triggering_conflict is None:
            for conflict in conflict_log:
                if conflict["affected_ids"]:
                    atk_objects = set(conflict.get("object_entities", []))
                    if atk_objects & set(mem_entities):
                        triggering_conflict = conflict
                        break

        # 분류
        object_entities = set(triggering_conflict.get("object_entities", [])) if triggering_conflict else set()
        attack_subject_key = triggering_conflict.get("subject_key", "") if triggering_conflict else ""

        # propagation 경로 추적
        propagation_path = []
        if triggering_conflict:
            source_entities = set(triggering_conflict.get("object_entities", []))
            target_entities = set(mem_entities)
            propagation_path = _trace_propagation_path(
                adapter._graph_store, source_entities, target_entities, max_depth=3
            )

        classification = _classify_damage(
            damaged_mem_content=dmg_mem.content,
            damaged_mem_id=dmg_mem.id,
            damaged_mem_entities=mem_entities,
            damaged_mem_subject_key=mem_subject_key,
            attack_subject_key=attack_subject_key,
            attack_fact_text=triggering_conflict.get("old_content", "") if triggering_conflict else "",
            object_entities=object_entities,
            propagation_path=propagation_path,
        )

        classified_results.append({
            "memory_id": dmg_mem.id,
            "memory_content": dmg_mem.content,
            "memory_subject_key": mem_subject_key,
            "memory_entities": mem_entities[:5],
            "current_weight": round(dmg_mem.decay_weight, 6),
            "weight_drop": round(1.0 - dmg_mem.decay_weight, 6),
            "triggering_conflict": {
                "subject_key": attack_subject_key,
                "old_content": triggering_conflict["old_content"][:100] if triggering_conflict else "N/A",
                "object_entities": list(object_entities)[:5],
            } if triggering_conflict else None,
            "propagation_path": propagation_path,
            "classification": classification["classification"],
            "classification_reason": classification["reason"],
            "classification_details": {
                "subject_matches_object": classification["subject_matches_object"],
                "content_mentions_object": classification["content_mentions_object"],
                "same_entity_different_attr": classification["same_entity_different_attr"],
            },
        })

    # --- Phase 4: 집계 ---
    total = len(classified_results)
    legitimate = sum(1 for r in classified_results if r["classification"] == "legitimate_cascade")
    borderline = sum(1 for r in classified_results if r["classification"] == "borderline")
    false_pos = sum(1 for r in classified_results if r["classification"] == "false_positive")

    logger.info(f"\n  Classification Summary:")
    logger.info(f"    Legitimate cascade: {legitimate} ({legitimate/max(total,1)*100:.1f}%)")
    logger.info(f"    Borderline:         {borderline} ({borderline/max(total,1)*100:.1f}%)")
    logger.info(f"    False positive:     {false_pos} ({false_pos/max(total,1)*100:.1f}%)")

    # weight 분포
    weights = [m.decay_weight for m in damaged_mems]
    weight_dist = {
        "w<0.1": sum(1 for w in weights if w < 0.1),
        "0.1≤w<0.3": sum(1 for w in weights if 0.1 <= w < 0.3),
        "0.3≤w<0.5": sum(1 for w in weights if 0.3 <= w < 0.5),
        "0.5≤w<0.7": sum(1 for w in weights if 0.5 <= w < 0.7),
        "0.7≤w<0.9": sum(1 for w in weights if 0.7 <= w < 0.9),
        "0.9≤w<1.0": sum(1 for w in weights if 0.9 <= w < 1.0),
    }

    await adapter.reset()

    return {
        "experiment": "organic_residual_classification",
        "config": {
            "context_size": "6k",
            "propagation_mode": "attr_aware",
            "propagation_depth": 2,
            "decay_per_hop": 0.5,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summary": {
            "total_valid_memories": len(valid_mems),
            "total_damaged": total,
            "damage_ratio_pct": round(total / max(len(valid_mems), 1) * 100, 2),
            "total_conflict_events": len(conflict_log),
            "legitimate_cascade": legitimate,
            "legitimate_cascade_pct": round(legitimate / max(total, 1) * 100, 1),
            "borderline": borderline,
            "borderline_pct": round(borderline / max(total, 1) * 100, 1),
            "false_positive": false_pos,
            "false_positive_pct": round(false_pos / max(total, 1) * 100, 1),
            "weight_distribution": weight_dist,
            "avg_damaged_weight": round(statistics.mean(weights), 4) if weights else 0,
            "min_damaged_weight": round(min(weights), 4) if weights else 0,
        },
        "classified_damages": classified_results,
    }


# ============================================================
# Q2: Weighted BFS at scale (32K / 64K)
# ============================================================

async def run_wbfs_at_scale_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
    context_size: str = "32k",
) -> dict:
    """Weighted BFS θ=0.3 vs ATTR-AWARE at 32K/64K scale

    Reviewer 3 Q2/W3: "Can you provide Weighted BFS (θ=0.3) results
    at 32K and 64K? If damage remains at ~1.5%, the practical case
    for ATTR-AWARE over simpler threshold methods weakens considerably."
    """
    strategies = [
        {"name": "bfs_standard", "params": {}},
        {"name": "weighted_bfs_0.3", "params": {"edge_weight_threshold": 0.3}},
        {"name": "attr_aware", "mode": "attr_aware"},
    ]

    results = {}

    for strategy in strategies:
        name = strategy["name"]
        is_attr = strategy.get("mode") == "attr_aware"
        params = strategy.get("params", {})

        logger.info(f"\n--- {context_size} / {name} ---")

        adapter = MemoryModuleAdapter(
            graph_propagation=False,
            semantic_filter=is_attr,
            attribute_aware=is_attr,
            propagation_depth=2,
            decay_per_hop=0.5,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
        )

        # Phase 1: Memorize
        chunks = chunk_text(context, chunk_size)
        for chunk in chunks:
            await adapter.async_send_message(chunk, memorizing=True)

        pre_state = await snapshot_memory_state(adapter)
        hubs = identify_hub_entities(adapter._graph_store, top_k=5)
        top_hub = hubs[0] if hubs else {"entity": "N/A", "degree": 0}
        graph_nodes = len(adapter._graph_store.entity_graph.nodes())
        graph_edges = len(adapter._graph_store.entity_graph.edges())

        # Phase 2: Attack
        adapter.graph_propagation = True

        if not is_attr:
            # BFS mode with strategy params
            original_propagate = adapter._decay_engine.propagate_invalidation

            async def patched_propagate(_params=params, **kwargs):
                kwargs.update(_params)
                return await original_propagate(**kwargs)

            adapter._decay_engine.propagate_invalidation = lambda **kw: patched_propagate(**kw)

        high_impact = find_high_impact_keys(
            adapter._fact_registry, adapter._graph_store, top_k=10
        )
        matching_keys = [k for k, _ in high_impact]
        max_serial = max(adapter._serial_registry.keys()) if adapter._serial_registry else 0
        attack_facts = generate_attack_facts_from_registry(
            matching_keys, 5, max_serial
        )

        for fact_line, target_key in attack_facts:
            await adapter.async_send_message(fact_line, memorizing=True)

        # Phase 3: Measure
        post_state = await snapshot_memory_state(adapter)
        newly_decayed = post_state["decayed_below_1.0"] - pre_state["decayed_below_1.0"]
        newly_killed = post_state["decayed_below_0.1"] - pre_state["decayed_below_0.1"]
        damage_ratio = newly_decayed / max(pre_state["valid"], 1) * 100
        kill_ratio = newly_killed / max(pre_state["valid"], 1) * 100

        post_metrics = await evaluate_queries(adapter, questions, answers, max_queries)

        results[name] = {
            "strategy": name,
            "context_size": context_size,
            "pre_valid": pre_state["valid"],
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "newly_decayed": newly_decayed,
            "newly_killed": newly_killed,
            "damage_ratio_pct": round(damage_ratio, 2),
            "kill_ratio_pct": round(kill_ratio, 2),
            "post_em": round(post_metrics["exact_match"], 2),
            "post_f1": round(post_metrics["f1"], 2),
            "top_hub_degree": top_hub["degree"],
        }

        logger.info(
            f"  {name}: damage={damage_ratio:.1f}%, kill={kill_ratio:.1f}%, "
            f"EM={post_metrics['exact_match']:.1f}%"
        )

        await adapter.reset()

    return {"experiment": f"wbfs_at_scale_{context_size}", "results": results}


# ============================================================
# Main
# ============================================================

async def main(args):
    """Reviewer 3 response 실험 실행"""

    results = {
        "config": {
            "context_size": args.context_size,
            "experiments": args.experiments,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }

    llm_url = args.llm_url or DOOGPU_LLM_BASE
    embed_url = args.embed_url or DOOGPU_EMBED_BASE
    llm_client = DooGPULLMClient(base_url=llm_url, model=DEFAULT_LLM_MODEL)
    embedding_provider = DooGPUEmbeddingProvider(
        base_url=embed_url, model=DEFAULT_EMBED_MODEL
    )

    # --- Q1: Typed-relation graph ---
    if "typed_relation" in args.experiments:
        sub_dataset = f"factconsolidation_mh_{args.context_size}"
        samples = load_data(sub_dataset, max_contexts=1)
        if not samples:
            logger.error(f"데이터 없음: {sub_dataset}")
            return

        sample = samples[0]
        result = await run_typed_relation_experiment(
            context=sample["context"],
            questions=sample["questions"],
            answers=sample["answers"],
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["typed_relation"] = result

    # --- W5: Organic residual ---
    if "organic_residual" in args.experiments:
        sub_dataset = f"factconsolidation_mh_{args.context_size}"
        samples = load_data(sub_dataset, max_contexts=1)
        if not samples:
            logger.error(f"데이터 없음: {sub_dataset}")
            return

        sample = samples[0]
        result = await run_organic_residual_experiment(
            context=sample["context"],
            questions=sample["questions"],
            answers=sample["answers"],
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["organic_residual"] = result

    # --- Q2: WBFS at scale ---
    if "wbfs_at_scale" in args.experiments:
        for size in args.scale_sizes:
            sub_dataset = f"factconsolidation_mh_{size}"
            samples = load_data(sub_dataset, max_contexts=1)
            if not samples:
                logger.error(f"데이터 없음: {sub_dataset}")
                continue

            sample = samples[0]
            result = await run_wbfs_at_scale_experiment(
                context=sample["context"],
                questions=sample["questions"],
                answers=sample["answers"],
                llm_client=llm_client,
                embedding_provider=embedding_provider,
                chunk_size=args.chunk_size,
                max_queries=args.max_queries,
                context_size=size,
            )
            results[f"wbfs_at_scale_{size}"] = result

    # --- 결과 저장 ---
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    exp_names = "_".join(args.experiments)
    out_path = results_dir / f"reviewer3_{exp_names}_{args.context_size}_{int(time.time())}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"\n결과 저장: {out_path}")

    # --- 콘솔 리포트 ---
    print_report(results)

    return results


def print_report(results: dict):
    """콘솔 리포트"""
    print("\n" + "=" * 80)
    print("REVIEWER 3 EXPERIMENT REPORT")
    print("=" * 80)

    # Q1: Typed-relation
    tr = results.get("typed_relation", {}).get("results", {})
    if tr:
        print("\n### Q1: Typed-relation vs Co-occurrence Graph (BFS damage)")
        print(f"{'Mode':<20} | {'Nodes':>6} | {'Edges':>6} | {'MaxDeg':>6} | {'Damage%':>8} | {'Kill%':>6}")
        print("-" * 70)
        for key in ["cooccurrence", "typed_relation"]:
            if key in tr:
                r = tr[key]
                print(
                    f"{key:<20} | {r['graph_nodes']:>6} | {r['graph_edges']:>6} | "
                    f"{r['max_degree']:>6} | {r['damage_ratio_pct']:>7.1f}% | "
                    f"{r['kill_ratio_pct']:>5.1f}%"
                )
        comp = tr.get("comparison", {})
        if comp:
            print(f"\n  Edge reduction: {comp['edge_reduction_pct']:.1f}%")
            print(f"  Damage reduction: {comp['damage_reduction_pct']:.1f}%")
            print(f"  Max-degree reduction: {comp['max_degree_reduction_pct']:.1f}%")

    # W5: Organic residual
    org = results.get("organic_residual", {})
    if org:
        s = org.get("summary", {})
        print(f"\n### W5: Organic Residual Classification ({s.get('total_valid_memories', 0)} valid memories)")
        print(f"  Total damaged: {s.get('total_damaged', 0)} ({s.get('damage_ratio_pct', 0):.1f}%)")
        print(f"  Conflict events: {s.get('total_conflict_events', 0)}")
        print(f"\n  {'Category':<24} | {'Count':>6} | {'Percent':>8}")
        print(f"  {'-'*24}-+-{'-'*6}-+-{'-'*8}")
        print(f"  {'Legitimate Cascade':<24} | {s.get('legitimate_cascade', 0):>6} | {s.get('legitimate_cascade_pct', 0):>7.1f}%")
        print(f"  {'Borderline':<24} | {s.get('borderline', 0):>6} | {s.get('borderline_pct', 0):>7.1f}%")
        print(f"  {'False Positive':<24} | {s.get('false_positive', 0):>6} | {s.get('false_positive_pct', 0):>7.1f}%")
        print(f"\n  Weight distribution: {s.get('weight_distribution', {})}")

    # Q2: WBFS at scale
    for key in sorted(results.keys()):
        if key.startswith("wbfs_at_scale_"):
            data = results[key].get("results", {})
            size = key.replace("wbfs_at_scale_", "")
            print(f"\n### Q2: Weighted BFS at {size} scale")
            print(f"{'Strategy':<22} | {'Damage%':>8} | {'Kill%':>6} | {'EM':>6} | {'F1':>6}")
            print("-" * 62)
            for skey in ["bfs_standard", "weighted_bfs_0.3", "attr_aware"]:
                if skey in data:
                    r = data[skey]
                    print(
                        f"{skey:<22} | {r['damage_ratio_pct']:>7.1f}% | "
                        f"{r['kill_ratio_pct']:>5.1f}% | "
                        f"{r.get('post_em', 0):>5.1f}% | "
                        f"{r.get('post_f1', 0):>5.1f}%"
                    )

    print("\n" + "=" * 80)


def parse_args():
    parser = argparse.ArgumentParser(description="Reviewer 3 response 실험")
    parser.add_argument("--context_size", type=str, default="6k")
    parser.add_argument("--experiments", nargs="+",
                        default=["typed_relation"],
                        choices=["typed_relation", "organic_residual", "wbfs_at_scale"])
    parser.add_argument("--scale_sizes", nargs="+", default=["32k", "64k"],
                        help="wbfs_at_scale에서 테스트할 scale (기본: 32k 64k)")
    parser.add_argument("--chunk_size", type=int, default=4096)
    parser.add_argument("--max_queries", type=int, default=10)
    parser.add_argument("--llm_url", type=str, default=None)
    parser.add_argument("--embed_url", type=str, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
