import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# --- 1. 定位数据路径 ---
# 假设脚本在 scripts/ 下，数据在 results/mixed_workload/ 下
script_dir = Path(__file__).resolve().parent
results_dir = script_dir.parent / "results" / "mixed_workload"

with open(results_dir / "replay_mix_l7_only.json") as f:
    data_l7 = json.load(f)
with open(results_dir / "replay_mix_full.json") as f:
    data_full = json.load(f)

# --- 2. 全局画图设置 ---
plt.rcParams.update({
    'font.size': 13,
    'axes.labelsize': 14,
    'axes.titlesize': 15,
    'legend.fontsize': 12,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'figure.dpi': 300
})

ratios = ["ratio_10", "ratio_50", "ratio_90"]
ratio_labels = {"ratio_10": "10% Attack", "ratio_50": "50% Attack", "ratio_90": "90% Attack"}
all_ratios = ["ratio_0"] + ratios
c_levels_str = ["c_1", "c_10", "c_30", "c_50", "c_100"]
c_levels_int = [1, 10, 30, 50, 100]
x = np.arange(len(c_levels_int))

# ==============================================================================
# Figure 1: Attack Interception Shift (并排展示 L7-only vs Full)
# ==============================================================================
fig1, axes1 = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
fig1.suptitle('Figure 1: Attack Interception Shift\nObserved division of mitigation responsibility between L7 and L4',
              fontsize=16, y=1.08)

bar_width = 0.35

for i, ratio in enumerate(ratios):
    ax = axes1[i]
    l7_l4, l7_l7, l7_pen = [], [], []
    full_l4, full_l7, full_pen = [], [], []

    for c_str in c_levels_str:
        # 提取 L7-only 数据
        m_l7 = data_l7["sweep_data"][ratio][c_str]
        if m_l7.get("invalid_for_primary_plot", False):
            l7_l4.append(0);
            l7_l7.append(0);
            l7_pen.append(0)
        else:
            tot = m_l7["attack_metrics"]["actual_attack_count"]
            l7_l4.append((m_l7["attack_metrics"].get("l4_blocked", 0) / tot * 100) if tot else 0)
            l7_l7.append((m_l7["attack_metrics"].get("l7_blocked", 0) / tot * 100) if tot else 0)
            l7_pen.append((m_l7["attack_metrics"].get("penetrated", 0) / tot * 100) if tot else 0)

        # 提取 Full 数据
        m_full = data_full["sweep_data"][ratio][c_str]
        if m_full.get("invalid_for_primary_plot", False):
            full_l4.append(0);
            full_l7.append(0);
            full_pen.append(0)
        else:
            tot = m_full["attack_metrics"]["actual_attack_count"]
            full_l4.append((m_full["attack_metrics"].get("l4_blocked", 0) / tot * 100) if tot else 0)
            full_l7.append((m_full["attack_metrics"].get("l7_blocked", 0) / tot * 100) if tot else 0)
            full_pen.append((m_full["attack_metrics"].get("penetrated", 0) / tot * 100) if tot else 0)

    # 画 L7-only 柱子 (靠左)
    ax.bar(x - bar_width / 2, l7_l4, bar_width, label='L4 Blocked' if i == 0 else "", color='#aec7e8',
           edgecolor='black', hatch='//')
    ax.bar(x - bar_width / 2, l7_l7, bar_width, bottom=l7_l4, label='L7 Blocked' if i == 0 else "", color='#1f77b4',
           edgecolor='black', hatch='//')
    ax.bar(x - bar_width / 2, l7_pen, bar_width, bottom=np.array(l7_l4) + np.array(l7_l7),
           label='Penetrated' if i == 0 else "", color='#d62728', edgecolor='black', hatch='//')

    # 画 Full 柱子 (靠右)
    ax.bar(x + bar_width / 2, full_l4, bar_width, label='L4 Blocked (Full)' if i == 0 else "", color='#aec7e8',
           edgecolor='black')
    ax.bar(x + bar_width / 2, full_l7, bar_width, bottom=full_l4, label='L7 Blocked (Full)' if i == 0 else "",
           color='#1f77b4', edgecolor='black')
    ax.bar(x + bar_width / 2, full_pen, bar_width, bottom=np.array(full_l4) + np.array(full_l7),
           label='Penetrated (Full)' if i == 0 else "", color='#d62728', edgecolor='black')

    ax.set_xticks(x)
    ax.set_xticklabels(c_levels_int)
    ax.set_xlabel('Concurrency Level')
    ax.set_title(ratio_labels[ratio])
    ax.grid(axis='y', linestyle='--', alpha=0.5)

axes1[0].set_ylabel('Attack Outcome Share (%)')
fig1.legend(loc='lower center', bbox_to_anchor=(0.5, -0.05), ncol=6)
plt.tight_layout()
plt.savefig(results_dir / "fig1_attack_shift.pdf", bbox_inches='tight')

# ==============================================================================
# Figure 2: Legit Request Fate Breakdown
# ==============================================================================
fig2, axes2 = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
fig2.suptitle('Figure 2: Legit Request Fate Breakdown under Full System\nDissecting Same-Source Collateral Effects',
              fontsize=16, y=1.05)

width_single = 0.6

for i, ratio in enumerate(ratios):
    ax = axes2[i]
    succ, l4_fail, conn_err, l7_fail = [], [], [], []
    for c_str in c_levels_str:
        m = data_full["sweep_data"][ratio][c_str]

        # 处理异常样本点
        if m.get("invalid_for_primary_plot", False):
            succ.append(0);
            l4_fail.append(0);
            conn_err.append(0);
            l7_fail.append(0)
            continue

        legit = m["legit_metrics"]
        tot = legit["actual_legit_count"]
        if tot == 0:
            succ.append(0);
            l4_fail.append(0);
            conn_err.append(0);
            l7_fail.append(0)
            continue

        succ.append(legit.get("success_rate_pct", 0))
        l4_fail.append((legit.get("l4_failed", 0) / tot) * 100)
        conn_err.append((legit.get("conn_err", 0) / tot) * 100)
        l7_fail.append((legit.get("l7_failed", 0) / tot) * 100)

    # 堆叠图（已修改学术用语）
    ax.bar(x, succ, width_single, label='Success' if i == 0 else "", color='#2ca02c', edgecolor='black')
    ax.bar(x, l4_fail, width_single, bottom=succ, label='L4-style Failure Proxy' if i == 0 else "", color='#d62728',
           edgecolor='black')
    ax.bar(x, conn_err, width_single, bottom=np.array(succ) + np.array(l4_fail),
           label='Connection-Level Error' if i == 0 else "", color='#7f7f7f', edgecolor='black')
    ax.bar(x, l7_fail, width_single, bottom=np.array(succ) + np.array(l4_fail) + np.array(conn_err),
           label='L7 Failure' if i == 0 else "", color='#ff7f0e', edgecolor='black')

    ax.set_xticks(x)
    ax.set_xticklabels(c_levels_int)
    ax.set_xlabel('Concurrency Level')
    ax.set_title(ratio_labels[ratio])
    ax.set_ylim(0, 100)  # 严格锁定 0-100%
    ax.grid(axis='y', linestyle='--', alpha=0.5)

axes2[0].set_ylabel('Legitimate Outcome Share (%)')
fig2.legend(loc='lower center', bbox_to_anchor=(0.5, -0.05), ncol=4)
plt.tight_layout()
plt.savefig(results_dir / "fig2_legit_fate.pdf", bbox_inches='tight')

# ==============================================================================
# Figure 3: Legit P95 Latency Degradation (引入过滤机制与线性轴)
# ==============================================================================
fig3, axes3 = plt.subplots(1, 4, figsize=(20, 5), sharey=True)
fig3.suptitle('Figure 3: Legit P95 Latency Degradation\nComparing Latency for Surviving Honest Requests', fontsize=16,
              y=1.05)
ratio_labels_4 = {"ratio_0": "0% Attack"} | ratio_labels

MIN_SUCCESS_RATE = 10.0  # 统计 P95 的最小成功率阈值 (%)

for i, ratio in enumerate(all_ratios):
    ax = axes3[i]
    l7_lats, full_lats = [], []

    for c_str in c_levels_str:
        # -- L7 Data Extraction --
        m_l7_node = data_l7["sweep_data"][ratio][c_str]
        m_l7 = m_l7_node["legit_metrics"]
        if m_l7_node.get("invalid_for_primary_plot", False) or m_l7.get("success_rate_pct", 0) < MIN_SUCCESS_RATE:
            l7_lats.append(np.nan)
        else:
            l7_lats.append(m_l7["p95_latency_ms"] / 1000.0)

        # -- Full Data Extraction --
        m_full_node = data_full["sweep_data"][ratio][c_str]
        m_full = m_full_node["legit_metrics"]
        if m_full_node.get("invalid_for_primary_plot", False) or m_full.get("success_rate_pct", 0) < MIN_SUCCESS_RATE:
            full_lats.append(np.nan)
        else:
            full_lats.append(m_full["p95_latency_ms"] / 1000.0)

    ax.plot(c_levels_int, l7_lats, marker='o', linestyle='--', linewidth=2, color='#ff7f0e',
            label='L7-only System' if i == 0 else "")
    ax.plot(c_levels_int, full_lats, marker='s', linestyle='-', linewidth=2.5, color='#2ca02c',
            label='Full System (w/ eBPF)' if i == 0 else "")

    # 恢复线性 X 轴，使用刻度直接映射
    ax.set_xticks(c_levels_int)
    ax.set_xlabel('Concurrency Level (Linear)')
    ax.set_title(ratio_labels_4[ratio])
    ax.grid(True, linestyle='--', alpha=0.6)

axes3[0].set_ylabel('P95 Latency (Seconds)')
# 如果需要的话，Y轴可以继续保留 log 以适应跨度
# axes3[0].set_yscale('log')

fig3.legend(loc='lower center', bbox_to_anchor=(0.5, -0.05), ncol=2)
plt.tight_layout()
plt.savefig(results_dir / "fig3_p95_latency.pdf", bbox_inches='tight')

print(f"🎉 论文图表已生成至: {results_dir}")