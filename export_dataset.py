"""실험 결과를 정량 데이터셋으로 내보내기

입력: data/demo_results_v2.json 또는 data/demo_results_v2_long.json
출력:
  data/dataset/
  ├── turns.csv           — Turn-by-turn 정량 메트릭 (메인 데이터셋)
  ├── evolution_events.csv — Taxonomy 진화 이벤트 로그
  ├── category_final.csv  — 최종 카테고리 상태
  ├── memory_stats.csv    — 유저별 메모리 통계
  ├── summary.json        — 전체 실험 요약 (정량 지표)
  └── README_dataset.md   — 데이터셋 설명

사용법:
    PYTHONPATH=. python export_dataset.py                         # v2 198턴
    PYTHONPATH=. python export_dataset.py data/demo_results_v2_long.json  # 624턴
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# --- Semantic mapping (analyze_results_v2.py와 동일) ---
SEMANTIC_MAP = {
    "scheduling": {"schedule_management", "team_collaboration", "team_meeting_prep",
                    "strategic_planning", "task_ops_management", "ops_schedule_management",
                    "schedule_management", "strategic_tech_ops", "task_status"},
    "issue_tracking": {"issue_tracking", "bug_resolution", "bug_tracking"},
    "code_review": {"meeting_preparation", "code_review", "team_meeting_prep",
                     "dev_ops_request", "technical_consulting", "tech_ops_consulting"},
    "knowledge_lookup": {"technical_discussion", "knowledge_lookup",
                          "technical_consulting", "tech_ops_consulting",
                          "strategic_tech_ops", "tech_guide"},
    "data_analysis": {"data_analysis"},
    "document_drafting": {"document_creation", "document_drafting"},
    "team_communication": {"team_communication", "team_collaboration",
                            "team_meeting_prep", "strategic_tech_ops"},
    "project_status": {"team_collaboration", "team_meeting_prep", "project_status",
                        "strategic_planning", "strategic_tech_ops", "task_status"},
    "onboarding": {"schedule_management", "team_meeting_prep", "onboarding",
                    "ops_schedule_management", "task_ops_management"},
    "weekly_report": {"weekly_report", "document_creation", "team_meeting_prep",
                       "strategic_planning", "strategic_tech_ops"},
    "meeting_prep": {"meeting_preparation", "team_meeting_prep", "meeting_prep",
                      "strategic_planning", "strategic_tech_ops"},
    "troubleshooting": {"bug_resolution", "technical_discussion", "troubleshooting",
                         "bug_tracking", "tech_ops_consulting"},
}


def semantic_match(gt: str, v2: str) -> bool:
    if gt == v2:
        return True
    return v2 in SEMANTIC_MAP.get(gt, set())


def export(input_path: str):
    with open(input_path) as f:
        data = json.load(f)

    meta = data["meta"]
    turns = data["turns"]
    taxonomy = data.get("taxonomy", {})
    lineage = data.get("lineage", {})
    evolution_log = data.get("evolution_log", [])

    version = meta.get("version", "v2")
    out_dir = Path(f"data/dataset_{version}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────
    # 1. turns.csv — Turn-by-turn 정량 메트릭
    # ──────────────────────────────────────────
    csv_path = out_dir / "turns.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "turn_id", "user_id", "message", "timestamp",
            "ground_truth", "v1_classified", "v2_classified",
            "v1_correct", "v2_exact_correct", "v2_semantic_correct",
            "memories_found", "has_prediction", "pred_intent", "pred_weight",
            "latency_ms", "has_error",
        ])

        for t in turns:
            gt = t.get("ground_truth_intent", "")
            v1 = t.get("v1_classified", "")
            v2 = t.get("v2_classified", "")
            pred = t.get("prediction")

            v1_correct = 1 if gt and gt == v1 else 0
            v2_exact = 1 if gt and gt == v2 else 0
            v2_sem = 1 if gt and v2 and semantic_match(gt, v2) else 0

            writer.writerow([
                t["turn_id"],
                t["user_id"],
                t["message"],
                t.get("timestamp", ""),
                gt or "",
                v1 or "",
                v2 or "",
                v1_correct,
                v2_exact,
                v2_sem,
                t.get("memories_found", 0),
                1 if pred else 0,
                pred["next_intent"] if pred else "",
                pred["weight"] if pred else "",
                t.get("latency_ms", 0),
                1 if "error" in t else 0,
            ])

    print(f"  turns.csv: {len(turns)} rows")

    # ──────────────────────────────────────────
    # 2. evolution_events.csv
    # ──────────────────────────────────────────
    events = lineage.get("events", [])
    csv_path = out_dir / "evolution_events.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "event_id", "timestamp", "type",
            "category", "parent", "parents", "child", "children",
            "member_count", "trigger_message", "reason",
        ])

        for i, evt in enumerate(events):
            writer.writerow([
                i,
                evt.get("timestamp", ""),
                evt["type"],
                evt.get("category", ""),
                evt.get("parent", ""),
                "|".join(evt["parents"]) if "parents" in evt else "",
                evt.get("child", ""),
                "|".join(evt.get("children", [])) if "children" in evt else "",
                evt.get("metadata", {}).get("member_count", ""),
                evt.get("metadata", {}).get("trigger_message", ""),
                evt.get("metadata", {}).get("reason", ""),
            ])

    print(f"  evolution_events.csv: {len(events)} rows")

    # ──────────────────────────────────────────
    # 3. category_final.csv
    # ──────────────────────────────────────────
    cats = taxonomy.get("categories", [])
    csv_path = out_dir / "category_final.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "category", "member_count", "decay_weight",
            "access_count", "created_by",
        ])
        for c in sorted(cats, key=lambda x: x["member_count"], reverse=True):
            writer.writerow([
                c["name"], c["member_count"],
                round(c["decay_weight"], 4),
                c["access_count"], c["created_by"],
            ])

    print(f"  category_final.csv: {len(cats)} rows")

    # ──────────────────────────────────────────
    # 4. memory_stats.csv
    # ──────────────────────────────────────────
    mem_per_user = data.get("final_state", {}).get("memories_per_user", {})
    csv_path = out_dir / "memory_stats.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "memory_count"])
        for uid, count in sorted(mem_per_user.items()):
            writer.writerow([uid, count])

    print(f"  memory_stats.csv: {len(mem_per_user)} rows")

    # ──────────────────────────────────────────
    # 5. summary.json — 정량 지표 요약
    # ──────────────────────────────────────────
    total = len(turns)
    errors = sum(1 for t in turns if "error" in t)
    valid = [t for t in turns if "error" not in t]
    latencies = [t["latency_ms"] for t in valid]
    sorted_lat = sorted(latencies)

    # 분류 정확도
    gt_turns = [t for t in turns if t.get("ground_truth_intent")]
    total_gt = len(gt_turns)

    v1_correct = sum(1 for t in gt_turns if t.get("v1_classified") == t["ground_truth_intent"])
    v2_exact = sum(1 for t in gt_turns
                   if t.get("v2_classified") and t["v2_classified"] == t["ground_truth_intent"])
    v2_semantic = sum(1 for t in gt_turns
                      if t.get("v2_classified") and semantic_match(t["ground_truth_intent"], t["v2_classified"]))

    # Prediction
    pred_turns = [t for t in turns if t.get("prediction")]
    pred_hit = sum(1 for t in pred_turns
                   if t.get("ground_truth_intent") and t["prediction"]["next_intent"] == t["ground_truth_intent"])

    # Memory
    mem_turns = [t for t in turns if t.get("memories_found", 0) > 0]

    # Taxonomy
    event_counts = lineage.get("event_counts", {})

    summary = {
        "experiment": {
            "version": version,
            "total_turns": total,
            "total_sessions": meta.get("total_sessions", 0),
            "users": meta.get("users", []),
            "duration_days": meta.get("duration_days", 0),
            "duration_sec": meta.get("duration_sec", 0),
            "llm_model": meta.get("llm_model", ""),
            "embedding_model": meta.get("embedding_model", ""),
            "errors": errors,
        },
        "classification_accuracy": {
            "total_with_ground_truth": total_gt,
            "v1_rule_based": {
                "correct": v1_correct,
                "accuracy_pct": round(v1_correct / max(total_gt, 1) * 100, 1),
            },
            "v2_exact_match": {
                "correct": v2_exact,
                "accuracy_pct": round(v2_exact / max(total_gt, 1) * 100, 1),
            },
            "v2_semantic_match": {
                "correct": v2_semantic,
                "accuracy_pct": round(v2_semantic / max(total_gt, 1) * 100, 1),
            },
        },
        "prediction": {
            "total_predictions": len(pred_turns),
            "prediction_rate_pct": round(len(pred_turns) / max(total, 1) * 100, 1),
            "hit_count": pred_hit,
            "hit_rate_pct": round(pred_hit / max(len(pred_turns), 1) * 100, 1),
        },
        "memory": {
            "total_memories": sum(mem_per_user.values()),
            "memories_per_user": mem_per_user,
            "turns_with_memories": len(mem_turns),
            "utilization_pct": round(len(mem_turns) / max(total, 1) * 100, 1),
        },
        "taxonomy_evolution": {
            "bootstrap_categories": event_counts.get("bootstrap", 0),
            "final_categories": taxonomy.get("total_categories", 0),
            "events": {
                "bootstrap": event_counts.get("bootstrap", 0),
                "discovery": event_counts.get("discovery", 0),
                "merge": event_counts.get("merge", 0),
                "split": event_counts.get("split", 0),
                "extinction": lineage.get("extinct_categories", 0),
            },
            "alive_categories": lineage.get("alive_categories", 0),
        },
        "latency": {
            "avg_ms": round(sum(latencies) / max(len(latencies), 1)),
            "p50_ms": sorted_lat[len(sorted_lat) // 2] if sorted_lat else 0,
            "p90_ms": sorted_lat[int(len(sorted_lat) * 0.9)] if sorted_lat else 0,
            "p99_ms": sorted_lat[int(len(sorted_lat) * 0.99)] if sorted_lat else 0,
            "min_ms": min(latencies) if latencies else 0,
            "max_ms": max(latencies) if latencies else 0,
        },
    }

    summary_path = out_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"  summary.json: 정량 지표 저장")

    # ──────────────────────────────────────────
    # 6. README_dataset.md
    # ──────────────────────────────────────────
    readme = f"""# Experiment Dataset — {version}

## 실험 개요

| 항목 | 값 |
|------|-----|
| 버전 | {version} |
| 총 턴 | {total} |
| 유저 | {', '.join(meta.get('users', []))} |
| 기간 | {meta.get('duration_days', '?')}일 |
| LLM | {meta.get('llm_model', '')} |
| Embedding | {meta.get('embedding_model', '')} |
| 에러 | {errors}건 |

## 파일 설명

| 파일 | 행 수 | 설명 |
|------|-------|------|
| `turns.csv` | {total} | Turn별 메시지, 분류 결과, 정확도, latency |
| `evolution_events.csv` | {len(events)} | Taxonomy 진화 이벤트 (bootstrap/discovery/merge/split/extinction) |
| `category_final.csv` | {len(cats)} | 최종 카테고리 상태 (member_count, decay_weight) |
| `memory_stats.csv` | {len(mem_per_user)} | 유저별 메모리 수 |
| `summary.json` | 1 | 전체 정량 지표 요약 |

## 주요 정량 지표

| 지표 | 값 |
|------|-----|
| v1 분류 정확도 | {summary['classification_accuracy']['v1_rule_based']['accuracy_pct']}% |
| v2 exact match | {summary['classification_accuracy']['v2_exact_match']['accuracy_pct']}% |
| v2 semantic match | {summary['classification_accuracy']['v2_semantic_match']['accuracy_pct']}% |
| Prediction 생성률 | {summary['prediction']['prediction_rate_pct']}% |
| 메모리 활용률 | {summary['memory']['utilization_pct']}% |
| Bootstrap 카테고리 | {summary['taxonomy_evolution']['bootstrap_categories']}개 |
| 최종 카테고리 | {summary['taxonomy_evolution']['final_categories']}개 |
| Fusion 횟수 | {summary['taxonomy_evolution']['events']['merge']}회 |
| Discovery 횟수 | {summary['taxonomy_evolution']['events']['discovery']}회 |
| Extinction 수 | {summary['taxonomy_evolution']['events']['extinction']}개 |
| 평균 latency | {summary['latency']['avg_ms']}ms |
| P90 latency | {summary['latency']['p90_ms']}ms |

## turns.csv 컬럼 설명

| 컬럼 | 타입 | 설명 |
|------|------|------|
| turn_id | int | 턴 순번 (0-indexed) |
| user_id | str | 유저 식별자 |
| message | str | 사용자 메시지 원문 |
| timestamp | str | ISO 8601 타임스탬프 |
| ground_truth | str | 정답 Intent (v1 카테고리 기준) |
| v1_classified | str | v1 규칙 기반 분류 결과 |
| v2_classified | str | v2 taxonomy 동적 분류 결과 |
| v1_correct | 0/1 | v1 분류 정확도 (ground_truth == v1_classified) |
| v2_exact_correct | 0/1 | v2 exact match (ground_truth == v2_classified) |
| v2_semantic_correct | 0/1 | v2 semantic match (의미적 매핑 기반) |
| memories_found | int | 검색된 관련 메모리 수 |
| has_prediction | 0/1 | 선제적 예측 생성 여부 |
| pred_intent | str | 예측된 다음 Intent |
| pred_weight | float | 예측 전이 확률 |
| latency_ms | int | 처리 시간 (밀리초) |
| has_error | 0/1 | 에러 발생 여부 |
"""

    with open(out_dir / "README_dataset.md", "w", encoding="utf-8") as f:
        f.write(readme)

    print(f"  README_dataset.md: 데이터셋 설명")
    print(f"\n=== 데이터셋 내보내기 완료: {out_dir}/ ===")
    print(f"    summary.json 주요 지표:")
    print(f"      v1 정확도:       {summary['classification_accuracy']['v1_rule_based']['accuracy_pct']}%")
    print(f"      v2 exact:       {summary['classification_accuracy']['v2_exact_match']['accuracy_pct']}%")
    print(f"      v2 semantic:    {summary['classification_accuracy']['v2_semantic_match']['accuracy_pct']}%")
    print(f"      Prediction:     {summary['prediction']['prediction_rate_pct']}%")
    print(f"      Memory 활용:    {summary['memory']['utilization_pct']}%")
    print(f"      Taxonomy: {summary['taxonomy_evolution']['bootstrap_categories']} → {summary['taxonomy_evolution']['final_categories']}")
    print(f"      Latency avg:    {summary['latency']['avg_ms']}ms, P90: {summary['latency']['p90_ms']}ms")


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data/demo_results_v2.json"
    print(f"입력: {input_file}")
    export(input_file)
