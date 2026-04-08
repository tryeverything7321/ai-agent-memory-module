"""장기 시뮬레이션 러너 — 500+ turns, Mitosis/Extinction 검증

v2 MemoryService 통합 파이프라인 사용:
  - use_taxonomy=True → Bootstrap → Evolution 자동 전환
  - TaxonomyPersistence로 중간 상태 저장
  - Decay sweep 결과에서 Mitosis/Extinction 이벤트 추적

사용법:
    PYTHONPATH=. python demo_runner_v2_long.py

출력:
    data/demo_results_v2_long.json
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
from taxonomy.persistence import TaxonomyPersistence

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

DATA_PATH = Path(__file__).parent / "data" / "long_simulation.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "demo_results_v2_long.json"
PERSIST_DIR = Path(__file__).parent / "data" / "taxonomy_long"


async def run_long_simulation():
    # --- 데이터 로드 ---
    with open(DATA_PATH) as f:
        data = json.load(f)
    sessions = data["sessions"]
    meta = data["metadata"]

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

    # --- v2 MemoryService (통합 모드) ---
    svc = MemoryService(
        metadata_store=metadata,
        vector_store=vector,
        graph_store=graph,
        extractor=extractor,
        use_taxonomy=True,
        llm_client=llm,
        embedding_provider=embedding,
    )

    # --- Persistence ---
    persistence = TaxonomyPersistence(base_dir=PERSIST_DIR)
    # 항상 처음부터 실행 (clean run)
    if persistence.exists():
        print("  >>> 기존 taxonomy 상태 발견 — clean run이므로 무시합니다.")

    # --- user turns 추출 ---
    all_user_turns = []
    for si, session in enumerate(sessions):
        for turn in session["turns"]:
            if turn["role"] == "user":
                all_user_turns.append({
                    "session_idx": si,
                    "user_id": session["user_id"],
                    "session_id": session["session_id"],
                    **turn,
                })

    total_user_turns = len(all_user_turns)
    print(f"\n=== Long Simulation Start: {len(sessions)} sessions, {total_user_turns} user turns ===")
    print(f"    Users: {meta['users']}")
    print(f"    Duration: {meta['duration_days']} days")
    print(f"    Phases: {json.dumps(meta['phases'], ensure_ascii=False, indent=6)}\n")

    # --- 실행 ---
    results = []
    evolution_log = []
    bootstrap_logged = False
    total_start = time.time()

    for turn_id, turn_data in enumerate(all_user_turns):
        message = turn_data["content"]
        user_id = turn_data["user_id"]
        session_id = turn_data["session_id"]
        ground_truth_intent = turn_data.get("intent")
        t0 = time.time()

        try:
            response = await svc.process_chat(message, user_id, session_id)
            latency_ms = int((time.time() - t0) * 1000)

            # v1/v2 분류 결과
            v1_intent = svc._last_intent.get(user_id, "unknown")

            # 예측 정보
            prediction_info = None
            if response.prediction:
                prediction_info = {
                    "next_intent": response.prediction.predicted_next.value,
                    "weight": round(response.prediction.transition_weight, 3),
                }

            # v2 분류 결과 캡처
            v2_classified = svc._last_v2_category.get(user_id)

            # taxonomy 상태 스냅샷
            taxonomy_snapshot = None
            if svc.evolver:
                cats = svc.evolver.taxonomy.get_all_categories()
                taxonomy_snapshot = {
                    "total_categories": len(cats),
                    "categories": {c["name"]: c["member_count"] for c in cats},
                }

            turn_result = {
                "turn_id": turn_id,
                "user_id": user_id,
                "message": message,
                "timestamp": turn_data.get("timestamp"),
                "ground_truth_intent": ground_truth_intent,
                "v1_classified": v1_intent,
                "v2_classified": v2_classified,
                "memories_found": len(response.memories_used),
                "prediction": prediction_info,
                "latency_ms": latency_ms,
            }
            results.append(turn_result)

            # 진행 상태 (50턴마다)
            if (turn_id + 1) % 50 == 0 or turn_id == 0:
                v2_tag = v2_classified or "?"
                print(f"  [{turn_id+1}/{total_user_turns}] {user_id}: "
                      f"\"{message[:35]}\" | v1:{v1_intent} v2:{v2_tag} "
                      f"| mem={len(response.memories_used)} | {latency_ms}ms")

            # --- Evolution 이벤트 감지 ---
            if svc.evolver:
                ev = svc.evolver

                # Bootstrap 완료 감지
                if not bootstrap_logged and svc.taxonomy_ready:
                    bootstrap_cats = ev.taxonomy.get_all_categories()
                    evolution_log.append({
                        "turn_id": turn_id,
                        "event": "bootstrap_complete",
                        "categories": [c["name"] for c in bootstrap_cats],
                        "category_sizes": {c["name"]: c["member_count"] for c in bootstrap_cats},
                        "ephemeral_count": len(svc._ephemeral_patterns or []),
                    })
                    bootstrap_logged = True
                    print(f"\n  >>> Bootstrap 완료: {len(bootstrap_cats)} categories")

        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            results.append({
                "turn_id": turn_id,
                "user_id": user_id,
                "message": message,
                "ground_truth_intent": ground_truth_intent,
                "latency_ms": latency_ms,
                "error": str(e),
            })
            print(f"  [ERR] [{turn_id+1}] {user_id}: {e}")

        # --- Persistence: 100턴마다 저장 ---
        if svc.evolver and (turn_id + 1) % 100 == 0:
            persistence.save(
                svc.evolver.taxonomy,
                svc.evolver.lineage,
                svc._ephemeral_patterns,
                turn_count=turn_id + 1,
            )
            cats = svc.evolver.taxonomy.get_all_categories()
            print(f"\n  >>> State saved @turn {turn_id+1}: {len(cats)} categories")
            for c in cats:
                print(f"      - {c['name']}: {c['member_count']} members, "
                      f"weight={c['decay_weight']:.3f}")
            print()

    total_duration = time.time() - total_start

    # --- 최종 상태 ---
    taxonomy_final = {}
    lineage_summary = {}

    if svc.evolver:
        cats = svc.evolver.taxonomy.get_all_categories()
        taxonomy_final = {
            "categories": [
                {
                    "name": c["name"],
                    "member_count": c["member_count"],
                    "decay_weight": round(c["decay_weight"], 4),
                    "access_count": c["access_count"],
                    "created_by": c["created_by"],
                }
                for c in cats
            ],
            "total_categories": len(cats),
        }

        lineage_summary = svc.evolver.lineage.get_summary()
        lineage_summary["events"] = svc.evolver.lineage.get_events()

        # 최종 저장
        persistence.save(
            svc.evolver.taxonomy,
            svc.evolver.lineage,
            svc._ephemeral_patterns,
            turn_count=len(all_user_turns),
        )

    # 메모리 통계
    mem_per_user = {}
    for uid in meta["users"]:
        mems = await metadata.get_memories_by_user(uid)
        mem_per_user[uid] = len(mems)

    # --- 결과 저장 ---
    output = {
        "meta": {
            "version": "v2-long",
            "total_turns": len(all_user_turns),
            "total_sessions": len(sessions),
            "users": meta["users"],
            "duration_sec": round(total_duration, 1),
            "duration_days": meta["duration_days"],
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in results) / max(len(results), 1), 1
            ),
            "llm_model": LLM_MODEL,
            "embedding_model": EMBED_MODEL,
            "timestamp": datetime.now().isoformat(),
        },
        "turns": results,
        "taxonomy": taxonomy_final,
        "lineage": lineage_summary,
        "evolution_log": evolution_log,
        "ephemeral_patterns": svc._ephemeral_patterns or [],
        "final_state": {
            "memories_per_user": mem_per_user,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # --- 요약 ---
    errors = sum(1 for r in results if "error" in r)
    predictions = [r for r in results if r.get("prediction")]
    mem_found = [r for r in results if r.get("memories_found", 0) > 0]

    print(f"\n{'='*60}")
    print(f"=== Long Simulation Complete ===")
    print(f"  Turns: {len(all_user_turns)} ({errors} errors)")
    print(f"  Duration: {total_duration:.1f}s (avg {output['meta']['avg_latency_ms']:.0f}ms/turn)")

    if taxonomy_final:
        print(f"\n  --- Final Taxonomy ({taxonomy_final['total_categories']} categories) ---")
        for c in taxonomy_final["categories"]:
            print(f"    {c['name']}: {c['member_count']} members, "
                  f"weight={c['decay_weight']:.3f}, by={c['created_by']}")

    if lineage_summary:
        print(f"\n  --- Lineage ---")
        for k, v in lineage_summary.get("event_counts", {}).items():
            print(f"    {k}: {v}")

    print(f"\n  --- Memories ---")
    for uid, count in mem_per_user.items():
        print(f"    {uid}: {count}")
    print(f"  Predictions: {len(predictions)}/{len(all_user_turns)}")
    print(f"  Turns with memories: {len(mem_found)}/{len(all_user_turns)}")
    print(f"\n  Output: {OUTPUT_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(run_long_simulation())
