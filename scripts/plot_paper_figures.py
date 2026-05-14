# scripts/plot_paper_figures.py
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# ==========================================
# 全局学术绘图样式配置
# ==========================================
plt.rcParams.update({
    'font.size': 13,
    'axes.labelsize': 14,
    'axes.titlesize': 15,
    'legend.fontsize': 12,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'lines.linewidth': 2.5,
    'lines.markersize': 9,
    'figure.dpi': 300,
    'font.family': 'serif'  # 适合 LaTeX 风格
})


def main():
    root_path = Path(__file__).resolve().parent.parent
    agg_dir = root_path / "results" / "dbscale" / "aggregated"

    fig_dir = root_path / "results" / "dbscale" / "figures"
    fig_dir.mkdir(exist_ok=True, parents=True)

    perf_csv = agg_dir / "dbscale_by_concurrency.csv"
    prot_csv = agg_dir / "dbscale_protection.csv"

    if not perf_csv.exists() or not prot_csv.exists():
        print("❌ 错误：找不到 CSV 文件，请确认路径。")
        return

    # ==========================================
    # 图 1：DB Size vs TPS & Latency (选取最高并发 C=50)
    # ==========================================
    df_perf = pd.read_csv(perf_csv)
    df_c50 = df_perf[df_perf['Concurrency'] == 50]

    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    modes = ['raw', 'l7_only', 'full']
    labels = {'raw': 'Raw PIR', 'l7_only': 'L7-only Protection', 'full': 'Full System (eBPF)'}
    colors = {'raw': '#1f77b4', 'l7_only': '#ff7f0e', 'full': '#2ca02c'}
    markers = {'raw': 'o', 'l7_only': 's', 'full': '^'}
    linestyles = {'raw': '-', 'l7_only': '--', 'full': '-.'}

    db_sizes = sorted(df_c50['DB_Size_GB'].unique())

    # 左图：TPS vs DB Size
    for mode in modes:
        sub_df = df_c50[df_c50['Mode'] == mode].sort_values('DB_Size_GB')
        ax1.plot(sub_df['DB_Size_GB'], sub_df['Success_TPS'],
                 marker=markers[mode], color=colors[mode],
                 linestyle=linestyles[mode], label=labels[mode])

    ax1.set_title('Impact of Database Size on Throughput (C=50)')
    ax1.set_xlabel('Database Size (GB)')
    ax1.set_ylabel('Throughput (TPS)')
    ax1.set_xticks(db_sizes)
    ax1.grid(True, linestyle=':', alpha=0.7)
    ax1.legend()

    # 右图：Latency vs DB Size
    for mode in modes:
        sub_df = df_c50[df_c50['Mode'] == mode].sort_values('DB_Size_GB')
        ax2.plot(sub_df['DB_Size_GB'], sub_df['Avg_Latency_ms'] / 1000.0,
                 marker=markers[mode], color=colors[mode],
                 linestyle=linestyles[mode], label=labels[mode])

    ax2.set_title('Impact of Database Size on Average Latency (C=50)')
    ax2.set_xlabel('Database Size (GB)')
    ax2.set_ylabel('Average Latency (Seconds)')
    ax2.set_xticks(db_sizes)
    ax2.grid(True, linestyle=':', alpha=0.7)
    ax2.legend()

    plt.tight_layout()
    fig1_path = fig_dir / "fig1_dbscale_performance.pdf"
    plt.savefig(fig1_path, format='pdf', bbox_inches='tight')
    print(f"✅ 图 1 (性能规模折线图) 已保存至: {fig1_path}")

    # ==========================================
    # 图 2：DB Size vs L7/L4 Blocked Breakdown
    # ==========================================
    df_prot = pd.read_csv(prot_csv)

    fig2, ax = plt.subplots(figsize=(8, 6))

    x_pos = np.arange(len(db_sizes))
    width = 0.35

    l7_only_df = df_prot[df_prot['Mode'] == 'l7_only'].set_index('DB_Size_GB')
    l7_blocked_l7mode = [l7_only_df.loc[s, 'L7_Blocked'] if s in l7_only_df.index else 0 for s in db_sizes]

    full_df = df_prot[df_prot['Mode'] == 'full'].set_index('DB_Size_GB')
    l7_blocked_fullmode = [full_df.loc[s, 'L7_Blocked'] if s in full_df.index else 0 for s in db_sizes]
    l4_blocked_fullmode = [full_df.loc[s, 'L4_Blocked'] if s in full_df.index else 0 for s in db_sizes]

    ax.bar(x_pos - width / 2, l7_blocked_l7mode, width,
           label='L7-only: Blocked by Verifier', color='#d62728', alpha=0.8, hatch='//')

    p1 = ax.bar(x_pos + width / 2, l7_blocked_fullmode, width,
                label='Full System: Blocked by Verifier (L7)', color='#ff9896')
    p2 = ax.bar(x_pos + width / 2, l4_blocked_fullmode, width,
                bottom=l7_blocked_fullmode,
                label='Full System: Blocked by eBPF (L4)', color='#2ca02c', alpha=0.9)

    ax.set_title('Replay Flood Mitigation Breakdown across L7 and L4')
    ax.set_xlabel('Database Size (GB)')
    ax.set_ylabel('Number of Blocked Malicious Requests')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{s}GB" for s in db_sizes])

    ax.legend(loc='lower left', bbox_to_anchor=(0, 1.02), ncol=1)
    ax.grid(axis='y', linestyle=':', alpha=0.7)

    # [优化] 在 Full 柱子内部标注 L4 接管的主力数据，并在顶部标注 Total
    for i in range(len(db_sizes)):
        total_blocked = l7_blocked_fullmode[i] + l4_blocked_fullmode[i]

        if l4_blocked_fullmode[i] > 0:
            # 突出展示 L4 的拦截量
            ax.text(x_pos[i] + width / 2, l7_blocked_fullmode[i] + (l4_blocked_fullmode[i] / 2),
                    f"L4: {l4_blocked_fullmode[i]}", ha='center', va='center', color='white', fontweight='bold',
                    fontsize=11)

        if total_blocked > 0:
            # 在顶部增加 Total 标注
            ax.text(x_pos[i] + width / 2, total_blocked + 5,
                    f"Total: {int(total_blocked)}", ha='center', va='bottom', color='black', fontsize=10)

    # 动态调整 Y 轴上限，防止 Total 标签被切掉
    current_ymax = ax.get_ylim()[1]
    ax.set_ylim(0, current_ymax + 15)

    plt.tight_layout()
    fig2_path = fig_dir / "fig2_defense_breakdown.pdf"
    plt.savefig(fig2_path, format='pdf', bbox_inches='tight')
    print(f"✅ 图 2 (拦截纵深堆叠图) 已保存至: {fig2_path}")


if __name__ == "__main__":
    main()