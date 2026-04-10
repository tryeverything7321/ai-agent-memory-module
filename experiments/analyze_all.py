"""전체 실험 결과 통합 분석 — Workshop Paper용

Collateral damage (6K/32K/64K), Adversarial attack, Scale 트렌드 통합.
결과를 표 형식으로 출력하고 docs/paper_tables.md로 저장.

사용법:
  PYTHONPATH=/home/mingyu1choi/PJT/memory_module \
    .venv/bin/python experiments/analyze_all.py
"""

from __future__ import annotations

import json
import glob
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


def load_latest(pattern: str) -> dict | None:
    """패턴에 매칭되는 최신 결과 파일 로드"""
    files = sorted(glob.glob(str(RESULTS_DIR / pattern)))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as f:
        return json.load(f)


def analyze_scale_trend():
    """C1: Scale 트렌드 (6K/32K/64K) 분석"""
    print("\n" + "=" * 80)
    print("## C1: Collateral Damage Scale Trend (6K → 32K → 64K)")
    print("=" * 80)

    rows = []
    for size in ["6k", "32k", "64k"]:
        cd = load_latest(f"collateral_damage_factconsolidation_mh_{size}_*.json")
        if not cd:
            print(f"  ⚠ {size} collateral damage 결과 없음")
            continue

        agg = cd.get("aggregate", {})
        valid = agg.get("total_valid_memories", 0)
        bfs_dec = agg.get("bfs_total_decayed", 0)
        attr_dec = agg.get("attr_total_decayed", 0)
        bfs_ratio = agg.get("bfs_collateral_ratio", 0)
        attr_ratio = agg.get("attr_collateral_ratio", 0)
        reduction = agg.get("total_reduction_pct", 0)

        bfs_dist = agg.get("bfs_weight_distribution", {})
        attr_dist = agg.get("attr_weight_distribution", {})

        hubs = agg.get("top_global_hubs", [])
        max_degree = hubs[0]["degree"] if hubs else 0
        max_hub = hubs[0]["entity"] if hubs else "N/A"

        rows.append({
            "size": size.upper(),
            "valid": valid,
            "bfs_decay": bfs_dec,
            "bfs_ratio": bfs_ratio,
            "attr_decay": attr_dec,
            "attr_ratio": attr_ratio,
            "reduction": reduction,
            "bfs_killed": bfs_dist.get("<0.1", 0),
            "attr_killed": attr_dist.get("<0.1", 0),
            "max_hub": max_hub,
            "max_degree": max_degree,
        })

    if rows:
        print(f"\n{'Scale':>6} | {'Valid':>6} | {'BFS Decay':>10} | {'Attr Decay':>11} | "
              f"{'Reduction':>10} | {'BFS <0.1':>9} | {'Attr <0.1':>10} | {'Max Hub':>20} | {'Degree':>6}")
        print("-" * 115)
        for r in rows:
            print(f"{r['size']:>6} | {r['valid']:>6} | "
                  f"{r['bfs_decay']:>5} ({r['bfs_ratio']:>5.1f}%) | "
                  f"{r['attr_decay']:>5} ({r['attr_ratio']:>5.1f}%) | "
                  f"{r['reduction']:>9.1f}% | "
                  f"{r['bfs_killed']:>9} | {r['attr_killed']:>10} | "
                  f"{r['max_hub']:>20} | {r['max_degree']:>6}")

    return rows


def analyze_adversarial():
    """C3: Adversarial Attack 분석"""
    print("\n" + "=" * 80)
    print("## C3: Adversarial Hub Exploitation")
    print("=" * 80)

    all_results = {}
    for size in ["6k", "32k"]:
        data = load_latest(f"adversarial_attack_{size}_*.json")
        if not data:
            print(f"  ⚠ {size} adversarial attack 결과 없음")
            continue
        all_results[size] = data

    if not all_results:
        return {}

    for size, data in all_results.items():
        summary = data.get("summary", {})
        print(f"\n### {size.upper()} Context")
        print(f"{'Attack':>8} | {'Mode':<16} | {'Damage%':>8} | {'Kill%':>6} | "
              f"{'Pre-EM':>7} | {'Post-EM':>8} | {'EM Drop':>8}")
        print("-" * 85)

        for key, modes in sorted(summary.items()):
            n_facts = key.split("_")[1]  # "attack_N_facts" → N
            for mode in ["bfs", "attribute_aware"]:
                d = modes.get(mode, {})
                if "error" in d:
                    continue
                print(f"{n_facts:>8} | {mode:<16} | "
                      f"{d.get('avg_damage_ratio_pct', 0):>7.1f}% | "
                      f"{d.get('avg_kill_ratio_pct', 0):>5.1f}% | "
                      f"{d.get('avg_pre_attack_em', 0):>6.1f}% | "
                      f"{d.get('avg_post_attack_em', 0):>7.1f}% | "
                      f"{d.get('avg_em_drop_pp', 0):>+7.1f}pp")

            diff = modes.get("bfs_vs_attr", {})
            if diff:
                vuln = "YES" if diff.get("bfs_more_vulnerable") else "NO"
                print(f"{'':>8} | {'→ BFS vuln?':<16} | "
                      f"{diff.get('damage_ratio_diff', 0):>+7.1f}pp | "
                      f"{diff.get('kill_ratio_diff', 0):>+5.1f}pp | "
                      f"{'':>7} | {'':>8} | {vuln:>8}")
            print()

    return all_results


def analyze_defense_effectiveness(scale_rows, adv_results):
    """C4: Defense 효과 요약"""
    print("\n" + "=" * 80)
    print("## C4: Attribute-aware Defense Effectiveness Summary")
    print("=" * 80)

    # Scale 트렌드에서 방어 효과
    if scale_rows:
        print("\n### Collateral Damage 방어")
        for r in scale_rows:
            if r["bfs_ratio"] > 0:
                defense_pct = (1 - r["attr_ratio"] / r["bfs_ratio"]) * 100
                kill_defense = (1 - r["attr_killed"] / max(r["bfs_killed"], 1)) * 100
                print(f"  {r['size']}: BFS {r['bfs_ratio']:.1f}% → Attr {r['attr_ratio']:.1f}% "
                      f"(방어율 {defense_pct:.1f}%, kill 방어율 {kill_defense:.1f}%)")

    # Adversarial에서 방어 효과
    if adv_results:
        print("\n### Adversarial Attack 방어")
        for size, data in adv_results.items():
            summary = data.get("summary", {})
            for key, modes in sorted(summary.items()):
                bfs = modes.get("bfs", {})
                attr = modes.get("attribute_aware", {})
                if "error" in bfs or "error" in attr:
                    continue
                bfs_dmg = bfs.get("avg_damage_ratio_pct", 0)
                attr_dmg = attr.get("avg_damage_ratio_pct", 0)
                if bfs_dmg > 0:
                    defense = (1 - attr_dmg / bfs_dmg) * 100
                    n = key.split("_")[1]
                    print(f"  {size.upper()} / {n} facts: BFS {bfs_dmg:.1f}% → Attr {attr_dmg:.1f}% "
                          f"(방어율 {defense:.1f}%)")


def generate_paper_tables(scale_rows, adv_results):
    """Paper용 Markdown 표 생성"""
    lines = ["# Workshop Paper Tables\n"]
    lines.append(f"Generated from experiments/analyze_all.py\n")

    # Table 1: Scale Trend
    lines.append("## Table 1: Collateral Damage Scale Trend\n")
    lines.append("| Scale | Valid Mem | BFS Decay (%) | Attr Decay (%) | Reduction (%) | BFS Kill (<0.1) | Max Hub Degree |")
    lines.append("|-------|----------|---------------|----------------|---------------|-----------------|----------------|")
    for r in (scale_rows or []):
        lines.append(f"| {r['size']} | {r['valid']:,} | {r['bfs_decay']:,} ({r['bfs_ratio']:.1f}%) | "
                     f"{r['attr_decay']:,} ({r['attr_ratio']:.1f}%) | {r['reduction']:.1f}% | "
                     f"{r['bfs_killed']:,} | {r['max_degree']} ({r['max_hub']}) |")

    # Table 2: Adversarial Attack
    lines.append("\n## Table 2: Adversarial Hub Exploitation (6K)\n")
    lines.append("| Attack Facts | BFS Damage (%) | BFS Kill (%) | Attr Damage (%) | BFS EM Drop | Amplification |")
    lines.append("|-------------|----------------|--------------|-----------------|-------------|---------------|")

    if adv_results and "6k" in adv_results:
        summary = adv_results["6k"].get("summary", {})
        for key, modes in sorted(summary.items()):
            n = key.split("_")[1]
            bfs = modes.get("bfs", {})
            attr = modes.get("attribute_aware", {})
            if "error" in bfs:
                continue
            bfs_dmg = bfs.get("avg_damage_ratio_pct", 0)
            attr_dmg = attr.get("avg_damage_ratio_pct", 0)
            bfs_kill = bfs.get("avg_kill_ratio_pct", 0)
            em_drop = bfs.get("avg_em_drop_pp", 0)
            amp = bfs_dmg / max(attr_dmg, 0.01)
            lines.append(f"| {n} | {bfs_dmg:.1f}% | {bfs_kill:.1f}% | {attr_dmg:.1f}% | "
                         f"{em_drop:+.1f}pp | {amp:.1f}x |")

    # Table 3: Defense Summary
    lines.append("\n## Table 3: Defense Effectiveness Across All Experiments\n")
    lines.append("| Experiment | BFS Damage | Attr Damage | Defense Rate |")
    lines.append("|------------|------------|-------------|--------------|")
    for r in (scale_rows or []):
        if r["bfs_ratio"] > 0:
            defense = (1 - r["attr_ratio"] / r["bfs_ratio"]) * 100
            lines.append(f"| CD {r['size']} | {r['bfs_ratio']:.1f}% | {r['attr_ratio']:.1f}% | {defense:.1f}% |")

    if adv_results:
        for size, data in adv_results.items():
            summary = data.get("summary", {})
            for key, modes in sorted(summary.items()):
                bfs = modes.get("bfs", {})
                attr = modes.get("attribute_aware", {})
                if "error" in bfs or "error" in attr:
                    continue
                bfs_d = bfs.get("avg_damage_ratio_pct", 0)
                attr_d = attr.get("avg_damage_ratio_pct", 0)
                if bfs_d > 0:
                    defense = (1 - attr_d / bfs_d) * 100
                    n = key.split("_")[1]
                    lines.append(f"| Adv {size.upper()} / {n}f | {bfs_d:.1f}% | {attr_d:.1f}% | {defense:.1f}% |")

    output_path = Path(__file__).parent.parent / "docs" / "paper_tables.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n표 저장: {output_path}")


def main():
    print("=" * 80)
    print("ADVERSARIAL FORGETTING WORKSHOP PAPER — 통합 분석")
    print("=" * 80)

    scale_rows = analyze_scale_trend()
    adv_results = analyze_adversarial()
    analyze_defense_effectiveness(scale_rows, adv_results)
    generate_paper_tables(scale_rows, adv_results)

    print("\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == "__main__":
    main()
