"""벤치마크 결과 분석 — Baseline vs Experiment 비교 리포트 생성

사용법:
  python experiments/analyze_benchmark.py experiments/results/benchmark_*.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict


def analyze_result(filepath: str) -> dict:
    """결과 JSON 파일을 읽고 분석 리포트 생성"""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    config = data["config"]
    comparison = data["comparison"]
    baseline = data["baseline"]
    experiment = data["experiment"]

    print(f"\n{'='*70}")
    print(f"벤치마크 결과 분석: {Path(filepath).name}")
    print(f"{'='*70}")

    # --- 설정 ---
    print(f"\n[설정]")
    print(f"  데이터셋: {config['sub_dataset']}")
    print(f"  청크 사이즈: {config['chunk_size']}")
    print(f"  전파 깊이: {config['propagation_depth']}")
    print(f"  홉당 감쇄: {config['decay_per_hop']}")
    print(f"  최대 쿼리: {config.get('max_queries', 'ALL')}")

    # --- 전체 메트릭 비교 ---
    print(f"\n[전체 메트릭 비교]")
    print(f"  {'메트릭':<25} {'Baseline':>10} {'Experiment':>10} {'Δ':>10}")
    print(f"  {'-'*55}")
    for key in ["exact_match", "substring_exact_match", "f1"]:
        b = comparison[key]["baseline"]
        e = comparison[key]["experiment"]
        d = comparison[key]["delta"]
        marker = "↑" if d > 0 else ("↓" if d < 0 else "=")
        print(f"  {key:<25} {b:>9.2f}% {e:>9.2f}% {d:>+9.2f}% {marker}")

    # --- 시간 비교 ---
    b_metrics = baseline["metrics"]
    e_metrics = experiment["metrics"]
    print(f"\n[시간 비교]")
    print(f"  Memorize time: Baseline={b_metrics['total_memorize_time']:.1f}s, "
          f"Experiment={e_metrics['total_memorize_time']:.1f}s")
    print(f"  Avg query time: Baseline={b_metrics['avg_query_time']:.3f}s, "
          f"Experiment={e_metrics['avg_query_time']:.3f}s")

    # --- 개별 쿼리 비교 ---
    b_results = {(r["context_id"], r["query_id"]): r for r in baseline["results"]}
    e_results = {(r["context_id"], r["query_id"]): r for r in experiment["results"]}

    improved = []
    degraded = []
    same = []

    for key in b_results:
        if key not in e_results:
            continue
        b_em = b_results[key]["exact_match"]
        e_em = e_results[key]["exact_match"]
        if e_em > b_em:
            improved.append((key, b_results[key], e_results[key]))
        elif e_em < b_em:
            degraded.append((key, b_results[key], e_results[key]))
        else:
            same.append((key, b_results[key], e_results[key]))

    print(f"\n[개별 쿼리 변화 (Exact Match 기준)]")
    print(f"  개선: {len(improved)} 쿼리")
    print(f"  악화: {len(degraded)} 쿼리")
    print(f"  동일: {len(same)} 쿼리")

    if improved:
        print(f"\n  [개선된 쿼리]")
        for key, br, er in improved[:10]:
            q = br["question"][:70]
            print(f"    Q{key[1]}: {q}...")
            print(f"      GT: {br['ground_truth']} | B: \"{br['prediction'][:30]}\" → E: \"{er['prediction'][:30]}\"")

    if degraded:
        print(f"\n  [악화된 쿼리]")
        for key, br, er in degraded[:10]:
            q = br["question"][:70]
            print(f"    Q{key[1]}: {q}...")
            print(f"      GT: {br['ground_truth']} | B: \"{br['prediction'][:30]}\" → E: \"{er['prediction'][:30]}\"")

    # --- F1 분포 비교 ---
    b_f1s = [r["f1"] for r in baseline["results"]]
    e_f1s = [r["f1"] for r in experiment["results"]]

    def dist_summary(scores):
        if not scores:
            return "N/A"
        n = len(scores)
        mean = sum(scores) / n
        zero_count = sum(1 for s in scores if s == 0)
        perfect_count = sum(1 for s in scores if s == 1.0)
        return f"mean={mean:.3f}, zero={zero_count}/{n}, perfect={perfect_count}/{n}"

    print(f"\n[F1 분포]")
    print(f"  Baseline:   {dist_summary(b_f1s)}")
    print(f"  Experiment: {dist_summary(e_f1s)}")

    print(f"\n{'='*70}\n")

    return {
        "filepath": filepath,
        "comparison": comparison,
        "improved": len(improved),
        "degraded": len(degraded),
        "same": len(same),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 가장 최근 결과 파일 자동 선택
        results_dir = Path(__file__).parent / "results"
        files = sorted(results_dir.glob("benchmark_*.json"))
        if not files:
            print("결과 파일이 없습니다.")
            sys.exit(1)
        filepath = str(files[-1])
    else:
        filepath = sys.argv[1]

    analyze_result(filepath)
