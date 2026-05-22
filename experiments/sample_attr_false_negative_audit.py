from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def make_audit_item(
    sample_idx: int,
    hub: str,
    source_memory: str,
    target_memory: str,
    bfs_reached: bool,
    attr_reached: bool,
) -> dict[str, Any]:
    if bfs_reached and not attr_reached:
        bucket = "bfs_reached_attr_blocked"
    elif attr_reached:
        bucket = "attr_reached"
    else:
        bucket = "random_cooccurring"
    return {
        "sample_idx": sample_idx,
        "hub": hub,
        "source_memory": source_memory,
        "target_memory": target_memory,
        "bfs_reached": bfs_reached,
        "attr_reached": attr_reached,
        "bucket": bucket,
        "label": "",
        "notes": "",
    }


def write_template(output: Path) -> None:
    template = [
        make_audit_item(
            sample_idx=0,
            hub="Debbie",
            source_memory="Replace with invalidated memory text.",
            target_memory="Replace with candidate dependent memory text.",
            bfs_reached=True,
            attr_reached=False,
        )
    ]
    output.write_text(json.dumps(template, indent=2) + "\n")


def _trace_by_hub(sample: dict[str, Any], policy: str) -> dict[str, dict[str, Any]]:
    per_hub = sample.get(policy, {}).get("multi_hub", {}).get("per_hub", [])
    return {
        str(row.get("hub_entity", "")): row.get("audit_trace") or {}
        for row in per_hub
        if row.get("audit_trace")
    }


def _affected_by_id(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("memory_id", "")): row
        for row in trace.get("affected_sample", [])
        if row.get("memory_id")
    }


def sample_audit_items(
    result: dict[str, Any],
    max_items_per_bucket: int,
) -> list[dict[str, Any]]:
    """Create a stratified dependency-audit set from trace-enabled results.

    Buckets:
      - bfs_reached_attr_blocked: candidate false negatives for ATTR-AWARE.
      - attr_reached: accepted propagation controls sampled directly from the
        ATTR-AWARE trace, not only from overlap with the BFS trace sample.

    The direct ATTR sampling matters because trace caps can hide overlap even
    when ATTR-AWARE accepted many propagated memories.
    """
    blocked_candidates = []
    reached_candidates = []
    seen_blocked = set()
    seen_reached = set()
    for sample in result.get("per_sample", []):
        sample_idx = int(sample.get("sample_idx", -1))
        bfs_traces = _trace_by_hub(sample, "bfs")
        attr_traces = _trace_by_hub(sample, "attribute_aware")
        for hub, bfs_trace in bfs_traces.items():
            attr_trace = attr_traces.get(hub, {})
            bfs_affected = _affected_by_id(bfs_trace)
            attr_affected = _affected_by_id(attr_trace)
            source_memory = str(bfs_trace.get("trigger_content", ""))
            for memory_id, target in bfs_affected.items():
                if memory_id in attr_affected:
                    key = (sample_idx, hub, memory_id)
                    if (
                        key not in seen_reached
                    ):
                        seen_reached.add(key)
                        reached_candidates.append(make_audit_item(
                            sample_idx=sample_idx,
                            hub=hub,
                            source_memory=source_memory,
                            target_memory=str(target.get("content", "")),
                            bfs_reached=True,
                            attr_reached=True,
                        ))
                    continue
                key = (sample_idx, hub, memory_id)
                if (
                    key not in seen_blocked
                ):
                    seen_blocked.add(key)
                    blocked_candidates.append(make_audit_item(
                        sample_idx=sample_idx,
                        hub=hub,
                        source_memory=source_memory,
                        target_memory=str(target.get("content", "")),
                        bfs_reached=True,
                        attr_reached=False,
                    ))
        for hub, attr_trace in attr_traces.items():
            bfs_affected = _affected_by_id(bfs_traces.get(hub, {}))
            attr_affected = _affected_by_id(attr_trace)
            source_memory = str(attr_trace.get("trigger_content", ""))
            for memory_id, target in attr_affected.items():
                key = (sample_idx, hub, memory_id)
                if key in seen_reached:
                    continue
                seen_reached.add(key)
                reached_candidates.append(make_audit_item(
                    sample_idx=sample_idx,
                    hub=hub,
                    source_memory=source_memory,
                    target_memory=str(target.get("content", "")),
                    bfs_reached=memory_id in bfs_affected,
                    attr_reached=True,
                ))
    blocked_items = _round_robin_by_group(blocked_candidates, max_items_per_bucket)
    reached_items = _round_robin_by_group(reached_candidates, max_items_per_bucket)
    return blocked_items + reached_items


def _round_robin_by_group(
    items: list[dict[str, Any]],
    max_items: int,
) -> list[dict[str, Any]]:
    """Select items across sample/hub groups before taking extras from any one group."""
    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for item in items:
        key = (int(item.get("sample_idx", -1)), str(item.get("hub", "")))
        groups.setdefault(key, []).append(item)

    selected = []
    keys = sorted(groups)
    while len(selected) < max_items and any(groups.values()):
        for key in keys:
            if not groups[key]:
                continue
            selected.append(groups[key].pop(0))
            if len(selected) >= max_items:
                break
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--max-items-per-bucket", type=int, default=50)
    args = parser.parse_args()
    if args.result_json:
        result = json.loads(args.result_json.read_text())
        items = sample_audit_items(result, args.max_items_per_bucket)
        args.output.write_text(json.dumps(items, indent=2) + "\n")
    else:
        write_template(args.output)


if __name__ == "__main__":
    main()
