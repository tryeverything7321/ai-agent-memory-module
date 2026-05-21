from __future__ import annotations

import argparse
import json
import random
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class MemoryFact:
    fact_id: int
    subject: str
    attribute: str
    object: str
    chain_id: int | None
    position: int | None
    has_hub: bool = False


@dataclass
class SyntheticWorld:
    facts: list[MemoryFact]
    dependency_edges: dict[int, set[int]]
    cooccurrence_edges: dict[int, set[int]]
    triggers: list[int]
    config: dict


def _add_edge(graph: dict[int, set[int]], a: int, b: int) -> None:
    if a == b:
        return
    graph.setdefault(a, set()).add(b)
    graph.setdefault(b, set()).add(a)


def _add_directed_edge(graph: dict[int, set[int]], a: int, b: int) -> None:
    if a == b:
        return
    graph.setdefault(a, set()).add(b)


def _empty_graph(n: int) -> dict[int, set[int]]:
    return {idx: set() for idx in range(n)}


def generate_world(
    *,
    n_entities: int = 30,
    n_chains: int = 10,
    chain_length: int = 5,
    noise_edges: int = 0,
    hub_facts: int = 0,
    seed: int = 0,
) -> SyntheticWorld:
    rng = random.Random(seed)
    entities = [f"E{idx:03d}" for idx in range(n_entities)]
    facts: list[MemoryFact] = []
    dependency_edges: dict[int, set[int]] = {}

    for chain_id in range(n_chains):
        subject = entities[chain_id % n_entities]
        previous_id: int | None = None
        for position in range(chain_length):
            fact_id = len(facts)
            obj = entities[(chain_id + position + 1) % n_entities]
            facts.append(
                MemoryFact(
                    fact_id=fact_id,
                    subject=subject,
                    attribute=f"attr_{position}",
                    object=obj,
                    chain_id=chain_id,
                    position=position,
                )
            )
            if previous_id is not None:
                _add_directed_edge(dependency_edges, previous_id, fact_id)
            previous_id = fact_id

    base_fact_count = len(facts)
    for idx in range(hub_facts):
        fact_id = len(facts)
        facts.append(
            MemoryFact(
                fact_id=fact_id,
                subject="Project Note",
                attribute=f"generic_{idx}",
                object=entities[idx % n_entities],
                chain_id=None,
                position=None,
                has_hub=True,
            )
        )

    dependency_edges = {
        fact.fact_id: set(dependency_edges.get(fact.fact_id, set()))
        for fact in facts
    }
    cooccurrence_edges = _empty_graph(len(facts))

    # Dependency chains co-occur because they share a subject.
    chain_members: dict[int, list[int]] = {}
    for fact in facts[:base_fact_count]:
        if fact.chain_id is None:
            continue
        chain_members.setdefault(fact.chain_id, []).append(fact.fact_id)
    for members in chain_members.values():
        for left, right in zip(members, members[1:]):
            _add_edge(cooccurrence_edges, left, right)

    # The artificial hub creates co-occurrence shortcuts without true dependency.
    hub_ids = [fact.fact_id for fact in facts if fact.has_hub]
    if hub_ids:
        for hub_id in hub_ids:
            for target in rng.sample(range(base_fact_count), k=min(6, base_fact_count)):
                _add_edge(cooccurrence_edges, hub_id, target)
        for left, right in zip(hub_ids, hub_ids[1:]):
            _add_edge(cooccurrence_edges, left, right)

    possible_pairs = [
        (a, b)
        for a in range(len(facts))
        for b in range(a + 1, len(facts))
        if b not in cooccurrence_edges[a]
    ]
    rng.shuffle(possible_pairs)
    for left, right in possible_pairs[:noise_edges]:
        _add_edge(cooccurrence_edges, left, right)

    triggers = [
        members[0]
        for _, members in sorted(chain_members.items())
        if members
    ]
    if hub_ids:
        triggers.extend(hub_ids[: min(3, len(hub_ids))])

    return SyntheticWorld(
        facts=facts,
        dependency_edges=dependency_edges,
        cooccurrence_edges=cooccurrence_edges,
        triggers=triggers,
        config={
            "n_entities": n_entities,
            "n_chains": n_chains,
            "chain_length": chain_length,
            "noise_edges": noise_edges,
            "hub_facts": hub_facts,
            "seed": seed,
        },
    )


def dependency_closure(world: SyntheticWorld, trigger: int, depth: int) -> set[int]:
    return _directed_reachable(world.dependency_edges, trigger, depth)


def _directed_reachable(
    graph: dict[int, set[int]], start: int, depth: int
) -> set[int]:
    reached: set[int] = set()
    queue = deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        if dist >= depth:
            continue
        for nxt in graph.get(node, set()):
            if nxt in reached:
                continue
            reached.add(nxt)
            queue.append((nxt, dist + 1))
    reached.discard(start)
    return reached


def bfs_cooccurrence(world: SyntheticWorld, trigger: int, depth: int) -> set[int]:
    return _undirected_reachable(world.cooccurrence_edges, trigger, depth)


def degree_capped_bfs(
    world: SyntheticWorld, trigger: int, depth: int, degree_cap: int
) -> set[int]:
    reached: set[int] = set()
    queue = deque([(trigger, 0)])
    while queue:
        node, dist = queue.popleft()
        if dist >= depth:
            continue
        if node != trigger and len(world.cooccurrence_edges.get(node, set())) > degree_cap:
            continue
        for nxt in world.cooccurrence_edges.get(node, set()):
            if nxt in reached or nxt == trigger:
                continue
            reached.add(nxt)
            queue.append((nxt, dist + 1))
    return reached


def weighted_bfs(
    world: SyntheticWorld, trigger: int, depth: int, degree_penalty_threshold: int
) -> set[int]:
    reached: set[int] = set()
    queue = deque([(trigger, 0)])
    while queue:
        node, dist = queue.popleft()
        if dist >= depth:
            continue
        for nxt in world.cooccurrence_edges.get(node, set()):
            if nxt in reached or nxt == trigger:
                continue
            if len(world.cooccurrence_edges.get(nxt, set())) > degree_penalty_threshold:
                continue
            reached.add(nxt)
            queue.append((nxt, dist + 1))
    return reached


def attr_like(world: SyntheticWorld, trigger: int, depth: int) -> set[int]:
    trigger_subject = world.facts[trigger].subject
    true_edges = world.dependency_edges.get(trigger, set())
    reached: set[int] = set()
    for candidate in bfs_cooccurrence(world, trigger, depth):
        if candidate in true_edges:
            reached.add(candidate)
            continue
        if world.facts[candidate].subject == trigger_subject:
            # Heuristic guardrail: only adjacent same-subject memories are kept.
            if candidate in world.cooccurrence_edges.get(trigger, set()):
                reached.add(candidate)
    reached.discard(trigger)
    return reached


def _undirected_reachable(
    graph: dict[int, set[int]], start: int, depth: int
) -> set[int]:
    reached: set[int] = set()
    queue = deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        if dist >= depth:
            continue
        for nxt in graph.get(node, set()):
            if nxt in reached or nxt == start:
                continue
            reached.add(nxt)
            queue.append((nxt, dist + 1))
    return reached


def score_prediction(
    *,
    predicted: set[int],
    truth: set[int],
    universe_size: int,
) -> dict[str, float]:
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    non_dependent = max(universe_size - len(truth) - 1, 0)
    precision = tp / len(predicted) if predicted else (1.0 if not truth else 0.0)
    recall = tp / len(truth) if truth else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "blast_radius": len(predicted),
        "false_positive_rate": fp / non_dependent if non_dependent else 0.0,
    }


def evaluate_world(
    world: SyntheticWorld,
    *,
    depth: int = 2,
    degree_cap: int = 4,
    degree_penalty_threshold: int = 4,
) -> dict:
    algorithms = {
        "oracle_dependency": lambda trigger: dependency_closure(world, trigger, depth),
        "bfs_cooccurrence": lambda trigger: bfs_cooccurrence(world, trigger, depth),
        "degree_capped_bfs": lambda trigger: degree_capped_bfs(
            world, trigger, depth, degree_cap
        ),
        "weighted_bfs": lambda trigger: weighted_bfs(
            world, trigger, depth, degree_penalty_threshold
        ),
        "attr_like": lambda trigger: attr_like(world, trigger, depth),
    }
    per_trigger = []
    for trigger in world.triggers:
        truth = dependency_closure(world, trigger, depth)
        row = {"trigger": trigger, "truth_size": len(truth), "algorithms": {}}
        for name, fn in algorithms.items():
            predicted = fn(trigger)
            row["algorithms"][name] = score_prediction(
                predicted=predicted,
                truth=truth,
                universe_size=len(world.facts),
            )
        per_trigger.append(row)
    aggregate = {
        name: _average_metrics(row["algorithms"][name] for row in per_trigger)
        for name in algorithms
    }
    return {
        "config": world.config,
        "n_facts": len(world.facts),
        "n_triggers": len(world.triggers),
        "depth": depth,
        "degree_cap": degree_cap,
        "degree_penalty_threshold": degree_penalty_threshold,
        "aggregate": aggregate,
        "per_trigger": per_trigger,
    }


def _average_metrics(rows: Iterable[dict[str, float]]) -> dict[str, float]:
    rows = list(rows)
    if not rows:
        return {}
    keys = rows[0].keys()
    return {
        key: sum(float(row[key]) for row in rows) / len(rows)
        for key in keys
    }


def run_smoke(seed: int = 0) -> dict:
    variants = {
        "clean": {"noise_edges": 0, "hub_facts": 0},
        "noisy": {"noise_edges": 120, "hub_facts": 0},
        "hub_heavy": {"noise_edges": 120, "hub_facts": 20},
    }
    results = {}
    for name, cfg in variants.items():
        world = generate_world(seed=seed, **cfg)
        results[name] = evaluate_world(world, depth=2)
    return {"seed": seed, "variants": results}


def run_sweep(
    *,
    sizes: list[int],
    noise_multipliers: list[float],
    hub_multipliers: list[float],
    seeds: list[int],
    chain_length: int = 5,
) -> dict:
    rows = []
    for n_entities in sizes:
        n_chains = max(1, n_entities // 3)
        base_facts = n_chains * chain_length
        for noise_multiplier in noise_multipliers:
            for hub_multiplier in hub_multipliers:
                for seed in seeds:
                    noise_edges = int(base_facts * noise_multiplier)
                    hub_facts = int(n_chains * hub_multiplier)
                    world = generate_world(
                        n_entities=n_entities,
                        n_chains=n_chains,
                        chain_length=chain_length,
                        noise_edges=noise_edges,
                        hub_facts=hub_facts,
                        seed=seed,
                    )
                    evaluation = evaluate_world(world, depth=2)
                    rows.append({
                        "n_entities": n_entities,
                        "n_chains": n_chains,
                        "chain_length": chain_length,
                        "noise_multiplier": noise_multiplier,
                        "hub_multiplier": hub_multiplier,
                        "noise_edges": noise_edges,
                        "hub_facts": hub_facts,
                        "seed": seed,
                        "n_facts": evaluation["n_facts"],
                        "aggregate": evaluation["aggregate"],
                    })
    return {
        "config": {
            "sizes": sizes,
            "noise_multipliers": noise_multipliers,
            "hub_multipliers": hub_multipliers,
            "seeds": seeds,
            "chain_length": chain_length,
        },
        "rows": rows,
        "summary": summarize_sweep(rows),
    }


def summarize_sweep(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[int, float, float], list[dict]] = {}
    for row in rows:
        key = (
            row["n_entities"],
            row["noise_multiplier"],
            row["hub_multiplier"],
        )
        grouped.setdefault(key, []).append(row)

    summary = []
    for (n_entities, noise_multiplier, hub_multiplier), group in sorted(grouped.items()):
        entry = {
            "n_entities": n_entities,
            "noise_multiplier": noise_multiplier,
            "hub_multiplier": hub_multiplier,
            "n_runs": len(group),
            "algorithms": {},
        }
        for algorithm in group[0]["aggregate"]:
            entry["algorithms"][algorithm] = _average_metrics(
                row["aggregate"][algorithm] for row in group
            )
        summary.append(entry)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--sizes", nargs="+", type=int, default=[30, 100, 300])
    parser.add_argument(
        "--noise_multipliers", nargs="+", type=float, default=[0.0, 1.0, 3.0]
    )
    parser.add_argument(
        "--hub_multipliers", nargs="+", type=float, default=[0.0, 0.5, 2.0]
    )
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.sweep:
        result = run_sweep(
            sizes=args.sizes,
            noise_multipliers=args.noise_multipliers,
            hub_multipliers=args.hub_multipliers,
            seeds=list(range(args.seeds)),
        )
        compact = _compact_sweep_summary(result)
    else:
        result = run_smoke(seed=args.seed)
        compact = _compact_summary(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(compact, indent=2))


def _compact_summary(result: dict) -> dict:
    summary = {}
    for variant, data in result["variants"].items():
        summary[variant] = {
            name: {
                "precision": round(metrics["precision"], 3),
                "recall": round(metrics["recall"], 3),
                "false_positive": round(metrics["false_positive"], 2),
                "false_negative": round(metrics["false_negative"], 2),
                "blast_radius": round(metrics["blast_radius"], 2),
            }
            for name, metrics in data["aggregate"].items()
        }
    return summary


def _compact_sweep_summary(result: dict) -> list[dict]:
    compact = []
    for row in result["summary"]:
        algorithms = row["algorithms"]
        compact.append({
            "n_entities": row["n_entities"],
            "noise_multiplier": row["noise_multiplier"],
            "hub_multiplier": row["hub_multiplier"],
            "bfs_fp": round(
                algorithms["bfs_cooccurrence"]["false_positive"], 2
            ),
            "bfs_blast": round(
                algorithms["bfs_cooccurrence"]["blast_radius"], 2
            ),
            "attr_fp": round(algorithms["attr_like"]["false_positive"], 2),
            "attr_recall": round(algorithms["attr_like"]["recall"], 3),
            "degree_cap_fp": round(
                algorithms["degree_capped_bfs"]["false_positive"], 2
            ),
            "weighted_recall": round(algorithms["weighted_bfs"]["recall"], 3),
        })
    return compact


def world_to_jsonable(world: SyntheticWorld) -> dict:
    return {
        "facts": [asdict(fact) for fact in world.facts],
        "dependency_edges": {
            str(key): sorted(value) for key, value in world.dependency_edges.items()
        },
        "cooccurrence_edges": {
            str(key): sorted(value) for key, value in world.cooccurrence_edges.items()
        },
        "triggers": world.triggers,
        "config": world.config,
    }


if __name__ == "__main__":
    main()
