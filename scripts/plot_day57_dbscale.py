# scripts/plot_day57_dbscale.py
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import os

# 设置全局绘图样式 (适用于学术论文)
plt.rcParams.update({
    'font.size': 12,
    'axes.labelsize': 14,
    'axes.titlesize': 16,
    'legend.fontsize': 12,
    'lines.linewidth': 2.5,
    'lines.markersize': 8
})


def main():
    root_path = Path(__file__).resolve().parent.parent
    agg_dir = root_path / "results" / "dbscale" / "aggregated"

    perf_csv = agg_dir / "dbscale_by_concurrency.csv"
    prot_csv = agg_dir / "dbscale_protection.csv"

    if not perf_csv.exists() or not prot_csv.exists():
        print("错误：找不到聚合的 CSV 文件，请确认路径。")
        return

    # ==========================================
    # 图 1：并发与吞吐量规模曲线 (Line Chart)
    # ==========================================
    df_perf = pd.read_csv(perf_csv)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    colors = {1: '#1f77b4', 2: '#ff7f0e', 4: '#2ca02c', 8: '#d62728'}
    markers = {1: 'o', 2: 's', 4: '^', 8: 'D'}

    # 左图：Raw PIR 性能衰减
    raw_df = df_perf[df_perf['Mode'] == 'raw']
    for size in [1, 2, 4, 8]:
        sub_df = raw_df[raw_df['DB_Size_GB'] == size]
        if not sub_df.empty:
            ax1.plot(sub_df['Concurrency'], sub_df['Success_TPS'],
                     marker=markers[size], color=colors[size], label=f'{size} GB')

    ax1.set_title('Raw PIR Performance Scaling')
    ax1.set_xlabel('Concurrency')
    ax1.set_ylabel('Throughput (TPS)')
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend(title="DB Size")

    # 右图：Full System 性能 (展示 Legit Overhead)
    full_df = df_perf[df_perf['Mode'] == 'full']
    for size in [1, 2, 4, 8]:
        sub_df = full_df[full_df['DB_Size_GB'] == size]
        if not sub_df.empty:
            ax2.plot(sub_df['Concurrency'], sub_df['Success_TPS'],
                     marker=markers[size], color=colors[size], label=f'{size} GB')

    ax2.set_title('Full System (Protected) Performance')
    ax2.set_xlabel('Concurrency')
    ax2.set_ylabel('Throughput (TPS)')
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.legend(title="DB Size")

    plt.tight_layout()
    fig1_path = agg_dir / "fig_dbscale_throughput.pdf"
    plt.savefig(fig1_path, format='pdf', bbox_inches='tight')
    print(f"✅ 图表 1 已保存: {fig1_path}")

    # ==========================================
    # 图 2：纵深防御拦截栈 (Stacked Bar Chart)
    # ==========================================
    df_prot = pd.read_csv(prot_csv)

    fig2, ax = plt.subplots(figsize=(10, 6))

    db_sizes = [1, 2, 4, 8]
    x_labels = [f"{s}GB" for s in db_sizes]
    x_pos = np.arange(len(db_sizes))
    width = 0.35

    # 提取 L7-only 数据
    l7_only_df = df_prot[df_prot['Mode'] == 'l7_only'].set_index('DB_Size_GB')
    l7_blocked_l7mode = [l7_only_df.loc[s, 'L7_Blocked'] if s in l7_only_df.index else 0 for s in db_sizes]

    # 提取 Full System 数据
    full_df = df_prot[df_prot['Mode'] == 'full'].set_index('DB_Size_GB')
    l7_blocked_fullmode = [full_df.loc[s, 'L7_Blocked'] if s in full_df.index else 0 for s in db_sizes]
    l4_blocked_fullmode = [full_df.loc[s, 'L4_Blocked'] if s in full_df.index else 0 for s in db_sizes]

    # 绘制 L7-only 柱子
    ax.bar(x_pos - width / 2, l7_blocked_l7mode, width, label='L7 Blocked (L7-only mode)', color='#d62728', hatch='//')

    # 绘制 Full 柱子 (堆叠)
    ax.bar(x_pos + width / 2, l7_blocked_fullmode, width, label='L7 Blocked (Full mode)', color='#ff9896')
    ax.bar(x_pos + width / 2, l4_blocked_fullmode, width, bottom=l7_blocked_fullmode, label='L4 Blocked (eBPF)',
           color='#2ca02c')

    ax.set_title('Defense-in-Depth: L4 vs L7 Intercepts (300 Replay Attacks)')
    ax.set_xlabel('Database Size')
    ax.set_ylabel('Number of Blocked Requests')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels)
    ax.legend(loc='lower right')
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    fig2_path = agg_dir / "fig_dbscale_protection.pdf"
    plt.savefig(fig2_path, format='pdf', bbox_inches='tight')
    print(f"✅ 图表 2 已保存: {fig2_path}")


if __name__ == "__main__":
    main()