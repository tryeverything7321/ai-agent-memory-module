"""
통계적 유의성 보강 분석 스크립트

목적: adversarial attack 7회 실행 결과에 대해 non-parametric 통계 검정,
      층화 분석, bootstrap CI를 수행하여 논문의 통계적 유의성을 보강.

분석 항목:
  1. Wilcoxon signed-rank test (BFS vs Attr-aware damage ratio)
  2. 층화 분석 (attack 강도별 하위그룹)
  3. Bootstrap 95% CI for damage ratio difference
"""

import json
import glob
import os
import numpy as np
from scipy import stats
from datetime import datetime


# --- 데이터 로드 ---
def load_adversarial_data(results_dir: str) -> list[dict]:
    """모든 adversarial_attack_6k 결과 파일을 로드하여 실험 단위로 반환."""
    files = sorted(glob.glob(os.path.join(results_dir, "adversarial_attack_6k_*.json")))
    all_experiments = []
    for fpath in files:
        with open(fpath) as f:
            data = json.load(f)
        file_id = os.path.basename(fpath).replace("adversarial_attack_6k_", "").replace(".json", "")
        for exp in data["experiments"]:
            exp["_file_id"] = file_id
        all_experiments.extend(data["experiments"])
    return all_experiments


# --- paired 데이터 구성 ---
def build_paired_data(experiments: list[dict]) -> dict[int, list[tuple[float, float]]]:
    """
    attack 강도별로 (bfs_damage, attr_damage) 쌍을 구성.
    같은 file_id + num_attack_facts를 기준으로 pairing.
    """
    # file_id × num_attack_facts → {mode: damage_ratio}
    grouped = {}
    for exp in experiments:
        key = (exp["_file_id"], exp["num_attack_facts"])
        if key not in grouped:
            grouped[key] = {}
        grouped[key][exp["mode"]] = exp["damage"]["damage_ratio_pct"]

    # attack 강도별로 분류
    paired_by_attack = {}
    for (file_id, n_attack), modes in grouped.items():
        if "bfs" in modes and "attribute_aware" in modes:
            if n_attack not in paired_by_attack:
                paired_by_attack[n_attack] = []
            paired_by_attack[n_attack].append((modes["bfs"], modes["attribute_aware"]))

    return paired_by_attack


# --- 1. Wilcoxon signed-rank test ---
def wilcoxon_test(paired_by_attack: dict) -> dict:
    """
    각 attack 강도별 + 전체 통합에 대해 Wilcoxon signed-rank test 수행.
    BFS damage > Attr-aware damage를 대립가설로 설정 (one-sided).
    """
    results = {}

    # 전체 통합
    all_bfs = []
    all_attr = []
    for n_attack, pairs in sorted(paired_by_attack.items()):
        bfs_vals = [p[0] for p in pairs]
        attr_vals = [p[1] for p in pairs]
        all_bfs.extend(bfs_vals)
        all_attr.extend(attr_vals)

        diff = np.array(bfs_vals) - np.array(attr_vals)
        # 0인 차이 제거 (Wilcoxon은 tie 처리 필요)
        nonzero_diff = diff[diff != 0]

        result_entry = {
            "n_pairs": len(pairs),
            "bfs_mean": float(np.mean(bfs_vals)),
            "bfs_std": float(np.std(bfs_vals, ddof=1)) if len(bfs_vals) > 1 else 0.0,
            "attr_mean": float(np.mean(attr_vals)),
            "attr_std": float(np.std(attr_vals, ddof=1)) if len(attr_vals) > 1 else 0.0,
            "diff_mean": float(np.mean(diff)),
            "diff_median": float(np.median(diff)),
            "n_nonzero_diffs": int(len(nonzero_diff)),
        }

        if len(nonzero_diff) >= 6:
            # Wilcoxon signed-rank test (greater: bfs > attr)
            stat, p_value = stats.wilcoxon(
                bfs_vals, attr_vals, alternative="greater", zero_method="wilcox"
            )
            result_entry["wilcoxon_statistic"] = float(stat)
            result_entry["p_value_one_sided"] = float(p_value)
            result_entry["significant_at_0.05"] = p_value < 0.05
            result_entry["significant_at_0.10"] = p_value < 0.10
        else:
            # 표본 부족 → exact test 또는 permutation test로 대체
            result_entry["note"] = f"non-zero diff 수({len(nonzero_diff)})가 Wilcoxon 최소 요건(6) 미달"
            # Permutation test 대체
            if len(nonzero_diff) > 0:
                perm_p = permutation_test_one_sided(diff)
                result_entry["permutation_p_value"] = float(perm_p)
                result_entry["permutation_significant_at_0.05"] = perm_p < 0.05
                result_entry["permutation_significant_at_0.10"] = perm_p < 0.10

        results[f"attack_{n_attack}_facts"] = result_entry

    # 전체 통합 분석
    all_diff = np.array(all_bfs) - np.array(all_attr)
    nonzero_all = all_diff[all_diff != 0]

    combined = {
        "n_pairs": len(all_bfs),
        "bfs_mean": float(np.mean(all_bfs)),
        "bfs_std": float(np.std(all_bfs, ddof=1)),
        "attr_mean": float(np.mean(all_attr)),
        "attr_std": float(np.std(all_attr, ddof=1)),
        "diff_mean": float(np.mean(all_diff)),
        "diff_median": float(np.median(all_diff)),
        "n_nonzero_diffs": int(len(nonzero_all)),
    }

    if len(nonzero_all) >= 6:
        stat, p_value = stats.wilcoxon(
            all_bfs, all_attr, alternative="greater", zero_method="wilcox"
        )
        combined["wilcoxon_statistic"] = float(stat)
        combined["p_value_one_sided"] = float(p_value)
        combined["significant_at_0.05"] = p_value < 0.05
        combined["significant_at_0.10"] = p_value < 0.10
    else:
        combined["note"] = f"non-zero diff 수({len(nonzero_all)})가 부족"
        perm_p = permutation_test_one_sided(all_diff)
        combined["permutation_p_value"] = float(perm_p)
        combined["permutation_significant_at_0.05"] = perm_p < 0.05
        combined["permutation_significant_at_0.10"] = perm_p < 0.10

    # Welch t-test 비교용
    t_stat, t_p = stats.ttest_ind(all_bfs, all_attr, equal_var=False, alternative="greater")
    combined["welch_t_statistic"] = float(t_stat)
    combined["welch_t_p_value"] = float(t_p)

    # 대응 t-test
    paired_t_stat, paired_t_p = stats.ttest_rel(all_bfs, all_attr, alternative="greater")
    combined["paired_t_statistic"] = float(paired_t_stat)
    combined["paired_t_p_value"] = float(paired_t_p)

    results["combined_all_attacks"] = combined
    return results


def permutation_test_one_sided(diffs: np.ndarray, n_permutations: int = 100000) -> float:
    """
    Exact/approximate permutation test for paired differences.
    H0: median(diff) = 0, H1: median(diff) > 0
    각 차이값의 부호를 랜덤으로 뒤집어 관측 통계량 이상의 비율 계산.
    """
    observed_stat = np.mean(diffs)
    n = len(diffs)
    abs_diffs = np.abs(diffs)

    # exact test 가능 여부 (2^n <= n_permutations)
    if n <= 20:
        # exact enumeration
        count_ge = 0
        total = 2 ** n
        for i in range(total):
            signs = np.array([(1 if (i >> j) & 1 else -1) for j in range(n)])
            perm_stat = np.mean(signs * abs_diffs)
            if perm_stat >= observed_stat - 1e-12:
                count_ge += 1
        return count_ge / total
    else:
        # approximate
        rng = np.random.default_rng(42)
        count_ge = 0
        for _ in range(n_permutations):
            signs = rng.choice([-1, 1], size=n)
            perm_stat = np.mean(signs * abs_diffs)
            if perm_stat >= observed_stat - 1e-12:
                count_ge += 1
        return count_ge / n_permutations


# --- 2. 층화 분석 ---
def stratified_analysis(paired_by_attack: dict) -> dict:
    """
    Attack 강도별 층화 분석.
    hub degree가 모두 동일(23)하므로 attack 강도(1, 3, 5)를 층화 변수로 사용.
    추가로 damage 발생 여부 기반 층화도 수행.
    """
    results = {}

    for n_attack, pairs in sorted(paired_by_attack.items()):
        bfs_vals = np.array([p[0] for p in pairs])
        attr_vals = np.array([p[1] for p in pairs])
        diff = bfs_vals - attr_vals

        # damage가 실제로 발생한 쌍만 분류
        has_damage = (bfs_vals != 0) | (attr_vals != 0)
        n_with_damage = int(np.sum(has_damage))
        n_without_damage = int(np.sum(~has_damage))

        entry = {
            "n_total_pairs": len(pairs),
            "n_with_damage": n_with_damage,
            "n_without_damage": n_without_damage,
            "bfs_damage_values": bfs_vals.tolist(),
            "attr_damage_values": attr_vals.tolist(),
            "diff_values": diff.tolist(),
            "bfs_nonzero_count": int(np.sum(bfs_vals != 0)),
            "attr_nonzero_count": int(np.sum(attr_vals != 0)),
            "bfs_positive_damage_mean": float(np.mean(bfs_vals[bfs_vals > 0])) if np.any(bfs_vals > 0) else None,
            "attr_positive_damage_mean": float(np.mean(attr_vals[attr_vals > 0])) if np.any(attr_vals > 0) else None,
        }

        # Effect size: Cliff's delta (non-parametric effect size)
        cliffs_d = cliffs_delta(bfs_vals, attr_vals)
        entry["cliffs_delta"] = float(cliffs_d)
        entry["cliffs_delta_interpretation"] = interpret_cliffs_delta(cliffs_d)

        # Rank-biserial correlation (effect size for Wilcoxon)
        if n_with_damage >= 2:
            # Cohen's d for paired data
            if np.std(diff, ddof=1) > 0:
                cohens_d = float(np.mean(diff) / np.std(diff, ddof=1))
                entry["cohens_d_paired"] = cohens_d
                entry["cohens_d_interpretation"] = interpret_cohens_d(cohens_d)

        results[f"attack_{n_attack}_facts"] = entry

    return results


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Cliff's delta: non-parametric effect size measure."""
    n_x, n_y = len(x), len(y)
    more = 0
    less = 0
    for xi in x:
        for yj in y:
            if xi > yj:
                more += 1
            elif xi < yj:
                less += 1
    return (more - less) / (n_x * n_y)


def interpret_cliffs_delta(d: float) -> str:
    """Cliff's delta 해석 (Vargha & Delaney, 2000)."""
    ad = abs(d)
    if ad < 0.147:
        return "negligible"
    elif ad < 0.33:
        return "small"
    elif ad < 0.474:
        return "medium"
    else:
        return "large"


def interpret_cohens_d(d: float) -> str:
    """Cohen's d 해석."""
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    elif ad < 0.5:
        return "small"
    elif ad < 0.8:
        return "medium"
    else:
        return "large"


# --- 3. Bootstrap CI ---
def bootstrap_ci(
    paired_by_attack: dict,
    n_bootstrap: int = 10000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> dict:
    """
    BFS vs Attr-aware damage ratio 차이에 대한 Bootstrap 신뢰구간.
    BCa (bias-corrected and accelerated) 방법 사용.
    """
    rng = np.random.default_rng(seed)
    results = {}

    # attack 강도별
    for n_attack, pairs in sorted(paired_by_attack.items()):
        bfs_vals = np.array([p[0] for p in pairs])
        attr_vals = np.array([p[1] for p in pairs])
        diff = bfs_vals - attr_vals

        ci_result = _compute_bootstrap_ci(diff, rng, n_bootstrap, ci_level)
        ci_result["bfs_values"] = bfs_vals.tolist()
        ci_result["attr_values"] = attr_vals.tolist()
        results[f"attack_{n_attack}_facts"] = ci_result

    # 전체 통합
    all_diff = []
    for pairs in paired_by_attack.values():
        for p in pairs:
            all_diff.append(p[0] - p[1])
    all_diff = np.array(all_diff)

    combined = _compute_bootstrap_ci(all_diff, rng, n_bootstrap, ci_level)
    results["combined_all_attacks"] = combined

    return results


def _compute_bootstrap_ci(
    diff: np.ndarray,
    rng: np.random.Generator,
    n_bootstrap: int,
    ci_level: float,
) -> dict:
    """단일 차이 배열에 대한 bootstrap CI 계산."""
    n = len(diff)
    observed_mean = float(np.mean(diff))
    observed_median = float(np.median(diff))

    # Bootstrap resampling
    boot_means = np.zeros(n_bootstrap)
    boot_medians = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(diff, size=n, replace=True)
        boot_means[i] = np.mean(sample)
        boot_medians[i] = np.median(sample)

    alpha = 1 - ci_level

    # Percentile method
    mean_ci_lower = float(np.percentile(boot_means, 100 * alpha / 2))
    mean_ci_upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    median_ci_lower = float(np.percentile(boot_medians, 100 * alpha / 2))
    median_ci_upper = float(np.percentile(boot_medians, 100 * (1 - alpha / 2)))

    # BCa adjustment for mean
    # Bias correction factor
    z0 = stats.norm.ppf(np.mean(boot_means < observed_mean))
    # Acceleration factor (jackknife)
    jackknife_means = np.zeros(n)
    for i in range(n):
        jackknife_means[i] = np.mean(np.delete(diff, i))
    jack_mean = np.mean(jackknife_means)
    num = np.sum((jack_mean - jackknife_means) ** 3)
    denom = 6 * (np.sum((jack_mean - jackknife_means) ** 2) ** 1.5)
    a_hat = num / denom if denom != 0 else 0

    # BCa adjusted percentiles
    z_alpha_lower = stats.norm.ppf(alpha / 2)
    z_alpha_upper = stats.norm.ppf(1 - alpha / 2)

    if not np.isinf(z0):
        p_lower = stats.norm.cdf(z0 + (z0 + z_alpha_lower) / (1 - a_hat * (z0 + z_alpha_lower)))
        p_upper = stats.norm.cdf(z0 + (z0 + z_alpha_upper) / (1 - a_hat * (z0 + z_alpha_upper)))
        bca_lower = float(np.percentile(boot_means, 100 * p_lower))
        bca_upper = float(np.percentile(boot_means, 100 * p_upper))
    else:
        bca_lower = mean_ci_lower
        bca_upper = mean_ci_upper

    return {
        "n_samples": n,
        "observed_mean_diff": observed_mean,
        "observed_median_diff": observed_median,
        "bootstrap_mean_se": float(np.std(boot_means, ddof=1)),
        "ci_level": ci_level,
        "percentile_ci_mean": [mean_ci_lower, mean_ci_upper],
        "percentile_ci_median": [median_ci_lower, median_ci_upper],
        "bca_ci_mean": [bca_lower, bca_upper],
        "ci_excludes_zero_percentile": mean_ci_lower > 0 or mean_ci_upper < 0,
        "ci_excludes_zero_bca": bca_lower > 0 or bca_upper < 0,
    }


# --- 추가: 다중비교 보정 ---
def multiple_comparison_correction(wilcoxon_results: dict) -> dict:
    """Bonferroni 및 Holm-Bonferroni 다중비교 보정."""
    # attack별 p-value 수집
    p_values = {}
    for key, val in wilcoxon_results.items():
        if key == "combined_all_attacks":
            continue
        p_key = None
        p_val = None
        if "p_value_one_sided" in val:
            p_val = val["p_value_one_sided"]
            p_key = "wilcoxon"
        elif "permutation_p_value" in val:
            p_val = val["permutation_p_value"]
            p_key = "permutation"
        if p_val is not None:
            p_values[key] = {"test_type": p_key, "raw_p": p_val}

    n_tests = len(p_values)
    if n_tests == 0:
        return {"note": "보정할 p-value 없음"}

    # Bonferroni
    for key in p_values:
        p_values[key]["bonferroni_p"] = min(p_values[key]["raw_p"] * n_tests, 1.0)
        p_values[key]["bonferroni_significant_0.05"] = p_values[key]["bonferroni_p"] < 0.05

    # Holm-Bonferroni
    sorted_keys = sorted(p_values.keys(), key=lambda k: p_values[k]["raw_p"])
    for rank, key in enumerate(sorted_keys):
        adjusted_p = min(p_values[key]["raw_p"] * (n_tests - rank), 1.0)
        p_values[key]["holm_bonferroni_p"] = adjusted_p
        p_values[key]["holm_bonferroni_significant_0.05"] = adjusted_p < 0.05

    return {"n_tests": n_tests, "corrections": p_values}


# --- 메인 실행 ---
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(base_dir, "results")

    print("=" * 60)
    print("통계적 유의성 보강 분석")
    print("=" * 60)

    # 데이터 로드
    experiments = load_adversarial_data(results_dir)
    print(f"\n총 실험 수: {len(experiments)}")

    paired_by_attack = build_paired_data(experiments)
    for n_attack, pairs in sorted(paired_by_attack.items()):
        print(f"  Attack {n_attack}팩트: {len(pairs)}쌍")

    # 1. Wilcoxon signed-rank test
    print("\n" + "-" * 60)
    print("1. Wilcoxon Signed-Rank Test / Permutation Test")
    print("-" * 60)
    wilcoxon_results = wilcoxon_test(paired_by_attack)
    for key, val in wilcoxon_results.items():
        print(f"\n  [{key}]")
        print(f"    N pairs: {val['n_pairs']}")
        print(f"    BFS damage: {val['bfs_mean']:.4f} ± {val['bfs_std']:.4f}")
        print(f"    Attr damage: {val['attr_mean']:.4f} ± {val['attr_std']:.4f}")
        print(f"    Diff mean: {val['diff_mean']:.4f}, median: {val['diff_median']:.4f}")
        if "wilcoxon_statistic" in val:
            print(f"    Wilcoxon W: {val['wilcoxon_statistic']:.4f}")
            print(f"    p-value (one-sided): {val['p_value_one_sided']:.6f}")
            print(f"    Significant at α=0.05: {val['significant_at_0.05']}")
            print(f"    Significant at α=0.10: {val['significant_at_0.10']}")
        if "permutation_p_value" in val:
            print(f"    Permutation p-value: {val['permutation_p_value']:.6f}")
            print(f"    Perm significant at α=0.05: {val['permutation_significant_at_0.05']}")
            print(f"    Perm significant at α=0.10: {val['permutation_significant_at_0.10']}")
        if "welch_t_p_value" in val:
            print(f"    Welch t-test p-value: {val['welch_t_p_value']:.6f}")
            print(f"    Paired t-test p-value: {val['paired_t_p_value']:.6f}")

    # 2. 층화 분석
    print("\n" + "-" * 60)
    print("2. 층화 분석 (Attack 강도별)")
    print("-" * 60)
    stratified_results = stratified_analysis(paired_by_attack)
    for key, val in stratified_results.items():
        print(f"\n  [{key}]")
        print(f"    Total pairs: {val['n_total_pairs']}")
        print(f"    With damage: {val['n_with_damage']}, Without: {val['n_without_damage']}")
        print(f"    BFS nonzero: {val['bfs_nonzero_count']}, Attr nonzero: {val['attr_nonzero_count']}")
        if val.get("bfs_positive_damage_mean") is not None:
            print(f"    BFS positive damage mean: {val['bfs_positive_damage_mean']:.4f}")
        if val.get("attr_positive_damage_mean") is not None:
            print(f"    Attr positive damage mean: {val['attr_positive_damage_mean']:.4f}")
        print(f"    Cliff's delta: {val['cliffs_delta']:.4f} ({val['cliffs_delta_interpretation']})")
        if "cohens_d_paired" in val:
            print(f"    Cohen's d (paired): {val['cohens_d_paired']:.4f} ({val['cohens_d_interpretation']})")

    # 3. Bootstrap CI
    print("\n" + "-" * 60)
    print("3. Bootstrap 95% CI")
    print("-" * 60)
    bootstrap_results = bootstrap_ci(paired_by_attack)
    for key, val in bootstrap_results.items():
        print(f"\n  [{key}]")
        print(f"    N: {val['n_samples']}")
        print(f"    Observed mean diff: {val['observed_mean_diff']:.4f}")
        print(f"    Bootstrap SE: {val['bootstrap_mean_se']:.4f}")
        print(f"    Percentile CI (mean): [{val['percentile_ci_mean'][0]:.4f}, {val['percentile_ci_mean'][1]:.4f}]")
        print(f"    BCa CI (mean): [{val['bca_ci_mean'][0]:.4f}, {val['bca_ci_mean'][1]:.4f}]")
        print(f"    CI excludes zero (BCa): {val['ci_excludes_zero_bca']}")

    # 4. 다중비교 보정
    print("\n" + "-" * 60)
    print("4. 다중비교 보정 (Bonferroni / Holm-Bonferroni)")
    print("-" * 60)
    correction_results = multiple_comparison_correction(wilcoxon_results)
    if "corrections" in correction_results:
        print(f"  검정 횟수: {correction_results['n_tests']}")
        for key, val in correction_results["corrections"].items():
            print(f"\n  [{key}]")
            print(f"    Test type: {val['test_type']}")
            print(f"    Raw p: {val['raw_p']:.6f}")
            print(f"    Bonferroni p: {val['bonferroni_p']:.6f} (sig: {val['bonferroni_significant_0.05']})")
            print(f"    Holm-Bonferroni p: {val['holm_bonferroni_p']:.6f} (sig: {val['holm_bonferroni_significant_0.05']})")

    # 결과 저장
    output = {
        "metadata": {
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n_runs": 7,
            "n_total_experiments": len(experiments),
            "attack_levels": sorted(paired_by_attack.keys()),
            "description": "BFS vs Attribute-aware propagation의 adversarial damage 비교 통계 분석",
        },
        "wilcoxon_test": wilcoxon_results,
        "stratified_analysis": stratified_results,
        "bootstrap_ci": bootstrap_results,
        "multiple_comparison_correction": correction_results,
    }

    output_path = os.path.join(results_dir, "statistical_analysis.json")

    # numpy 타입 JSON 직렬화 지원
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    print(f"\n결과 저장: {output_path}")

    return output


if __name__ == "__main__":
    main()
