from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    split: str
    sub_dataset: str
    max_samples: int
    max_queries: int


@dataclass(frozen=True)
class HubSelectionConfig:
    top_k: int
    named_entity_only: bool
    exclude_stopwords_pronouns: bool


@dataclass(frozen=True)
class ModelConfig:
    llm_model: str
    embedding_model: str


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    dataset: DatasetConfig
    hub_selection: HubSelectionConfig
    policies: list[str]
    metrics: list[str]
    models: ModelConfig
    output_dir: Path


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"`{key}` must be an object")
    return value


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"`{key}` must be a non-empty string")
    return value


def _require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"`{key}` must be a positive integer")
    return value


def _require_str_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError(f"`{key}` must be a non-empty list of strings")
    return value


def _require_bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"`{key}` must be a boolean")
    return value


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("experiment config must be a JSON object")

    dataset_raw = _require_mapping(raw, "dataset")
    hub_raw = _require_mapping(raw, "hub_selection")
    models_raw = _require_mapping(raw, "models")

    hub_selection = HubSelectionConfig(
        top_k=_require_int(hub_raw, "top_k"),
        named_entity_only=_require_bool(hub_raw, "named_entity_only"),
        exclude_stopwords_pronouns=_require_bool(
            hub_raw, "exclude_stopwords_pronouns"
        ),
    )

    if not hub_selection.named_entity_only:
        raise ValueError(
            "headline hub experiments must use named-entity hub selection"
        )
    if not hub_selection.exclude_stopwords_pronouns:
        raise ValueError(
            "headline hub experiments must exclude stopwords and pronouns"
        )

    return ExperimentConfig(
        experiment_name=_require_str(raw, "experiment_name"),
        dataset=DatasetConfig(
            name=_require_str(dataset_raw, "name"),
            split=_require_str(dataset_raw, "split"),
            sub_dataset=_require_str(dataset_raw, "sub_dataset"),
            max_samples=_require_int(dataset_raw, "max_samples"),
            max_queries=_require_int(dataset_raw, "max_queries"),
        ),
        hub_selection=hub_selection,
        policies=_require_str_list(raw, "policies"),
        metrics=_require_str_list(raw, "metrics"),
        models=ModelConfig(
            llm_model=_require_str(models_raw, "llm_model"),
            embedding_model=_require_str(models_raw, "embedding_model"),
        ),
        output_dir=Path(_require_str(raw, "output_dir")),
    )


def make_run_id(experiment_name: str, timestamp: datetime | None = None) -> str:
    ts = timestamp or datetime.now(timezone.utc)
    return f"{experiment_name}_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def _config_to_dict(config: ExperimentConfig) -> dict[str, Any]:
    data = asdict(config)
    data["output_dir"] = str(config.output_dir)
    return data


def _safe_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return {}
    blocked_fragments = ("url", "token", "key", "secret", "password")
    return {
        key: value
        for key, value in extra.items()
        if not any(fragment in key.lower() for fragment in blocked_fragments)
    }


def to_manifest_dict(
    config: ExperimentConfig,
    command: list[str],
    dry_run: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc)
    return {
        "experiment_name": config.experiment_name,
        "run_id": make_run_id(config.experiment_name, created_at),
        "created_at_utc": created_at.isoformat(),
        "git_commit": get_git_commit(),
        "command": command,
        "dry_run": dry_run,
        "config": _config_to_dict(config),
        "extra": _safe_extra(extra),
        "outputs": [],
    }


def write_manifest(
    config: ExperimentConfig,
    command: list[str],
    dry_run: bool,
    extra: dict[str, Any] | None = None,
) -> Path:
    manifest = to_manifest_dict(config, command=command, dry_run=dry_run, extra=extra)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{manifest['run_id']}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path
