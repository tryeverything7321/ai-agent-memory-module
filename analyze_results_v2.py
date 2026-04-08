"""분석 리포트 v2 — demo_results_v2.json → docs/analysis_report_v2.md

v1 대비 추가 섹션:
  - Taxonomy Evolution 분석 (bootstrap, discovery, split, merge, extinction)
  - v1 vs v2 Intent 분류 비교
  - EPHEMERAL 패턴 분석
  - Lineage DAG 시각화 (텍스트)

사용법:
    PYTHONPATH=. python analyze_results_v2.py
"""

import json
from collections import Counter
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "data" / "demo_results_v2.json"
OUTPUT_PATH = Path(__file__).parent / "docs" / "analysis_report_v2.md"


def load_results() -> dict:
    with open(RESULTS_PATH) as f:
        return json.load(f)


def analyze(data: dict) -> str:
    """분석 수행 후 마크다운 리포트 반환"""
    meta = data["meta"]
    turns = data["turns"]
    final = data["final_state"]
    taxonomy = data.get("taxonomy", {})
    lineage = data.get("lineage", {})
    evolution_log = data.get("evolution_log", [])
    ephemeral_patterns = data.get("ephemeral_patterns", [])

    sections = []

    # --- 헤더 ---
    sections.append("# AI Agent Memory Module v2 — Taxonomy Evolution 분석 리포트\n")
    sections.append(f"**버전:** {meta.get('version', 'v2')}")
    sections.append(f"**생성 시각:** {meta['timestamp']}")
    sections.append(f"**LLM:** {meta['llm_model']}")
    sections.append(f"**Embedding:** {meta['embedding_model']}")
    sections.append(f"**총 턴:** {meta['total_turns']} | **유저:** {', '.join(meta.get('users', []))} | **소요:** {meta['duration_sec']}s")
    sections.append("")

    # --- 1. Taxonomy Evolution 분석 ---
    sections.append("## 1. Taxonomy Evolution 분석\n")

    if taxonomy:
        cats = taxonomy.get("categories", [])
        sections.append(f"### 최종 카테고리: {taxonomy.get('total_categories', len(cats))}개\n")
        sections.append("| 카테고리 | 멤버 수 | Decay Weight | Access Count | 생성 방식 |")
        sections.append("|----------|---------|-------------|-------------|----------|")
        for c in sorted(cats, key=lambda x: x["member_count"], reverse=True):
            sections.append(
                f"| {c['name']} | {c['member_count']} | {c['decay_weight']:.4f} | "
                f"{c['access_count']} | {c['created_by']} |"
            )
        sections.append("")

        # 생성 방식별 분포
        created_by_counts = Counter(c["created_by"] for c in cats)
        sections.append("### 카테고리 생성 방식 분포\n")
        for method, count in created_by_counts.most_common():
            sections.append(f"- **{method}**: {count}개")
        sections.append("")

    # --- 2. Lineage (계통수) ---
    sections.append("## 2. Lineage (계통수)\n")

    if lineage:
        sections.append(f"- 총 이벤트: {lineage.get('total_events', 0)}")
        sections.append(f"- DAG 노드: {lineage.get('total_nodes', 0)}")
        sections.append(f"- 현재 활성: {lineage.get('alive_categories', 0)}")
        sections.append(f"- 멸종: {lineage.get('extinct_categories', 0)}")
        sections.append("")

        event_counts = lineage.get("event_counts", {})
        if event_counts:
            sections.append("### 이벤트 유형별 횟수\n")
            sections.append("| 이벤트 | 횟수 |")
            sections.append("|--------|------|")
            for event_type, count in sorted(event_counts.items()):
                sections.append(f"| {event_type} | {count} |")
            sections.append("")

        # 이벤트 타임라인
        events = lineage.get("events", [])
        if events:
            sections.append("### 진화 타임라인\n")
            sections.append("```")
            for evt in events:
                ts = evt.get("timestamp", "")[:19]
                etype = evt["type"]
                if etype == "bootstrap":
                    sections.append(f"  {ts} [BOOTSTRAP] {evt['category']} ({evt['metadata'].get('member_count', '?')} members)")
                elif etype == "discovery":
                    sections.append(f"  {ts} [DISCOVERY] {evt['category']} — trigger: \"{evt['metadata'].get('trigger_message', '')[:50]}\"")
                elif etype == "split":
                    sections.append(f"  {ts} [SPLIT] {evt['parent']} → {evt['children']}")
                elif etype == "merge":
                    sections.append(f"  {ts} [MERGE] {evt['parents']} → {evt['child']}")
                elif etype == "extinction":
                    sections.append(f"  {ts} [EXTINCT] {evt['category']} (weight={evt['metadata'].get('final_weight', '?')})")
            sections.append("```\n")

    # --- 3. v1 vs v2 Intent 분류 비교 ---
    sections.append("## 3. v1 vs v2 Intent 분류 비교\n")

    v1_correct = 0
    v2_correct = 0
    total_with_gt = 0
    v2_categories_seen = set()

    for t in turns:
        gt = t.get("ground_truth_intent")
        v1 = t.get("v1_classified")
        v2 = t.get("v2_classified")

        if v2:
            v2_categories_seen.add(v2)

        if gt and v1:
            total_with_gt += 1
            if gt == v1:
                v1_correct += 1

        # v2는 동적 카테고리이므로 ground truth와 정확히 같지 않을 수 있음
        # 하지만 의미적으로 유사한지는 수동 평가 필요
        if gt and v2 and gt == v2:
            v2_correct += 1

    if total_with_gt > 0:
        v1_acc = v1_correct / total_with_gt * 100
        v2_acc = v2_correct / total_with_gt * 100
        sections.append(f"| 지표 | v1 (Rule-based) | v2 (Taxonomy Evolution) |")
        sections.append(f"|------|----------------|----------------------|")
        sections.append(f"| 정확도 (exact match) | {v1_acc:.1f}% ({v1_correct}/{total_with_gt}) | {v2_acc:.1f}% ({v2_correct}/{total_with_gt}) |")
        sections.append(f"| 카테고리 수 | 12 (고정) | {len(v2_categories_seen)} (동적) |")
        sections.append("")

        # v2가 발견한 고유 카테고리
        sections.append("### v2 발견 카테고리 목록\n")
        for cat in sorted(v2_categories_seen):
            sections.append(f"- `{cat}`")
        sections.append("")
    else:
        sections.append("*ground truth가 있는 턴이 없습니다.*\n")

    # --- 4. Evolution Log ---
    sections.append("## 4. Evolution Log\n")
    if evolution_log:
        for evt in evolution_log:
            turn = evt.get("turn_id", "?")
            event = evt.get("event", "unknown")
            if event == "bootstrap_complete":
                sections.append(f"- **Turn {turn}**: Bootstrap 완료 — {len(evt.get('categories', []))}개 카테고리, {evt.get('ephemeral_count', 0)}개 EPHEMERAL 패턴")
            elif event == "category_discovered":
                sections.append(f"- **Turn {turn}**: 카테고리 발견 — `{evt.get('category', '?')}` (trigger: \"{evt.get('trigger', '')[:50]}\")")
            elif event == "decay_sweep":
                pruned = evt.get("pruned", [])
                splits = evt.get("splits", [])
                fusions = evt.get("fusions", [])
                reclass = evt.get("reclassified", 0)
                parts = []
                if pruned:
                    parts.append(f"pruned={pruned}")
                if reclass:
                    parts.append(f"reclassified={reclass}")
                if splits:
                    parts.append(f"splits={[s['parent']+'→'+str(s['children']) for s in splits]}")
                if fusions:
                    parts.append(f"fusions={[f['parents'][0]+'+'+f['parents'][1]+'→'+f['child'] for f in fusions]}")
                summary = ", ".join(parts) if parts else "no changes"
                sections.append(f"- **Turn {turn}**: Decay Sweep — {summary}")
        sections.append("")
    else:
        sections.append("*진화 이벤트가 없습니다.*\n")

    # --- 5. EPHEMERAL 패턴 ---
    sections.append("## 5. LLM 생성 EPHEMERAL 패턴\n")
    if ephemeral_patterns:
        sections.append(f"총 {len(ephemeral_patterns)}개 패턴:\n")
        sections.append("```")
        for i in range(0, len(ephemeral_patterns), 10):
            chunk = ephemeral_patterns[i:i+10]
            sections.append("  " + ", ".join(f'"{p}"' for p in chunk))
        sections.append("```\n")
    else:
        sections.append("*EPHEMERAL 패턴이 생성되지 않았습니다.*\n")

    # --- 6. 예측 (Prediction) ---
    sections.append("## 6. Prediction (선제적 예측)\n")
    predictions = [t for t in turns if t.get("prediction")]
    if predictions:
        pred_counts = Counter()
        for t in predictions:
            pred = t["prediction"]
            pred_counts[pred["next_intent"]] += 1

        sections.append(f"- 예측 생성: {len(predictions)}/{len(turns)} 턴 ({len(predictions)/len(turns)*100:.1f}%)")
        sections.append("")
        sections.append("### 예측 Intent 분포\n")
        sections.append("| Intent | 횟수 |")
        sections.append("|--------|------|")
        for intent, count in pred_counts.most_common():
            sections.append(f"| {intent} | {count} |")
        sections.append("")
    else:
        sections.append("*예측이 생성되지 않았습니다.*\n")

    # --- 7. 메모리 통계 ---
    sections.append("## 7. 메모리 통계\n")
    mem_per_user = final.get("memories_per_user", {})
    if mem_per_user:
        sections.append("| 유저 | 메모리 수 |")
        sections.append("|------|----------|")
        for uid, count in sorted(mem_per_user.items()):
            sections.append(f"| {uid} | {count} |")
        sections.append(f"| **합계** | **{sum(mem_per_user.values())}** |")
        sections.append("")

    # --- 8. Latency ---
    sections.append("## 8. Latency 분석\n")
    latencies = [t["latency_ms"] for t in turns if "error" not in t]
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        max_lat = max(latencies)
        min_lat = min(latencies)
        p90_idx = int(len(latencies) * 0.9)
        sorted_lat = sorted(latencies)
        p90 = sorted_lat[p90_idx] if p90_idx < len(sorted_lat) else max_lat

        sections.append(f"| 지표 | 값 |")
        sections.append(f"|------|-----|")
        sections.append(f"| 평균 | {avg_lat:.0f}ms |")
        sections.append(f"| P90 | {p90}ms |")
        sections.append(f"| 최소 | {min_lat}ms |")
        sections.append(f"| 최대 | {max_lat}ms |")
        sections.append("")

    # --- 9. 에러 ---
    errors = [t for t in turns if "error" in t]
    sections.append("## 9. 에러\n")
    if errors:
        sections.append(f"총 {len(errors)}건:\n")
        for e in errors[:10]:
            sections.append(f"- Turn {e['turn_id']}: {e['error'][:100]}")
    else:
        sections.append("에러 0건\n")

    # --- 10. Key Insights ---
    sections.append("## 10. Key Insights\n")
    sections.append("### Taxonomy Evolution의 의미")
    sections.append("")
    sections.append("1. **자동 카테고리 발견**: 하드코딩된 12개 카테고리 대신 데이터 기반으로 카테고리가 자동 생성됨")
    sections.append("2. **Ebbinghaus on Taxonomy**: 카테고리 자체에 망각 곡선 적용 — 사용되지 않는 카테고리는 자연 소멸")
    sections.append("3. **Mitosis/Fusion**: 카테고리 분열/병합으로 MECE 유지 — 수동 관리 없이 분류 체계가 진화")
    sections.append("4. **LLM-bootstrapped EPHEMERAL**: 도메인별 자동 적응 가능한 ephemeral 패턴 생성")
    sections.append("")

    return "\n".join(sections)


def main():
    data = load_results()
    report = analyze(data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"분석 리포트 생성 완료: {OUTPUT_PATH}")
    print(f"  총 {len(report)} chars, {report.count(chr(10))} lines")


if __name__ == "__main__":
    main()
