# AI Agent Memory Module

Long-term memory infrastructure for agentic assistants: hybrid retrieval, graph-backed context, memory decay, and proactive context prediction.

This repository contains two related tracks:

1. **Engineering prototype** — a FastAPI memory service for assistant-style applications.
2. **Research track** — experiments on graph-based memory invalidation and collateral forgetting, prepared for an ICML 2026 SCALE workshop submission.

## Why This Exists

Most conversational AI systems either keep too much raw history in context or forget useful user-specific information too aggressively. This project explores a structured memory layer that can:

- extract facts, entities, and relations from conversations,
- store them across vector, graph, and metadata indexes,
- decay stale memories over time,
- predict likely next contexts from intent transitions,
- evaluate failure modes in graph-based memory invalidation.

The goal is not just better retrieval. The goal is a memory system that can be inspected, updated, forgotten, and evaluated.

## System Overview

```text
User message
    |
    v
Intent classification
    |
    +--> Hybrid retrieval
    |      - Vector search
    |      - Graph neighbors
    |      - Metadata filters
    |
    +--> Proactive context prediction
    |      - intent transition graph
    |
    +--> Async extraction
           - facts
           - entities
           - relations
    |
    v
Memory response + predicted context
```

## Architecture

| Layer | Responsibility |
|------|----------------|
| Extraction | Extract facts, entities, and relations from messages |
| Storage | Persist memories in vector, graph, and metadata stores |
| Decay | Apply importance-aware forgetting curves |
| Prediction | Predict likely next context using intent transitions |
| Taxonomy | Evolve user/domain categories from observed data |
| Evaluation | Measure retrieval quality, taxonomy behavior, and forgetting damage |

## Key Features

- **Hybrid retrieval:** vector + graph + metadata search with rank fusion.
- **Memory decay:** Ebbinghaus-style decay with different rates by memory importance.
- **Deduplication:** embedding similarity based duplicate detection and access-count updates.
- **Intent transition prediction:** proactive context injection from transition probabilities.
- **Self-evolving taxonomy:** dynamic category discovery, mitosis, fusion, and extinction.
- **User isolation:** request-level namespace support through user identifiers.
- **Research evaluation:** experiments for graph invalidation, propagation damage, and dependency-aware filtering.

## Repository Structure

```text
.
├── api/                 # FastAPI routes and service integration
├── storage/             # Vector, graph, metadata stores and retrieval fusion
├── prediction/          # Intent classification and proactive prediction
├── taxonomy/            # Self-evolving taxonomy graph and persistence
├── data/                # Synthetic and long-horizon simulation data
├── docs/                # Analysis reports and benchmark notes
├── paper/               # Research paper workspace
├── tests/               # Unit and integration tests
├── main.py              # FastAPI entrypoint
├── models.py            # Pydantic domain models
├── extraction.py        # Memory extraction pipeline
├── decay.py             # Forgetting curve implementation
└── docker-compose.yml   # Qdrant + app services
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI, Uvicorn |
| Vector DB | Qdrant |
| Graph | NetworkX |
| Metadata | SQLite |
| Validation | Pydantic |
| LLM interface | OpenAI-compatible local LLM endpoint |
| Embeddings | OpenAI-compatible embedding endpoint |
| Experiments | NumPy, scikit-learn |
| Tests | pytest, pytest-asyncio |

## Quick Start

Requirements:

- Python 3.10+
- Docker, if you want to run Qdrant locally
- OpenAI-compatible LLM and embedding endpoints for LLM-backed demos

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

docker compose up -d qdrant
uvicorn main:app --reload
```

Set environment variables for local or remote model endpoints:

```env
MEMORY_QDRANT_HOST=localhost
MEMORY_QDRANT_PORT=6333
MEMORY_SQLITE_PATH=memory.db
MEMORY_LLM_BASE_URL=http://localhost:8080/v1
MEMORY_EMBEDDING_BASE_URL=http://localhost:8080/v1
```

Run tests:

```bash
pytest tests/ -v
```

Run demo pipelines:

```bash
PYTHONPATH=. python data/generate_synthetic.py
PYTHONPATH=. python demo_runner.py
PYTHONPATH=. python analyze_results.py

PYTHONPATH=. python data/generate_realistic.py
PYTHONPATH=. python demo_runner_v2.py
PYTHONPATH=. python analyze_results_v2.py

PYTHONPATH=. python data/generate_long_simulation.py
PYTHONPATH=. python demo_runner_v2_long.py
```

## Research Track

The research track studies a failure mode in graph-based agent memory: when memory invalidation propagates over co-occurrence graphs, unrelated memories can be damaged through high-degree hub entities.

Core claim:

> Co-occurrence is not dependency. Unfiltered propagation over entity co-occurrence graphs can create collateral forgetting through hub entities. Dependency-aware propagation can reduce this damage without calling an LLM at propagation time.

Useful entry points:

- [`paper/`](paper/) — paper workspace
- [`paper/submission_logic_summary.md`](paper/submission_logic_summary.md) — argument and reviewer-facing summary
- [`docs/benchmark_report_v3.md`](docs/benchmark_report_v3.md) — benchmark notes
- [`docs/paper_contribution_summary.md`](docs/paper_contribution_summary.md) — contribution summary

## What I Would Improve Next

- Replace in-memory graph persistence with a production graph store or a normalized relational model.
- Add CI for unit tests and lightweight integration checks.
- Add API examples for memory write, retrieval, decay, and proactive prediction.
- Split the engineering prototype and research paper into clearer release tracks if the project grows.

## License

Apache-2.0
