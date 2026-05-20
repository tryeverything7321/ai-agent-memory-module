from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.preprint_config import load_experiment_config, write_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate preprint experiment config and write a run manifest."
    )
    parser.add_argument(
        "--config",
        default="experiments/configs/preprint_smoke.json",
        help="Path to JSON experiment config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate config and write manifest. Does not run MemoryAgentBench.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_experiment_config(args.config)
    manifest_path = write_manifest(
        config,
        command=sys.argv,
        dry_run=args.dry_run,
    )

    print(f"Experiment: {config.experiment_name}")
    print(
        "Dataset: "
        f"{config.dataset.name} / {config.dataset.split} / "
        f"{config.dataset.sub_dataset}"
    )
    print(
        "Hub selection: "
        f"top_k={config.hub_selection.top_k}, "
        "named_entity_only="
        f"{config.hub_selection.named_entity_only}, "
        "exclude_stopwords_pronouns="
        f"{config.hub_selection.exclude_stopwords_pronouns}"
    )
    print(f"Policies: {', '.join(config.policies)}")
    print(f"Metrics: {', '.join(config.metrics)}")
    print(f"Manifest: {manifest_path}")

    if not args.dry_run:
        print(
            "This setup command only validates configuration. "
            "Use the dedicated experiment runner for full runs."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
