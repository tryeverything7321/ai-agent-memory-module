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
    elif bfs_reached and attr_reached:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_template(args.output)


if __name__ == "__main__":
    main()
