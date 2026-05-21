from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.preprint_hubs import select_actionable_hubs


def flatten_haystack_messages(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    def visit(node: Any, session_idx: int | None = None) -> None:
        if isinstance(node, dict):
            if "content" in node and "role" in node:
                msg = dict(node)
                msg["session_idx"] = session_idx
                messages.append(msg)
            return
        if isinstance(node, list):
            next_session_idx = session_idx
            if node and isinstance(node[0], str) and node[0].startswith("Chat Time:"):
                next_session_idx = len({m.get("session_idx") for m in messages})
            for item in node:
                visit(item, next_session_idx)

    visit(metadata.get("haystack_sessions", []))
    return messages


def build_structured_context(sample: dict[str, Any], mode: str) -> str:
    if mode == "raw_context":
        return str(sample["context"])

    messages = flatten_haystack_messages(sample.get("metadata", {}))
    if mode == "content_turns":
        selected = messages
    elif mode == "user_turns":
        selected = [m for m in messages if m.get("role") == "user"]
    elif mode == "answer_turns":
        selected = [m for m in messages if m.get("has_answer")]
    elif mode == "answer_session_user_turns":
        answer_sessions = {
            m.get("session_idx") for m in messages if m.get("has_answer")
        }
        selected = [
            m for m in messages
            if m.get("role") == "user" and m.get("session_idx") in answer_sessions
        ]
    else:
        raise ValueError(f"Unknown structured context mode: {mode}")

    lines = []
    for idx, message in enumerate(selected, start=1):
        content = clean_turn_text(str(message.get("content", "")))
        if content:
            lines.append(f"{idx}. {content}")
    return "\n".join(lines)


def clean_turn_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^\*\*[^*]+:\*\*\s*", "", text)
    text = re.sub(r"^\d+\.\s+", "", text)
    return text


async def analyze_context(context: str, top_k: int) -> dict[str, Any]:
    return analyze_context_fast(context, top_k)


def analyze_context_fast(context: str, top_k: int) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = {}
    subjects: set[str] = set()
    lines = [line.strip() for line in context.splitlines() if line.strip()]

    for line in lines:
        entities = extract_entities_rule_based_fast(line)
        if not entities:
            continue
        subjects.add(entities[0])
        for entity in entities:
            adjacency.setdefault(entity, set())
        for idx, left in enumerate(entities):
            for right in entities[idx + 1:]:
                if left == right:
                    continue
                adjacency[left].add(right)
                adjacency[right].add(left)

    raw_hubs = sorted(
        (
            {"entity": entity, "degree": len(neighbors)}
            for entity, neighbors in adjacency.items()
        ),
        key=lambda hub: hub["degree"],
        reverse=True,
    )
    filtered = select_actionable_hubs(
        raw_hubs,
        top_k=top_k,
        has_trigger_fact=lambda entity: entity in subjects,
    )
    return {
        "n_lines": len(lines),
        "raw_top_hubs": raw_hubs[:top_k],
        "filtered_hubs": filtered,
        "n_filtered_hubs": len(filtered),
    }


def extract_entities_rule_based_fast(text: str) -> list[str]:
    entities = []
    seen = set()
    proper_nouns = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
    for noun in proper_nouns:
        if noun.lower() in {"the", "a", "an", "is", "was", "are", "were", "has", "have"}:
            continue
        if noun not in seen:
            entities.append(noun)
            seen.add(noun)

    of_pattern = re.findall(
        r"the\s+(\w+)\s+of\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)", text
    )
    for _attr, entity in of_pattern:
        if entity not in seen:
            entities.append(entity)
            seen.add(entity)
    return entities


async def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    from datasets import load_dataset

    raw = load_dataset(
        "ai-hyz/MemoryAgentBench", split="Accurate_Retrieval", revision="main"
    )
    samples = [
        sample for sample in raw
        if sample.get("metadata", {}).get("source", "") == args.sub_dataset
    ][: args.max_samples]

    results = []
    for sample_idx, sample in enumerate(samples):
        per_mode = {}
        for mode in args.modes:
            context = build_structured_context(sample, mode)
            per_mode[mode] = await analyze_context(context, args.top_k)
        results.append({"sample_idx": sample_idx, "modes": per_mode})

    output = {
        "config": {
            "sub_dataset": args.sub_dataset,
            "max_samples": args.max_samples,
            "top_k": args.top_k,
            "modes": args.modes,
        },
        "per_sample": results,
        "summary": summarize_gate(results, args.modes),
    }
    return output


def summarize_gate(results: list[dict[str, Any]], modes: list[str]) -> dict[str, Any]:
    summary = {}
    for mode in modes:
        counts = [
            sample["modes"][mode]["n_filtered_hubs"]
            for sample in results
        ]
        summary[mode] = {
            "samples": len(counts),
            "samples_with_filtered_hub": sum(1 for count in counts if count > 0),
            "avg_filtered_hubs": (
                sum(counts) / len(counts) if counts else 0.0
            ),
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub_dataset", default="longmemeval_s*")
    parser.add_argument("--max_samples", type=int, default=5)
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=[
            "raw_context",
            "content_turns",
            "user_turns",
            "answer_turns",
            "answer_session_user_turns",
        ],
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = asyncio.run(run_gate(args))
    if args.output is None:
        args.output = Path("experiments/results") / (
            f"structured_graph_gate_{args.sub_dataset}_{int(time.time())}.json"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
