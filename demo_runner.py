"""데모 러너 — 합성 대화 120턴을 Real LLM + Real Embedding으로 실행

사용법:
    PYTHONPATH=. python demo_runner.py

출력:
    data/demo_results.json
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from config import settings
from extraction import Extractor
from llm_client import DooGPULLMClient
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.vector_store import VectorStore, DooGPUEmbeddingProvider
from api.routes import MemoryService
from prediction.intent import IntentClassifier

# --- DooGPU 설정 ---
DOOGPU_LLM_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-9ffd545a-87ed-47ce-92d4-8171856ca014/reserved3/v1"
)
DOOGPU_EMBED_BASE = (
    "https://doogpu.doosan.com/standard/workspace/"
    "ws-94c8469a-43a7-4573-a455-2926fa446865/workload/"
    "wl-9ffd545a-87ed-47ce-92d4-8171856ca014/reserved9/v1"
)
LLM_MODEL = "google/gemma-4-31B-it"
EMBED_MODEL = "BAAI/bge-m3"

DATA_PATH = Path(__file__).parent / "data" / "synthetic_conversations.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "demo_results.json"


async def run_demo():
    # --- 데이터 로드 ---
    with open(DATA_PATH) as f:
        data = json.load(f)
    sessions = data["sessions"]

    # --- 서비스 초기화 ---
    llm = DooGPULLMClient(base_url=DOOGPU_LLM_BASE, model=LLM_MODEL, api_key="EMPTY")
    embedding = DooGPUEmbeddingProvider(
        base_url=DOOGPU_EMBED_BASE, model=EMBED_MODEL, api_key="EMPTY"
    )
    metadata = MetadataStore(db_path=":memory:")
    await metadata.initialize()
    graph = GraphStore(metadata_store=metadata)
    vector = VectorStore(embedding_provider=embedding, use_qdrant=False)
    await vector.initialize()
    extractor = Extractor(llm_client=llm)

    svc = MemoryService(
        metadata_store=metadata,
        vector_store=vector,
        graph_store=graph,
        extractor=extractor,
    )
    intent_clf = IntentClassifier()

    # --- 실행 ---
    results = []
    total_start = time.time()
    turn_id = 0
    total_user_turns = sum(
        1 for s in sessions for t in s["turns"] if t["role"] == "user"
    )

    print(f"=== Demo Start: {len(sessions)} sessions, {total_user_turns} user turns ===\n")

    for si, session in enumerate(sessions):
        user_id = session["user_id"]
        session_id = session["session_id"]

        for turn in session["turns"]:
            if turn["role"] != "user":
                continue

            message = turn["content"]
            ground_truth_intent = turn.get("intent")
            t0 = time.time()

            try:
                response = await svc.process_chat(message, user_id, session_id)
                latency_ms = int((time.time() - t0) * 1000)

                # 분류된 intent
                predicted_intent = svc._last_intent.get(user_id, "unknown")

                # 추출된 fact 수
                memories = await metadata.get_memories_by_user(user_id)
                facts_count = 0
                for m in memories:
                    if m.created_at and (time.time() - t0) < 5:
                        facts_count += len(m.facts) if m.facts else 1

                # dedup 확인: 이전 턴 메모리 수 vs 현재
                dedup_hit = False  # 간이 판별: response에서 추적

                # 예측 정보
                prediction_info = None
                if response.prediction:
                    prediction_info = {
                        "next_intent": response.prediction.predicted_next.value,
                        "weight": round(response.prediction.transition_weight, 3),
                    }

                turn_result = {
                    "turn_id": turn_id,
                    "session_idx": si,
                    "user_id": user_id,
                    "message": message,
                    "timestamp": turn.get("timestamp"),
                    "ground_truth_intent": ground_truth_intent,
                    "classified_intent": predicted_intent,
                    "memories_found": len(response.memories_used),
                    "prediction": prediction_info,
                    "latency_ms": latency_ms,
                    "response_preview": response.response[:200],
                }
                results.append(turn_result)

                status = "OK"
                if prediction_info:
                    status += f" pred={prediction_info['next_intent']}({prediction_info['weight']:.2f})"

                print(
                    f"  [{turn_id+1}/{total_user_turns}] {user_id}: "
                    f"\"{message[:40]}\" → {predicted_intent} "
                    f"| mem={len(response.memories_used)} "
                    f"| {latency_ms}ms | {status}"
                )

            except Exception as e:
                latency_ms = int((time.time() - t0) * 1000)
                turn_result = {
                    "turn_id": turn_id,
                    "session_idx": si,
                    "user_id": user_id,
                    "message": message,
                    "timestamp": turn.get("timestamp"),
                    "ground_truth_intent": ground_truth_intent,
                    "classified_intent": None,
                    "memories_found": 0,
                    "prediction": None,
                    "latency_ms": latency_ms,
                    "error": str(e),
                }
                results.append(turn_result)
                print(f"  [{turn_id+1}/{total_user_turns}] ERROR: {e}")

            turn_id += 1

    total_duration = time.time() - total_start

    # --- 최종 메모리 통계 ---
    all_memories = {}
    for uid in ["user_pm", "user_dev", "user_new"]:
        mems = await metadata.get_memories_by_user(uid)
        all_memories[uid] = [
            {
                "id": m.id,
                "content": m.content,
                "importance": m.importance.value,
                "access_count": m.access_count,
            }
            for m in mems
        ]

    # --- Intent transition graph ---
    transitions = {}
    for u, v, d in graph.intent_graph.edges(data=True):
        key = f"{u} -> {v}"
        transitions[key] = round(d.get("weight", 0), 3)

    # --- 결과 저장 ---
    output = {
        "meta": {
            "total_turns": turn_id,
            "total_sessions": len(sessions),
            "duration_sec": round(total_duration, 1),
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in results) / len(results), 1
            ),
            "llm_model": LLM_MODEL,
            "embedding_model": EMBED_MODEL,
            "timestamp": datetime.now().isoformat(),
        },
        "turns": results,
        "final_state": {
            "memories_per_user": {
                uid: len(mems) for uid, mems in all_memories.items()
            },
            "memories_detail": all_memories,
            "intent_transitions": transitions,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # --- 요약 ---
    errors = sum(1 for r in results if "error" in r)
    predictions = [r for r in results if r.get("prediction")]
    mem_found = [r for r in results if r["memories_found"] > 0]

    print(f"\n=== Demo Complete ===")
    print(f"  Turns: {turn_id} ({errors} errors)")
    print(f"  Duration: {total_duration:.1f}s (avg {output['meta']['avg_latency_ms']:.0f}ms/turn)")
    print(f"  Memories: {sum(len(m) for m in all_memories.values())} total")
    for uid, mems in all_memories.items():
        print(f"    {uid}: {len(mems)}")
    print(f"  Predictions made: {len(predictions)}")
    print(f"  Turns with memories: {len(mem_found)}/{turn_id}")
    print(f"  Transitions: {len(transitions)}")
    print(f"\n  Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(run_demo())
