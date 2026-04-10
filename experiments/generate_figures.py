"""
논문용 Figure 생성 스크립트
- Figure 1: Degree Distribution (CCDF, Log-log plot)
- Figure 2: Propagation Depth vs Damage/Kill Curve
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

# --- 스타일 설정 ---
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif', 'serif'],
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'legend.fontsize': 8,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'lines.linewidth': 1.2,
    'lines.markersize': 4,
})

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / 'results'
FIGURES_DIR = BASE_DIR.parent / 'paper' / 'figures'
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# --- 데이터 로드 ---
with open(RESULTS_DIR / 'deep_dive_analysis.json', 'r') as f:
    data = json.load(f)


def generate_figure1():
    """Figure 1: Degree Distribution CCDF (Log-log plot)"""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    # 각 scale의 CCDF 데이터와 스타일
    scales = {
        '6k': {
            'label': '6K turns',
            'marker': 'o',
            'linestyle': '-',
            'color': '#333333',
            'fillstyle': 'full',
        },
        '32k': {
            'label': '32K turns',
            'marker': 's',
            'linestyle': '--',
            'color': '#666666',
            'fillstyle': 'full',
        },
        '64k': {
            'label': '64K turns',
            'marker': '^',
            'linestyle': '-.',
            'color': '#999999',
            'fillstyle': 'full',
        },
    }

    for scale, style in scales.items():
        topo = data['topology_analysis'][scale]
        ccdf_data = topo['ccdf_data']

        # degree=0 제외 (log scale에서 표시 불가)
        degrees = [d['degree'] for d in ccdf_data if d['degree'] > 0 and d['ccdf'] > 0]
        ccdfs = [d['ccdf'] for d in ccdf_data if d['degree'] > 0 and d['ccdf'] > 0]

        ax.plot(degrees, ccdfs,
                marker=style['marker'],
                linestyle=style['linestyle'],
                color=style['color'],
                fillstyle=style['fillstyle'],
                label=style['label'],
                markersize=4,
                markeredgewidth=0.6,
                markeredgecolor='black',
                zorder=3)

    # --- Power-law reference lines ---
    for scale, style in scales.items():
        alpha = data['topology_analysis'][scale]['power_law']['k_min_2']['alpha']
        k_range = np.logspace(np.log10(2), np.log10(50), 50)
        # CCDF ~ k^{-(alpha-1)} for power-law
        ccdf_fit = k_range ** (-(alpha - 1))
        # 정규화: k=2에서의 실제 CCDF와 맞추기
        ccdf_data = data['topology_analysis'][scale]['ccdf_data']
        ccdf_at_2 = next((d['ccdf'] for d in ccdf_data if d['degree'] == 2), 0.4)
        ccdf_fit = ccdf_fit * (ccdf_at_2 / ccdf_fit[0])

        ax.plot(k_range, ccdf_fit,
                linestyle=':',
                color=style['color'],
                alpha=0.6,
                linewidth=0.8,
                zorder=2)

    # 마지막 fit line에 대해 범례 항목 추가
    ax.plot([], [], linestyle=':', color='gray', alpha=0.6, linewidth=0.8,
            label=r'Power-law fit ($k^{-(\alpha-1)}$)')

    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('Degree $k$')
    ax.set_ylabel('CCDF $P(K \\geq k)$')
    ax.legend(loc='lower left', frameon=True, fancybox=False,
              edgecolor='gray', framealpha=0.9)
    ax.grid(True, which='major', linewidth=0.4, alpha=0.5)
    ax.grid(True, which='minor', linewidth=0.2, alpha=0.3)
    ax.set_xlim(0.8, 500)
    ax.set_ylim(5e-4, 1.5)

    fig.savefig(FIGURES_DIR / 'fig_degree_distribution.pdf', format='pdf')
    plt.close(fig)
    print(f"[OK] Figure 1 saved: {FIGURES_DIR / 'fig_degree_distribution.pdf'}")


def generate_figure2():
    """Figure 2: Propagation Depth vs Damage/Kill Curve"""
    fig, ax1 = plt.subplots(figsize=(3.5, 2.8))

    # --- 데이터 (hard-coded) ---
    depths = [1, 2, 3, 4]
    damage = [18.6, 39.8, 48.3, 55.8]
    kill = [0.3, 17.4, 32.9, 44.8]

    x = np.arange(len(depths))
    width = 0.35

    # Bar chart: damage (왼쪽 축)
    bars_damage = ax1.bar(x - width/2, damage, width,
                          color='#888888', edgecolor='black',
                          linewidth=0.6, label='Cumulative damage',
                          zorder=3)
    bars_kill = ax1.bar(x + width/2, kill, width,
                        color='white', edgecolor='black',
                        linewidth=0.6, hatch='///',
                        label='Node kill rate',
                        zorder=3)

    ax1.set_xlabel('Propagation Depth')
    ax1.set_ylabel('Percentage (%)')
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(d) for d in depths])
    ax1.set_ylim(0, 70)
    ax1.grid(True, axis='y', linewidth=0.4, alpha=0.5, zorder=0)

    # Line: damage trend
    ax1.plot(x, damage, marker='o', color='black', linestyle='-',
             linewidth=1.2, markersize=5, markerfacecolor='black',
             zorder=4, label='Damage trend')
    # Line: kill trend
    ax1.plot(x, kill, marker='s', color='black', linestyle='--',
             linewidth=1.2, markersize=5, markerfacecolor='white',
             markeredgecolor='black', markeredgewidth=0.8,
             zorder=4, label='Kill trend')

    # 값 표기
    for i, (d_val, k_val) in enumerate(zip(damage, kill)):
        ax1.annotate(f'{d_val}', (x[i] - width/2, d_val),
                     textcoords="offset points", xytext=(0, 4),
                     ha='center', fontsize=6.5, fontweight='bold')
        ax1.annotate(f'{k_val}', (x[i] + width/2, k_val),
                     textcoords="offset points", xytext=(0, 4),
                     ha='center', fontsize=6.5)

    ax1.legend(loc='upper left', frameon=True, fancybox=False,
               edgecolor='gray', framealpha=0.9, fontsize=7)

    fig.savefig(FIGURES_DIR / 'fig_propagation_damage.pdf', format='pdf')
    plt.close(fig)
    print(f"[OK] Figure 2 saved: {FIGURES_DIR / 'fig_propagation_damage.pdf'}")


if __name__ == '__main__':
    generate_figure1()
    generate_figure2()
    print("\nAll figures generated successfully.")
