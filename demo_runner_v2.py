"""데모 러너 v2 — Taxonomy Evolution + Realistic 데이터

v1 대비 변경점:
  - TaxonomyBootstrap: 첫 30 user turns → k-means 자동 클러스터링 + LLM 네이밍
  - TaxonomyEvolver: 2-stage 분류 (centroid → LLM), decay sweep, mitosis/fusion
  - PhylogeneticLineage: 전체 진화 이벤트 DAG 기록
  - 4유저 × 28일 × 200+ user turns realistic 데이터

사용법:
    PYTHONPATH=. python demo_runner_v2.py

출력:
    data/demo_results_v2.json
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
from storage.memory_index import MemoryIndex
from api.routes import MemoryService
from taxonomy.bootstrap import TaxonomyBootstrap
from taxonomy.evolver import TaxonomyEvolver
from taxonomy.lineage import PhylogeneticLineage

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

DATA_PATH = Path(__file__).parent / "data" / "realistic_conversations.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "demo_results_v2.json"


async def run_demo():
    # --- 데이터 로드 ---
    with open(DATA_PATH) as f:
        data = json.load(f)
    sessions = data["sessions"]
    metadata_info = data["metadata"]

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

    # --- Taxonomy Evolution 초기화 ---
    bootstrap = TaxonomyBootstrap(llm)
    evolver = None  # bootstrap 완료 후 생성
    lineage = None
    ephemeral_patterns = None

    # --- 실행 ---
    results = []
    evolution_log = []  # 진화 이벤트 기록
    total_start = time.time()
    turn_id = 0
    bootstrap_phase = True  # bootstrap 완료 전

    # user turns만 추출 (시간순 정렬)
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
    print(f"=== Demo v2 Start: {len(sessions)} sessions, {total_user_turns} user turns ===")
    print(f"    Users: {metadata_info['users']}")
    print(f"    Duration: {metadata_info['duration_days']} days\n")

    for turn_data in all_user_turns:
        message = turn_data["content"]
        user_id = turn_data["user_id"]
        session_id = turn_data["session_id"]
        ground_truth_intent = turn_data.get("intent")
        t0 = time.time()

        try:
            # --- 임베딩 생성 ---
            emb = await embedding.embed(message)

            # --- Phase 1: Bootstrap (첫 30턴) ---
            if bootstrap_phase:
                bootstrap.add_message(message, emb)

                if bootstrap.is_ready():
                    print(f"\n  >>> Bootstrap 시작: {bootstrap.buffer_size}개 메시지 클러스터링...")
                    taxonomy, lineage, ephemeral_patterns = await bootstrap.execute()
                    evolver = TaxonomyEvolver(taxonomy, lineage, llm, embedding)
                    bootstrap_phase = False

                    # bootstrap 결과 기록
                    cats = taxonomy.get_all_categories()
                    cat_names = [c["name"] for c in cats]
                    print(f"  >>> Bootstrap 완료: {len(cats)}개 카테고리 발견")
                    for c in cats:
                        print(f"      - {c['name']} ({c['member_count']} members)")
                    print(f"  >>> EPHEMERAL 패턴: {len(ephemeral_patterns)}개 생성")
                    print()

                    evolution_log.append({
                        "turn_id": turn_id,
                        "event": "bootstrap_complete",
                        "categories": cat_names,
                        "ephemeral_count": len(ephemeral_patterns),
                    })

                    # bootstrap 중 분류: 가장 가까운 centroid 사용
                    classified = taxonomy.get_best_match(emb)
                    classified_intent = classified or "unknown"
                else:
                    classified_intent = "buffering"
            else:
                # --- Phase 2: Evolution ---
                classified_intent, is_new = await evolver.classify_or_propose(message, emb)

                if is_new:
                    evolution_log.append({
                        "turn_id": turn_id,
                        "event": "category_discovered",
                        "category": classified_intent,
                        "trigger": message[:80],
                    })
                    print(f"  *** NEW CATEGORY: {classified_intent}")

                # 멤버 등록
                memory_id = f"mem_{turn_id}"
                await evolver.register_memory(classified_intent, memory_id, emb)

                # --- Decay Sweep 체크 ---
                if evolver.should_sweep():
                    print(f"\n  >>> Decay Sweep @turn {turn_id}...")
                    sweep_result = await evolver.decay_sweep(datetime.now())

                    if sweep_result["pruned"]:
                        print(f"      Pruned: {sweep_result['pruned']}")
                    if sweep_result["reclassified"] > 0:
                        print(f"      Reclassified: {sweep_result['reclassified']} orphans")
                    if sweep_result["splits"]:
                        for s in sweep_result["splits"]:
                            print(f"      Split: {s['parent']} → {s['children']}")
                    if sweep_result["fusions"]:
                        for f in sweep_result["fusions"]:
                            print(f"      Fusion: {f['parents']} → {f['child']}")
                    print()

                    evolution_log.append({
                        "turn_id": turn_id,
                        "event": "decay_sweep",
                        **sweep_result,
                    })

            # --- 기존 MemoryService 파이프라인 (검색 + 추출 + 저장) ---
            response = await svc.process_chat(message, user_id, session_id)
            latency_ms = int((time.time() - t0) * 1000)

            # v1 호환: 기존 rule-based intent도 기록
            v1_intent = svc._last_intent.get(user_id, "unknown")

            # 예측 정보
            prediction_info = None
            if response.prediction:
                prediction_info = {
                    "next_intent": response.prediction.predicted_next.value,
                    "weight": round(response.prediction.transition_weight, 3),
                }

            turn_result = {
                "turn_id": turn_id,
                "session_idx": turn_data["session_idx"],
                "user_id": user_id,
                "message": message,
                "timestamp": turn_data.get("timestamp"),
                "ground_truth_intent": ground_truth_intent,
                "v2_classified": classified_intent,
                "v1_classified": v1_intent,
                "memories_found": len(response.memories_used),
                "prediction": prediction_info,
                "latency_ms": latency_ms,
                "response_preview": response.response[:200],
            }
            results.append(turn_result)

            # 진행 상태 출력
            phase_tag = "[BOOT]" if classified_intent == "buffering" else "[EVOL]"
            print(
                f"  {phase_tag} [{turn_id+1}/{total_user_turns}] {user_id}: "
                f"\"{message[:35]}\" → v2:{classified_intent} v1:{v1_intent} "
                f"| mem={len(response.memories_used)} | {latency_ms}ms"
            )

        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            turn_result = {
                "turn_id": turn_id,
                "session_idx": turn_data["session_idx"],
                "user_id": user_id,
                "message": message,
                "timestamp": turn_data.get("timestamp"),
                "ground_truth_intent": ground_truth_intent,
                "v2_classified": None,
                "v1_classified": None,
                "memories_found": 0,
                "prediction": None,
                "latency_ms": latency_ms,
                "error": str(e),
            }
            results.append(turn_result)
            print(f"  [ERR] [{turn_id+1}/{total_user_turns}] {user_id}: {e}")

        turn_id += 1

    total_duration = time.time() - total_start

    # --- 최종 상태 수집 ---
    # Taxonomy 최종 상태
    taxonomy_final = {}
    if evolver:
        cats = evolver.taxonomy.get_all_categories()
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

    # Lineage 요약
    lineage_summary = {}
    if lineage:
        lineage_summary = lineage.get_summary()
        lineage_summary["events"] = lineage.get_events()

    # 메모리 통계
    all_memories = {}
    for uid in metadata_info["users"]:
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

    # Intent transition graph
    transitions = {}
    for u, v, d in graph.intent_graph.edges(data=True):
        key = f"{u} -> {v}"
        transitions[key] = round(d.get("weight", 0), 3)

    # --- 결과 저장 ---
    output = {
        "meta": {
            "version": "v2",
            "total_turns": turn_id,
            "total_sessions": len(sessions),
            "users": metadata_info["users"],
            "duration_sec": round(total_duration, 1),
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
        "ephemeral_patterns": ephemeral_patterns or [],
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

    print(f"\n{'='*60}")
    print(f"=== Demo v2 Complete ===")
    print(f"  Turns: {turn_id} ({errors} errors)")
    print(f"  Duration: {total_duration:.1f}s (avg {output['meta']['avg_latency_ms']:.0f}ms/turn)")

    if taxonomy_final:
        print(f"\n  --- Taxonomy ---")
        print(f"  Final categories: {taxonomy_final['total_categories']}")
        for c in taxonomy_final["categories"]:
            print(f"    {c['name']}: {c['member_count']} members, "
                  f"weight={c['decay_weight']:.3f}, access={c['access_count']}, "
                  f"by={c['created_by']}")

    if lineage_summary:
        print(f"\n  --- Lineage ---")
        print(f"  Total events: {lineage_summary.get('total_events', 0)}")
        for k, v in lineage_summary.get("event_counts", {}).items():
            print(f"    {k}: {v}")

    print(f"\n  --- Evolution Events ---")
    for evt in evolution_log:
        print(f"    Turn {evt['turn_id']}: {evt['event']}")

    print(f"\n  --- Memories ---")
    for uid, mems in all_memories.items():
        print(f"    {uid}: {len(mems)}")

    print(f"  Predictions made: {len(predictions)}")
    print(f"  Turns with memories: {len(mem_found)}/{turn_id}")

    if ephemeral_patterns:
        print(f"\n  --- EPHEMERAL Patterns ({len(ephemeral_patterns)}) ---")
        print(f"    {ephemeral_patterns[:10]}...")

    print(f"\n  Output: {OUTPUT_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(run_demo())
