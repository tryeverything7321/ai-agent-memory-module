from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


POLICIES = ("bfs", "attribute_aware")


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(mean(values), 1)


def summarize_arm(sample: dict[str, Any], policy: str) -> dict[str, Any]:
    baseline_f1 = float(sample["baseline"]["metrics"]["f1"])
    arm = sample[policy]
    per_hub = arm.get("multi_hub", {}).get("per_hub", [])
    pre = arm.get("memory_stats_pre", {})
    post = arm.get("memory_stats_post", {})

    blast_values = [float(row.get("affected", 0.0)) for row in per_hub]
    collateral_values = [float(row.get("collateral", 0.0)) for row in per_hub]
    retrievable_loss = int(pre.get("retrievable", 0)) - int(post.get("retrievable", 0))
    invalid_added = int(post.get("invalid", 0)) - int(pre.get("invalid", 0))

    return {
        "policy": policy,
        "mean_blast_radius": _avg(blast_values),
        "mean_collateral": _avg(collateral_values),
        "retrievable_loss": retrievable_loss,
        "invalid_added": invalid_added,
        "decayed_below_threshold": int(post.get("decayed_below_threshold", 0)),
        "f1": round(float(arm["metrics"]["f1"]), 1),
        "f1_delta": round(float(arm["metrics"]["f1"]) - baseline_f1, 1),
    }


def summarize_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    dataset = str(result.get("config", {}).get("sub_dataset", "unknown"))
    rows = []
    for policy in POLICIES:
        arm_rows = [
            summarize_arm(sample, policy)
            for sample in result.get("per_sample", [])
        ]
        rows.append({
            "dataset": dataset,
            "policy": policy,
            "mean_blast_radius": _avg([
                row["mean_blast_radius"] for row in arm_rows
            ]),
            "mean_collateral": _avg([
                row["mean_collateral"] for row in arm_rows
            ]),
            "mean_retrievable_loss": _avg([
                row["retrievable_loss"] for row in arm_rows
            ]),
            "mean_invalid_added": _avg([
                row["invalid_added"] for row in arm_rows
            ]),
            "mean_decayed_below_threshold": _avg([
                row["decayed_below_threshold"] for row in arm_rows
            ]),
            "mean_f1": _avg([row["f1"] for row in arm_rows]),
            "mean_f1_delta": _avg([row["f1_delta"] for row in arm_rows]),
        })
    return rows


def markdown_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        "Dataset",
        "Policy",
        "Blast radius",
        "Collateral",
        "Retrievable loss",
        "Below threshold",
        "F1 delta",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {dataset} | {policy} | {mean_blast_radius:.1f} | "
            "{mean_collateral:.1f} | {mean_retrievable_loss:.1f} | "
            "{mean_decayed_below_threshold:.1f} | {mean_f1_delta:+.1f} |".format(
                **row
            )
        )
    return "\n".join(lines)


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(summarize_result(json.loads(path.read_text())))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    rows = load_rows(args.result_json)
    if args.format == "markdown":
        text = markdown_table(rows) + "\n"
    else:
        text = json.dumps(rows, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
