from __future__ import annotations

import argparse
import json
from pathlib import Path


def inject_phrase_into_context(
    context: str,
    phrase: str,
    repetitions: int,
) -> str:
    if repetitions <= 0:
        return context
    lines = context.splitlines()
    injected = []
    remaining = repetitions
    for line in lines:
        if line.strip() and remaining > 0:
            injected.append(f"{phrase}: {line}")
            remaining -= 1
        else:
            injected.append(line)
    while remaining > 0:
        injected.append(f"{phrase}: synthetic reminder {remaining}")
        remaining -= 1
    return "\n".join(injected)


def load_context(sub_dataset: str, sample_idx: int) -> str:
    from datasets import load_dataset

    raw = load_dataset(
        "ai-hyz/MemoryAgentBench",
        split="Accurate_Retrieval",
        revision="main",
    )
    filtered = [
        sample for sample in raw
        if sample.get("metadata", {}).get("source", "") == sub_dataset
    ]
    return filtered[sample_idx]["context"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub_dataset", default="eventqa_65536")
    parser.add_argument("--sample_idx", type=int, default=0)
    parser.add_argument("--phrase", required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    context = load_context(args.sub_dataset, args.sample_idx)
    injected = inject_phrase_into_context(context, args.phrase, args.repetitions)
    args.output.write_text(json.dumps({
        "sub_dataset": args.sub_dataset,
        "sample_idx": args.sample_idx,
        "phrase": args.phrase,
        "repetitions": args.repetitions,
        "original_chars": len(context),
        "injected_chars": len(injected),
        "phrase_count": injected.count(args.phrase),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
