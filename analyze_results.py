"""분석 리포트 생성 — demo_results.json → docs/analysis_report.md

사용법:
    PYTHONPATH=. python analyze_results.py
"""

import json
from collections import Counter
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "data" / "demo_results.json"
OUTPUT_PATH = Path(__file__).parent / "docs" / "analysis_report.md"


def load_results() -> dict:
    with open(RESULTS_PATH) as f:
        return json.load(f)


def analyze(data: dict) -> str:
    """분석 수행 후 마크다운 리포트 반환"""
    meta = data["meta"]
    turns = data["turns"]
    final = data["final_state"]

    sections = []

    # --- 헤더 ---
    sections.append(f"# AI Agent Memory Module — 분석 리포트\n")
    sections.append(f"**생성 시각:** {meta['timestamp']}")
    sections.append(f"**LLM:** {meta['llm_model']}")
    sections.append(f"**Embedding:** {meta['embedding_model']}")
    sections.append(f"**총 턴:** {meta['total_turns']} | **소요:** {meta['duration_sec']}s")
    sections.append("")

    # --- 1. Intent 분류 정확도 ---
    sections.append("## 1. Intent 분류 정확도\n")
    correct = 0
    total_with_gt = 0
    intent_matrix: dict[str, Counter] = {}

    for t in turns:
        gt = t.get("ground_truth_intent")
        pred = t.get("classified_intent")
        if gt and pred:
            total_with_gt += 1
            if gt == pred:
                correct += 1
            if gt not in intent_matrix:
                intent_matrix[gt] = Counter()
            intent_matrix[gt][pred] += 1

    if total_with_gt > 0:
        accuracy = correct / total_with_gt
        sections.append(f"- **정확도:** {correct}/{total_with_gt} = **{accuracy:.1%}**")
    else:
        accuracy = 0
        sections.append("- 정확도 계산 불가 (ground truth 없음)")

    sections.append("\n### Intent 혼동 행렬 (상위)\n")
    sections.append("| Ground Truth | Predicted | Count |")
    sections.append("|-------------|-----------|-------|")
    confusion_rows = []
    for gt, preds in sorted(intent_matrix.items()):
        for pred, count in preds.most_common(3):
            marker = " **miss**" if gt != pred else ""
            confusion_rows.append((gt, pred, count, marker))
    confusion_rows.sort(key=lambda x: -x[2])
    for gt, pred, count, marker in confusion_rows[:20]:
        sections.append(f"| {gt} | {pred} | {count}{marker} |")
    sections.append("")

    # --- 2. Prediction Hit Rate ---
    sections.append("## 2. 선제적 예측 (Prediction Hit Rate)\n")
    predictions_made = 0
    prediction_hits = 0

    for i, t in enumerate(turns):
        if t.get("prediction") and i + 1 < len(turns):
            predictions_made += 1
            predicted_next = t["prediction"]["next_intent"]
            # 같은 유저의 다음 턴 찾기
            for j in range(i + 1, len(turns)):
                next_t = turns[j]
                if next_t["user_id"] == t["user_id"] and next_t.get("classified_intent"):
                    if next_t["classified_intent"] == predicted_next:
                        prediction_hits += 1
                    break

    if predictions_made > 0:
        hit_rate = prediction_hits / predictions_made
        sections.append(f"- **예측 시도:** {predictions_made}회")
        sections.append(f"- **적중:** {prediction_hits}회")
        sections.append(f"- **Hit Rate:** **{hit_rate:.1%}**")
        target = "30%"
        status = "PASS" if hit_rate >= 0.3 else "FAIL"
        sections.append(f"- **목표 ({target}):** {status}")
    else:
        sections.append("- 예측이 발생하지 않음 (전이 패턴 부족)")
    sections.append("")

    # --- 3. 메모리 검색 효과 ---
    sections.append("## 3. 메모리 검색 효과\n")
    turns_with_mem = sum(1 for t in turns if t["memories_found"] > 0)
    total_mems_found = sum(t["memories_found"] for t in turns)
    total_turns = len(turns)

    sections.append(f"- **메모리 활용 턴:** {turns_with_mem}/{total_turns} ({turns_with_mem/total_turns:.1%})")
    sections.append(f"- **총 메모리 반환 수:** {total_mems_found}")
    if turns_with_mem > 0:
        sections.append(f"- **평균 반환 (활용 턴 기준):** {total_mems_found/turns_with_mem:.1f}건")
    sections.append("")

    # 유저별 메모리
    sections.append("### 유저별 저장 메모리\n")
    sections.append("| User | 메모리 수 | Importance 분포 |")
    sections.append("|------|----------|----------------|")
    for uid, mems in final.get("memories_detail", {}).items():
        imp_counts = Counter(m["importance"] for m in mems)
        dist = ", ".join(f"{k}: {v}" for k, v in sorted(imp_counts.items()))
        sections.append(f"| {uid} | {len(mems)} | {dist} |")
    sections.append("")

    # --- 4. Latency 분석 ---
    sections.append("## 4. Latency 분석\n")
    latencies = sorted(t["latency_ms"] for t in turns if "error" not in t)
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        p50 = latencies[len(latencies) // 2]
        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[min(p95_idx, len(latencies) - 1)]
        sections.append(f"- **평균:** {avg_lat:.0f}ms")
        sections.append(f"- **P50:** {p50}ms")
        sections.append(f"- **P95:** {p95}ms")
        sections.append(f"- **최소/최대:** {latencies[0]}ms / {latencies[-1]}ms")
    sections.append("")

    # --- 5. Intent 전이 그래프 ---
    sections.append("## 5. Intent 전이 패턴 (Top-10)\n")
    transitions = final.get("intent_transitions", {})
    sorted_trans = sorted(transitions.items(), key=lambda x: -x[1])

    sections.append("| 전이 | Weight |")
    sections.append("|------|--------|")
    for trans, weight in sorted_trans[:10]:
        sections.append(f"| {trans} | {weight:.3f} |")
    sections.append(f"\n- **총 전이 패턴:** {len(transitions)}개")
    sections.append("")

    # --- 6. 에러 분석 ---
    errors = [t for t in turns if "error" in t]
    sections.append("## 6. 에러 분석\n")
    if errors:
        sections.append(f"- **에러 발생:** {len(errors)}/{total_turns}턴")
        sections.append("\n| Turn | User | Message | Error |")
        sections.append("|------|------|---------|-------|")
        for e in errors[:10]:
            msg = e["message"][:30]
            err = e["error"][:80]
            sections.append(f"| {e['turn_id']} | {e['user_id']} | {msg} | {err} |")
    else:
        sections.append("- **에러 없음** (전체 턴 정상 처리)")
    sections.append("")

    # --- 7. 핵심 인사이트 ---
    sections.append("## 7. 핵심 인사이트\n")

    insights = []
    if accuracy >= 0.7:
        insights.append(f"Intent 분류 정확도 {accuracy:.1%}로 규칙 기반만으로도 높은 정확도 달성")
    elif accuracy >= 0.5:
        insights.append(f"Intent 분류 정확도 {accuracy:.1%} — LLM fallback 보강 고려 필요")
    else:
        insights.append(f"Intent 분류 정확도 {accuracy:.1%} — 규칙 패턴 확장 필요")

    if predictions_made > 0:
        if hit_rate >= 0.3:
            insights.append(f"예측 hit rate {hit_rate:.1%}로 목표(30%) 달성 — Anticipatory Memory Chains 유효")
        else:
            insights.append(f"예측 hit rate {hit_rate:.1%} — 전이 패턴 학습량 부족 가능성")

    mem_per_user = final.get("memories_per_user", {})
    total_stored = sum(mem_per_user.values())
    insights.append(f"총 {total_stored}건 메모리 저장 ({total_turns}턴 대비 {total_stored/max(total_turns,1):.1f}건/턴)")

    if latencies:
        insights.append(f"턴당 평균 {avg_lat:.0f}ms (LLM 추출 + 임베딩 포함)")

    for insight in insights:
        sections.append(f"- {insight}")
    sections.append("")

    # --- 8. 다음 단계 제안 ---
    sections.append("## 8. 다음 단계 제안\n")
    next_steps = [
        "Qdrant Docker 연동으로 벡터 DB 영속성 확보",
        "Decay engine 시간 경과 시뮬레이션 (7일/30일 후 메모리 상태)",
        "LLM fallback intent 분류 활성화 (규칙 실패 케이스 보강)",
        "대량 데이터 벤치마크 (10K 메모리, 동시 요청 부하)",
        "실제 사용자 파일럿 (소규모 그룹 2주 운영)",
    ]
    for i, step in enumerate(next_steps, 1):
        sections.append(f"{i}. {step}")

    return "\n".join(sections)


def main():
    data = load_results()
    report = analyze(data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Analysis report written to: {OUTPUT_PATH}")
    print(f"  Total turns analyzed: {data['meta']['total_turns']}")


if __name__ == "__main__":
    main()
