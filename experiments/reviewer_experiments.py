"""Reviewer Response 실험 — Visited-set BFS + Decay Sensitivity

Review 3의 핵심 지적사항에 대한 실증 데이터 수집:
  1. Visited-set BFS: memory-level visited set으로 중복 decay 제거 후 damage 비교
  2. Decay Sensitivity: decay_per_hop 값(0.3, 0.5, 0.7, 0.9)에 따른 damage 변화

사용법:
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/reviewer_experiments.py

  # 개별 실험
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/reviewer_experiments.py --experiments visited decay

  # DooGPU 엔드포인트 지정
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/reviewer_experiments.py --llm_url http://... --embed_url http://...
"""

from __future__ import annotations

import argparse
import asyncio
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
    DOOGPU_LLM_BASE, DOOGPU_EMBED_BASE,
    DEFAULT_LLM_MODEL, DEFAULT_EMBED_MODEL, FAKE_VALUES,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)


# ============================================================
# 1. Visited-set BFS vs Standard BFS
# ============================================================

async def run_visited_set_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """BFS with/without memory-level visited set 비교

    기존 BFS: 한 메모리가 여러 entity에 연결된 경우 중복 decay 발생
    Visited-set BFS: 각 메모리를 closest hop에서 1회만 decay
    """
    results = {}

    for mode_name, use_visited in [("bfs_standard", False), ("bfs_visited_set", True)]:
        logger.info(f"\n--- {mode_name} ---")

        adapter = MemoryModuleAdapter(
            graph_propagation=False,  # 초기 memorization 시 전파 OFF
            semantic_filter=False,
            attribute_aware=False,
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

        # Phase 2: Attack with 5 facts (white-box)
        adapter.graph_propagation = True

        # Monkey-patch: visited_memory_set 파라미터 전달
        original_propagate = adapter._decay_engine.propagate_invalidation

        async def patched_propagate(_visited=use_visited, **kwargs):
            kwargs["visited_memory_set"] = _visited
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

        results[mode_name] = {
            "use_visited_set": use_visited,
            "pre_valid": pre_state["valid"],
            "newly_decayed": newly_decayed,
            "newly_killed": newly_killed,
            "damage_ratio_pct": round(damage_ratio, 2),
            "kill_ratio_pct": round(kill_ratio, 2),
            "post_em": round(post_metrics["exact_match"], 2),
            "post_f1": round(post_metrics["f1"], 2),
            "top_hub_degree": top_hub["degree"],
        }

        logger.info(
            f"  {mode_name}: damage={damage_ratio:.1f}%, kill={kill_ratio:.1f}%, "
            f"EM={post_metrics['exact_match']:.1f}%"
        )

    # 비교 요약
    std = results.get("bfs_standard", {})
    vis = results.get("bfs_visited_set", {})
    if std and vis:
        results["comparison"] = {
            "damage_reduction_pp": round(std["damage_ratio_pct"] - vis["damage_ratio_pct"], 2),
            "kill_reduction_pp": round(std["kill_ratio_pct"] - vis["kill_ratio_pct"], 2),
            "visited_set_still_damages": vis["damage_ratio_pct"] > 10,  # 10% 이상이면 여전히 심각
        }
        logger.info(
            f"\n  Visited-set 효과: damage {std['damage_ratio_pct']:.1f}% → "
            f"{vis['damage_ratio_pct']:.1f}% "
            f"(Δ={results['comparison']['damage_reduction_pp']:+.1f}pp)"
        )

    return {"experiment": "visited_set_bfs", "results": results}


# ============================================================
# 2. Additional Propagation Baselines
# ============================================================

async def run_baseline_comparison_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """다양한 propagation strategy 비교

    BFS (standard), Weighted BFS, k-hop threshold,
    Degree-cap, Attr-Aware를 동일 조건에서 비교
    """
    strategies = [
        {"name": "bfs_standard", "params": {}},
        {"name": "weighted_bfs_0.1", "params": {"edge_weight_threshold": 0.1}},
        {"name": "weighted_bfs_0.3", "params": {"edge_weight_threshold": 0.3}},
        {"name": "khop_threshold_0.3", "params": {"decay_threshold": 0.3}},
        {"name": "khop_threshold_0.5", "params": {"decay_threshold": 0.5}},
        {"name": "degree_cap_5", "params": {"degree_cap": 5}},
        {"name": "degree_cap_10", "params": {"degree_cap": 10}},
        {"name": "visited_set", "params": {"visited_memory_set": True}},
    ]

    results = {}

    for strategy in strategies:
        name = strategy["name"]
        params = strategy["params"]
        logger.info(f"\n--- {name} ---")

        adapter = MemoryModuleAdapter(
            graph_propagation=False,
            semantic_filter=False,
            attribute_aware=False,
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

        # Phase 2: Attack (5 facts, white-box BFS with strategy params)
        adapter.graph_propagation = True

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
            "params": {k: v for k, v in params.items()},
            "pre_valid": pre_state["valid"],
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

    # Attr-Aware도 동일 조건으로 비교
    logger.info(f"\n--- attr_aware ---")
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
    pre_state = await snapshot_memory_state(adapter)

    adapter.graph_propagation = True
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

    post_state = await snapshot_memory_state(adapter)
    newly_decayed = post_state["decayed_below_1.0"] - pre_state["decayed_below_1.0"]
    newly_killed = post_state["decayed_below_0.1"] - pre_state["decayed_below_0.1"]
    damage_ratio = newly_decayed / max(pre_state["valid"], 1) * 100
    kill_ratio = newly_killed / max(pre_state["valid"], 1) * 100
    post_metrics = await evaluate_queries(adapter, questions, answers, max_queries)

    results["attr_aware"] = {
        "strategy": "attr_aware",
        "params": {},
        "pre_valid": pre_state["valid"],
        "newly_decayed": newly_decayed,
        "newly_killed": newly_killed,
        "damage_ratio_pct": round(damage_ratio, 2),
        "kill_ratio_pct": round(kill_ratio, 2),
        "post_em": round(post_metrics["exact_match"], 2),
        "post_f1": round(post_metrics["f1"], 2),
    }
    logger.info(
        f"  attr_aware: damage={damage_ratio:.1f}%, kill={kill_ratio:.1f}%, "
        f"EM={post_metrics['exact_match']:.1f}%"
    )

    return {"experiment": "baseline_comparison", "results": results}


# ============================================================
# 2.5 ATTR-AWARE Ablation: Direction vs In-degree Dampening
# ============================================================

async def run_ablation_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """ATTR-AWARE의 두 컴포넌트 ablation study

    4가지 조합:
    1. BFS (all neighbors + dampening) — 기존 결과
    2. BFS-flat (all neighbors, NO dampening) — dampening 효과 분리
    3. ATTR-AWARE (direction + dampening) — 기존 결과
    4. ATTR-flat (direction, NO dampening) — direction 효과 분리
    """
    results = {}

    # --- BFS variants (dampening ON/OFF) ---
    for name, use_dampening in [
        ("bfs_with_dampening", True),
        ("bfs_no_dampening", False),
    ]:
        logger.info(f"\n--- {name} ---")

        adapter = MemoryModuleAdapter(
            graph_propagation=False,
            semantic_filter=False,
            attribute_aware=False,
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

        # Phase 2: Attack with dampening flag
        adapter.graph_propagation = True
        original_propagate = adapter._decay_engine.propagate_invalidation

        async def patched_propagate(_dampening=use_dampening, **kwargs):
            kwargs["use_in_degree_dampening"] = _dampening
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
            "use_in_degree_dampening": use_dampening,
            "direction_filter": False,
            "pre_valid": pre_state["valid"],
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

    # --- ATTR-AWARE variants (dampening ON/OFF) ---
    for name, use_dampening in [
        ("attr_with_dampening", True),
        ("attr_no_dampening", False),
    ]:
        logger.info(f"\n--- {name} ---")

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

        pre_state = await snapshot_memory_state(adapter)
        hubs = identify_hub_entities(adapter._graph_store, top_k=5)
        top_hub = hubs[0] if hubs else {"entity": "N/A", "degree": 0}

        adapter.graph_propagation = True
        original_propagate = adapter._decay_engine.propagate_invalidation

        async def patched_propagate_attr(_dampening=use_dampening, **kwargs):
            kwargs["use_in_degree_dampening"] = _dampening
            return await original_propagate(**kwargs)

        adapter._decay_engine.propagate_invalidation = lambda **kw: patched_propagate_attr(**kw)

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

        post_state = await snapshot_memory_state(adapter)
        newly_decayed = post_state["decayed_below_1.0"] - pre_state["decayed_below_1.0"]
        newly_killed = post_state["decayed_below_0.1"] - pre_state["decayed_below_0.1"]
        damage_ratio = newly_decayed / max(pre_state["valid"], 1) * 100
        kill_ratio = newly_killed / max(pre_state["valid"], 1) * 100

        post_metrics = await evaluate_queries(adapter, questions, answers, max_queries)

        results[name] = {
            "strategy": name,
            "use_in_degree_dampening": use_dampening,
            "direction_filter": True,
            "pre_valid": pre_state["valid"],
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

    # --- ATTR-AWARE direction variants (downstream/upstream/bidirectional) ---
    for name, direction in [
        ("attr_downstream", "downstream"),
        ("attr_upstream", "upstream"),
        ("attr_bidirectional", "bidirectional"),
    ]:
        logger.info(f"\n--- {name} ---")

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

        pre_state = await snapshot_memory_state(adapter)
        hubs = identify_hub_entities(adapter._graph_store, top_k=5)
        top_hub = hubs[0] if hubs else {"entity": "N/A", "degree": 0}

        adapter.graph_propagation = True
        original_propagate = adapter._decay_engine.propagate_invalidation

        async def patched_propagate_dir(_dir=direction, **kwargs):
            kwargs["propagation_direction"] = _dir
            return await original_propagate(**kwargs)

        adapter._decay_engine.propagate_invalidation = lambda **kw: patched_propagate_dir(**kw)

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

        post_state = await snapshot_memory_state(adapter)
        newly_decayed = post_state["decayed_below_1.0"] - pre_state["decayed_below_1.0"]
        newly_killed = post_state["decayed_below_0.1"] - pre_state["decayed_below_0.1"]
        damage_ratio = newly_decayed / max(pre_state["valid"], 1) * 100
        kill_ratio = newly_killed / max(pre_state["valid"], 1) * 100

        post_metrics = await evaluate_queries(adapter, questions, answers, max_queries)

        results[name] = {
            "strategy": name,
            "propagation_direction": direction,
            "use_in_degree_dampening": True,
            "direction_filter": True,
            "pre_valid": pre_state["valid"],
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

    return {"experiment": "ablation", "results": results}


# ============================================================
# 3. Decay Sensitivity Analysis
# ============================================================

async def run_decay_sensitivity_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
    decay_values: list[float] = None,
) -> dict:
    """decay_per_hop 값에 따른 BFS damage 변화 측정

    decay=0.3 (약한 감쇄) → damage 높을 것
    decay=0.9 (강한 감쇄, 거의 원래 weight 유지) → damage 낮을 것
    """
    if decay_values is None:
        decay_values = [0.3, 0.5, 0.7, 0.9]

    results = {}

    for decay in decay_values:
        label = f"decay_{decay}"
        logger.info(f"\n--- BFS decay_per_hop={decay} ---")

        adapter = MemoryModuleAdapter(
            graph_propagation=False,
            semantic_filter=False,
            attribute_aware=False,
            propagation_depth=2,
            decay_per_hop=decay,  # 이 값이 실제 전파 시 사용됨
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
        )

        # Phase 1: Memorize
        chunks = chunk_text(context, chunk_size)
        for chunk in chunks:
            await adapter.async_send_message(chunk, memorizing=True)

        pre_state = await snapshot_memory_state(adapter)

        # Phase 2: Attack (5 facts, white-box BFS)
        adapter.graph_propagation = True

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

        results[label] = {
            "decay_per_hop": decay,
            "pre_valid": pre_state["valid"],
            "newly_decayed": newly_decayed,
            "newly_killed": newly_killed,
            "damage_ratio_pct": round(damage_ratio, 2),
            "kill_ratio_pct": round(kill_ratio, 2),
            "post_em": round(post_metrics["exact_match"], 2),
            "post_f1": round(post_metrics["f1"], 2),
        }

        logger.info(
            f"  decay={decay}: damage={damage_ratio:.1f}%, kill={kill_ratio:.1f}%, "
            f"EM={post_metrics['exact_match']:.1f}%"
        )

    return {"experiment": "decay_sensitivity", "results": results}


# ============================================================
# 4. Weight Distribution Analysis
# ============================================================

async def run_weight_distribution_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
) -> dict:
    """BFS variant별 damaged memory의 weight 분포 분석

    각 variant에 대해 5-fact white-box attack 후 weight 분포를 측정:
      - w < 0.1 (killed): 사실상 무효화된 메모리
      - 0.1 ≤ w < 0.5 (severe damage): 심각한 손상
      - 0.5 ≤ w < 1.0 (cosmetic damage): 경미한 손상
      - 전체 damaged (w < 1.0)

    Variants:
      1. bfs_standard: 기본 BFS (중복 decay 허용)
      2. bfs_visited_set: memory-level visited set (중복 decay 제거)
      3. decay_0.3 ~ decay_0.9: decay_per_hop 값 변화
    """

    # --- variant 정의 ---
    variants = [
        {
            "name": "bfs_standard",
            "decay_per_hop": 0.5,
            "propagate_params": {"visited_memory_set": False},
        },
        {
            "name": "bfs_visited_set",
            "decay_per_hop": 0.5,
            "propagate_params": {"visited_memory_set": True},
        },
        {
            "name": "decay_0.3",
            "decay_per_hop": 0.3,
            "propagate_params": {},
        },
        {
            "name": "decay_0.5",
            "decay_per_hop": 0.5,
            "propagate_params": {},
        },
        {
            "name": "decay_0.7",
            "decay_per_hop": 0.7,
            "propagate_params": {},
        },
        {
            "name": "decay_0.9",
            "decay_per_hop": 0.9,
            "propagate_params": {},
        },
    ]

    results = {}

    for variant in variants:
        name = variant["name"]
        decay = variant["decay_per_hop"]
        prop_params = variant["propagate_params"]
        logger.info(f"\n--- Weight Distribution: {name} (decay={decay}) ---")

        adapter = MemoryModuleAdapter(
            graph_propagation=False,  # memorization 시 전파 OFF
            semantic_filter=False,
            attribute_aware=False,
            propagation_depth=2,
            decay_per_hop=decay,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            db_path=":memory:",
        )

        # Phase 1: Memorize
        chunks = chunk_text(context, chunk_size)
        for chunk in chunks:
            await adapter.async_send_message(chunk, memorizing=True)

        pre_state = await snapshot_memory_state(adapter)

        # Phase 2: Attack (5 facts, white-box BFS with variant params)
        adapter.graph_propagation = True

        # monkey-patch: propagation 파라미터 주입
        if prop_params:
            original_propagate = adapter._decay_engine.propagate_invalidation

            async def patched_propagate(_params=prop_params, **kwargs):
                kwargs.update(_params)
                return await original_propagate(**kwargs)

            adapter._decay_engine.propagate_invalidation = (
                lambda **kw: patched_propagate(**kw)
            )

        high_impact = find_high_impact_keys(
            adapter._fact_registry, adapter._graph_store, top_k=10
        )
        matching_keys = [k for k, _ in high_impact]
        max_serial = (
            max(adapter._serial_registry.keys()) if adapter._serial_registry else 0
        )
        attack_facts = generate_attack_facts_from_registry(
            matching_keys, 5, max_serial
        )

        for fact_line, target_key in attack_facts:
            await adapter.async_send_message(fact_line, memorizing=True)

        # Phase 3: Weight 분포 수집
        post_state = await snapshot_memory_state(adapter)

        # pre에서 weight=1.0이었던 메모리 중 post에서 변한 것만 분석
        pre_weights = pre_state["weights"]
        post_weights = post_state["weights"]

        # 전체 valid 메모리의 post weight 분포 (attack으로 추가된 메모리 제외)
        # pre에 있던 valid 메모리 수만큼만 post_weights에서 분석
        n_pre_valid = pre_state["valid"]

        # post에서 모든 valid 메모리의 weight를 가져와 damaged 분석
        all_post_weights = post_weights  # snapshot이 반환하는 valid 메모리 전체

        # damaged memory: weight < 1.0인 것 (attack으로 새로 추가된 메모리는 weight=1.0)
        damaged_weights = [w for w in all_post_weights if w < 1.0]

        # 구간별 분류
        killed = [w for w in damaged_weights if w < 0.1]
        severe = [w for w in damaged_weights if 0.1 <= w < 0.5]
        cosmetic = [w for w in damaged_weights if 0.5 <= w < 1.0]
        total_damaged = len(damaged_weights)

        # pre 대비 새로 damaged된 것
        pre_damaged = pre_state["decayed_below_1.0"]
        newly_damaged = total_damaged - pre_damaged

        results[name] = {
            "variant": name,
            "decay_per_hop": decay,
            "propagate_params": {k: v for k, v in prop_params.items()},
            "pre_valid": n_pre_valid,
            "total_post_valid": post_state["valid"],
            # 절대 수치
            "total_damaged": total_damaged,
            "newly_damaged": newly_damaged,
            "killed_count": len(killed),
            "severe_count": len(severe),
            "cosmetic_count": len(cosmetic),
            # 비율 (pre_valid 기준)
            "killed_pct": round(len(killed) / max(n_pre_valid, 1) * 100, 2),
            "severe_pct": round(len(severe) / max(n_pre_valid, 1) * 100, 2),
            "cosmetic_pct": round(len(cosmetic) / max(n_pre_valid, 1) * 100, 2),
            "total_damaged_pct": round(
                total_damaged / max(n_pre_valid, 1) * 100, 2
            ),
            # 분포 비율 (damaged 내부 비율)
            "killed_ratio_in_damaged": round(
                len(killed) / max(total_damaged, 1) * 100, 2
            ),
            "severe_ratio_in_damaged": round(
                len(severe) / max(total_damaged, 1) * 100, 2
            ),
            "cosmetic_ratio_in_damaged": round(
                len(cosmetic) / max(total_damaged, 1) * 100, 2
            ),
            # weight 통계
            "damaged_avg_weight": round(
                sum(damaged_weights) / max(len(damaged_weights), 1), 4
            ),
            "damaged_min_weight": round(min(damaged_weights), 4) if damaged_weights else 1.0,
        }

        logger.info(
            f"  {name}: damaged={total_damaged} ({results[name]['total_damaged_pct']:.1f}%) | "
            f"killed={len(killed)} ({results[name]['killed_pct']:.1f}%) | "
            f"severe={len(severe)} ({results[name]['severe_pct']:.1f}%) | "
            f"cosmetic={len(cosmetic)} ({results[name]['cosmetic_pct']:.1f}%)"
        )

    return {"experiment": "weight_distribution", "results": results}


# ============================================================
# Experiment 5: Wall-clock time measurement
# ============================================================

async def run_wallclock_experiment(
    context: str,
    questions: list,
    answers: list,
    llm_client,
    embedding_provider,
    chunk_size: int = 4096,
    max_queries: int = 10,
    n_runs: int = 3,
) -> dict:
    """BFS 및 Attr-Aware propagation의 wall-clock time 측정

    각 strategy를 n_runs회 반복하여 평균/표준편차 보고.
    """
    import statistics

    results = {}

    strategies = [
        ("bfs_standard", {"graph_propagation": True, "attribute_aware": False}),
        ("attr_aware", {"graph_propagation": True, "attribute_aware": True}),
    ]

    for strategy_name, strategy_params in strategies:
        logger.info(f"\n--- Wall-clock: {strategy_name} ---")
        times_propagation = []  # propagation만의 시간
        times_total = []  # attack fact 전체 처리 시간

        for run_i in range(n_runs):
            adapter = MemoryModuleAdapter(
                graph_propagation=False,  # memorization 시 전파 OFF
                semantic_filter=False,
                attribute_aware=False,
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

            # Phase 2: Prepare attack
            hubs = identify_hub_entities(adapter._graph_store, top_k=5)
            fact_registry = adapter._fact_registry
            max_serial = max(adapter._serial_registry.keys()) if adapter._serial_registry else 0
            high_impact = find_high_impact_keys(
                fact_registry, adapter._graph_store, top_k=10
            )
            matching_keys = [k for k, _ in high_impact]
            attack_facts = generate_attack_facts_from_registry(
                matching_keys, 5, max_serial
            )

            # Phase 3: 전파 ON + 시간 측정
            adapter.graph_propagation = strategy_params["graph_propagation"]
            adapter.attribute_aware = strategy_params.get("attribute_aware", False)

            prop_times = []

            # monkey-patch adapter._decay_engine.propagate_invalidation으로 시간 측정
            _orig_propagate = adapter._decay_engine.propagate_invalidation

            async def timed_propagate(**kwargs):
                t0 = time.perf_counter()
                result = await _orig_propagate(**kwargs)
                prop_times.append(time.perf_counter() - t0)
                return result

            adapter._decay_engine.propagate_invalidation = lambda **kw: timed_propagate(**kw)

            t_total_start = time.perf_counter()
            for fact_line, target_key in attack_facts:
                await adapter.async_send_message(fact_line, memorizing=True)
            t_total = time.perf_counter() - t_total_start

            # restore
            adapter._decay_engine.propagate_invalidation = _orig_propagate

            total_prop_time = sum(prop_times) if prop_times else 0
            times_propagation.append(total_prop_time)
            times_total.append(t_total)

            logger.info(
                f"  Run {run_i+1}: prop={total_prop_time*1000:.1f}ms, total={t_total*1000:.1f}ms"
            )

        results[strategy_name] = {
            "n_runs": n_runs,
            "propagation_ms_mean": round(statistics.mean(times_propagation) * 1000, 2),
            "propagation_ms_std": round(statistics.stdev(times_propagation) * 1000, 2) if len(times_propagation) > 1 else 0,
            "total_attack_ms_mean": round(statistics.mean(times_total) * 1000, 2),
            "total_attack_ms_std": round(statistics.stdev(times_total) * 1000, 2) if len(times_total) > 1 else 0,
            "propagation_per_fact_ms": round(statistics.mean(times_propagation) / 5 * 1000, 2),
            "graph_nodes": len(adapter._graph_store.entity_graph.nodes()),
            "graph_edges": len(adapter._graph_store.entity_graph.edges()),
        }

    return {"experiment": "wallclock_timing", "results": results}


# ============================================================
# Main
# ============================================================

async def main(args):
    """Reviewer response 실험 실행"""

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

    results = {
        "config": {
            "context_size": args.context_size,
            "sub_dataset": sub_dataset,
            "experiments": args.experiments,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }

    # --- Experiment 1: Visited-set BFS ---
    if "visited" in args.experiments:
        logger.info("\n" + "=" * 70)
        logger.info("EXPERIMENT 1: Visited-set BFS vs Standard BFS")
        logger.info("=" * 70)
        visited_result = await run_visited_set_experiment(
            context=context,
            questions=questions,
            answers=answers,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["visited_set"] = visited_result

    # --- Experiment 2: Baseline Comparison ---
    if "baselines" in args.experiments:
        logger.info("\n" + "=" * 70)
        logger.info("EXPERIMENT 2: Propagation Strategy Comparison")
        logger.info("=" * 70)
        baseline_result = await run_baseline_comparison_experiment(
            context=context,
            questions=questions,
            answers=answers,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["baseline_comparison"] = baseline_result

    # --- Experiment 3: Decay Sensitivity ---
    if "decay" in args.experiments:
        logger.info("\n" + "=" * 70)
        logger.info("EXPERIMENT 2: Decay Sensitivity (0.3, 0.5, 0.7, 0.9)")
        logger.info("=" * 70)
        decay_result = await run_decay_sensitivity_experiment(
            context=context,
            questions=questions,
            answers=answers,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
            decay_values=[0.3, 0.5, 0.7, 0.9],
        )
        results["decay_sensitivity"] = decay_result

    # --- Experiment 4: Weight Distribution ---
    if "weight_dist" in args.experiments:
        logger.info("\n" + "=" * 70)
        logger.info("EXPERIMENT 4: Weight Distribution Analysis")
        logger.info("=" * 70)
        weight_dist_result = await run_weight_distribution_experiment(
            context=context,
            questions=questions,
            answers=answers,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["weight_distribution"] = weight_dist_result

    # --- Experiment 5: Wall-clock Timing ---
    if "wallclock" in args.experiments:
        logger.info("\n" + "=" * 70)
        logger.info("EXPERIMENT 5: Wall-clock Timing (BFS vs Attr-Aware)")
        logger.info("=" * 70)
        wallclock_result = await run_wallclock_experiment(
            context=context,
            questions=questions,
            answers=answers,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["wallclock_timing"] = wallclock_result

    # --- Experiment 6: ATTR-AWARE Ablation ---
    if "ablation" in args.experiments:
        logger.info("\n" + "=" * 70)
        logger.info("EXPERIMENT 6: ATTR-AWARE Ablation (Direction vs Dampening)")
        logger.info("=" * 70)
        ablation_result = await run_ablation_experiment(
            context=context,
            questions=questions,
            answers=answers,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            chunk_size=args.chunk_size,
            max_queries=args.max_queries,
        )
        results["ablation"] = ablation_result

    # --- 결과 저장 ---
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"reviewer_experiments_{args.context_size}_{int(time.time())}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"\n결과 저장: {out_path}")

    # --- 콘솔 리포트 ---
    print_report(results)

    return results


def print_report(results: dict):
    """콘솔 리포트"""
    print("\n" + "=" * 80)
    print("REVIEWER EXPERIMENT REPORT")
    print("=" * 80)

    # Visited-set BFS
    vs = results.get("visited_set", {}).get("results", {})
    if vs:
        print("\n### 1. Visited-set BFS vs Standard BFS (5-fact white-box attack)")
        print(f"{'Mode':<20} | {'Damage%':>8} | {'Kill%':>6} | {'EM':>6} | {'F1':>6}")
        print("-" * 60)
        for key in ["bfs_standard", "bfs_visited_set"]:
            if key in vs:
                r = vs[key]
                label = "BFS (standard)" if key == "bfs_standard" else "BFS (visited-set)"
                print(
                    f"{label:<20} | {r['damage_ratio_pct']:>7.1f}% | "
                    f"{r['kill_ratio_pct']:>5.1f}% | "
                    f"{r.get('post_em', 0):>5.1f}% | "
                    f"{r.get('post_f1', 0):>5.1f}%"
                )
        comp = vs.get("comparison", {})
        if comp:
            print(f"\n  → Visited-set으로 damage {comp['damage_reduction_pp']:+.1f}pp 변화")
            if comp.get("visited_set_still_damages"):
                print("  → 여전히 심각한 수준 (>10%) — 논문 주장 유지")
            else:
                print("  → 10% 이하로 감소 — 논문 Limitation 수정 필요")

    # Baseline comparison
    bc = results.get("baseline_comparison", {}).get("results", {})
    if bc:
        print("\n### 2. Propagation Strategy Comparison (5-fact white-box attack)")
        print(f"{'Strategy':<22} | {'Damage%':>8} | {'Kill%':>6} | {'EM':>6} | {'F1':>6}")
        print("-" * 62)
        order = [
            "bfs_standard", "visited_set",
            "weighted_bfs_0.1", "weighted_bfs_0.3",
            "khop_threshold_0.3", "khop_threshold_0.5",
            "degree_cap_5", "degree_cap_10",
            "attr_aware",
        ]
        for key in order:
            if key in bc:
                r = bc[key]
                print(
                    f"{key:<22} | {r['damage_ratio_pct']:>7.1f}% | "
                    f"{r['kill_ratio_pct']:>5.1f}% | "
                    f"{r.get('post_em', 0):>5.1f}% | "
                    f"{r.get('post_f1', 0):>5.1f}%"
                )

    # Decay sensitivity
    ds = results.get("decay_sensitivity", {}).get("results", {})
    if ds:
        print("\n### 3. Decay Sensitivity (BFS, 5-fact white-box attack)")
        print(f"{'Decay':>8} | {'Damage%':>8} | {'Kill%':>6} | {'EM':>6} | {'F1':>6}")
        print("-" * 50)
        for key in sorted(ds.keys()):
            r = ds[key]
            print(
                f"{r['decay_per_hop']:>8.1f} | {r['damage_ratio_pct']:>7.1f}% | "
                f"{r['kill_ratio_pct']:>5.1f}% | "
                f"{r.get('post_em', 0):>5.1f}% | "
                f"{r.get('post_f1', 0):>5.1f}%"
            )

    # Weight Distribution
    wd = results.get("weight_distribution", {}).get("results", {})
    if wd:
        print("\n### 4. Weight Distribution (5-fact white-box attack)")
        print(
            f"{'Variant':<20} | {'Killed':>7} | {'Severe':>7} | {'Cosmetic':>8} | "
            f"{'Total':>7} | {'Dmg%':>6}"
        )
        print(
            f"{'':20} | {'w<0.1':>7} | {'0.1≤w<0.5':>7} | {'0.5≤w<1.0':>8} | "
            f"{'w<1.0':>7} |"
        )
        print("-" * 76)
        order = [
            "bfs_standard", "bfs_visited_set",
            "decay_0.3", "decay_0.5", "decay_0.7", "decay_0.9",
        ]
        for key in order:
            if key not in wd:
                continue
            r = wd[key]
            print(
                f"{key:<20} | "
                f"{r['killed_count']:>4} ({r['killed_pct']:>4.1f}%) | "
                f"{r['severe_count']:>4} ({r['severe_pct']:>4.1f}%) | "
                f"{r['cosmetic_count']:>5} ({r['cosmetic_pct']:>4.1f}%) | "
                f"{r['total_damaged']:>4} ({r['total_damaged_pct']:>4.1f}%) |"  # noqa: E501
            )

        # damaged 내부 비율 테이블
        print(
            f"\n  (damaged 내부 비율)"
        )
        print(
            f"  {'Variant':<20} | {'Killed%':>8} | {'Severe%':>8} | {'Cosmetic%':>9} | "
            f"{'AvgW':>6} | {'MinW':>6}"
        )
        print("  " + "-" * 72)
        for key in order:
            if key not in wd:
                continue
            r = wd[key]
            print(
                f"  {key:<20} | "
                f"{r['killed_ratio_in_damaged']:>7.1f}% | "
                f"{r['severe_ratio_in_damaged']:>7.1f}% | "
                f"{r['cosmetic_ratio_in_damaged']:>8.1f}% | "
                f"{r['damaged_avg_weight']:>6.4f} | "
                f"{r['damaged_min_weight']:>6.4f}"
            )

    print("\n" + "=" * 80)


def parse_args():
    parser = argparse.ArgumentParser(description="Reviewer response 실험")
    parser.add_argument("--context_size", type=str, default="6k")
    parser.add_argument("--experiments", nargs="+",
                        default=["visited", "decay"],
                        choices=["visited", "decay", "baselines", "weight_dist", "wallclock", "ablation"])
    parser.add_argument("--chunk_size", type=int, default=4096)
    parser.add_argument("--max_queries", type=int, default=10)
    parser.add_argument("--llm_url", type=str, default=None)
    parser.add_argument("--embed_url", type=str, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
