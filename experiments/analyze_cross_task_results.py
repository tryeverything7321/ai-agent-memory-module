from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _metric(arm: dict[str, Any], name: str) -> float:
    return float(arm["metrics"][name])


def summarize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    baseline_f1 = _metric(sample["baseline"], "f1")
    bfs_f1 = _metric(sample["bfs"], "f1")
    attr_f1 = _metric(sample["attribute_aware"], "f1")
    bfs_collateral = float(sample["bfs"].get("collateral_damage", 0.0))
    attr_collateral = float(sample["attribute_aware"].get("collateral_damage", 0.0))
    hubs = [
        str(hub["entity"])
        for hub in sample["baseline"].get("all_hubs", [])[:5]
    ]
    return {
        "sample_idx": int(sample["sample_idx"]),
        "hubs": hubs,
        "baseline_f1": round(baseline_f1, 1),
        "bfs_f1": round(bfs_f1, 1),
        "attr_f1": round(attr_f1, 1),
        "bfs_f1_delta": round(bfs_f1 - baseline_f1, 1),
        "attr_f1_delta": round(attr_f1 - baseline_f1, 1),
        "bfs_collateral": round(bfs_collateral, 1),
        "attr_collateral": round(attr_collateral, 1),
        "collateral_reduction": round(bfs_collateral - attr_collateral, 1),
    }


def compute_arm_deltas(sample_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    bfs_deltas = [float(sample["bfs_f1_delta"]) for sample in sample_summaries]
    attr_deltas = [float(sample["attr_f1_delta"]) for sample in sample_summaries]
    return {
        "n_samples": len(sample_summaries),
        "mean_bfs_f1_delta": round(mean(bfs_deltas), 1),
        "mean_attr_f1_delta": round(mean(attr_deltas), 1),
        "bfs_retrieval_drop_count": sum(delta < 0 for delta in bfs_deltas),
        "bfs_retrieval_gain_count": sum(delta > 0 for delta in bfs_deltas),
        "attr_retrieval_drop_count": sum(delta < 0 for delta in attr_deltas),
        "attr_retrieval_gain_count": sum(delta > 0 for delta in attr_deltas),
    }


def analyze(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    samples = [summarize_sample(sample) for sample in data["per_sample"]]
    return {
        "source_file": str(path),
        "aggregate": data["aggregate"],
        "per_sample": samples,
        "deltas": compute_arm_deltas(samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.result_json)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
