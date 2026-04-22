#!/bin/bash
# scripts/run_and_archive_experiments.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TARGET_IP=${1:-127.0.0.1}

echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN}🚀 Day 53: 半自动关键实验复现与证据归档 (Artifact Snapshot) 🚀${NC}"
echo -e "${GREEN}=================================================================${NC}"
echo -e "目标服务器 IP: ${TARGET_IP}"

# [修改 2]: 明确提示执行位置
echo -e "${YELLOW}[!] ⚠️ 严正声明：该归档脚本要求在承载 issuer/verifier/pir_server/auditor 的同一台云服务器上执行。${NC}"
echo -e "${YELLOW}[!] 若在本地机器执行，将无法正确打包服务端的 logs/*.log 和 Git 脏状态。${NC}\n"

# [修改 4]: 使用时间戳目录，禁止暴力覆盖历史数据
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SNAPSHOT_DIR="results/artifact_snapshot_${TIMESTAMP}"
mkdir -p "$SNAPSHOT_DIR"
echo -e "[*] 创建快照归档目录: $SNAPSHOT_DIR"

# 1. 获取 Git Commit Hash 与脏状态 (Working Tree)
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    COMMIT_HASH=$(git rev-parse HEAD)
    echo "Git Commit Hash: $COMMIT_HASH" > $SNAPSHOT_DIR/commit_hash.txt
    echo -e "\nGit Status:" >> $SNAPSHOT_DIR/commit_hash.txt
    git status -s >> $SNAPSHOT_DIR/commit_hash.txt

    # [修改 3]: 补齐 diff 快照，固化“工作区脏状态”
    echo -e "\nGit Diff Stat:" >> $SNAPSHOT_DIR/commit_hash.txt
    git diff --stat >> $SNAPSHOT_DIR/commit_hash.txt || true
    git diff > $SNAPSHOT_DIR/working_tree.diff || true

    echo -e "[*] 已提取代码库快照版本与 Git Diff: ${YELLOW}${COMMIT_HASH}${NC}"
else
    echo "Not a git repository" > $SNAPSHOT_DIR/commit_hash.txt
    echo -e "${YELLOW}[!] 当前不在 Git 仓库中，跳过 Hash 与 Diff 提取。${NC}"
fi

# 2. 备份脚本启动时的配置
cp configs/common/base.yaml $SNAPSHOT_DIR/base_at_script_start.yaml
echo -e "[*] 脚本启动时的 base.yaml 状态已备份进快照。"

# [修改 6]: 生成复现 Manifest 清单
cat > $SNAPSHOT_DIR/manifest.txt <<EOF
timestamp=$TIMESTAMP
target_ip=$TARGET_IP
run_script=scripts/run_and_archive_experiments.sh
day51_admission=python3 scripts/test_day51_ablation.py $TARGET_IP --attack admission
day51_binding=python3 scripts/test_day51_ablation.py $TARGET_IP --attack binding
day51_consume=python3 scripts/test_day51_ablation.py $TARGET_IP --attack replay
day51_epoch=python3 scripts/test_day51_ablation.py $TARGET_IP --attack epoch
day52_eval=HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" python3 scripts/run_eval_suite.py $TARGET_IP
EOF
echo -e "[*] 实验执行 Manifest 清单已生成。"

# 3. 执行 Day 51 消融实验复现
echo -e "\n${YELLOW}▶ 第一阶段：Day 51 消融实验 (Ablation Study) 证据留档${NC}"
echo -e "为确保真实性，请在另外一个终端打开 configs/common/base.yaml 配合开关防线："

read -p ">> 1. 请将 disable_admission 设为 true (其他为 false)，重启 Issuer。完成后按回车继续..."
# [修改 1]: 每次执行前备份那一刻的 YAML
cp configs/common/base.yaml $SNAPSHOT_DIR/base_ablation_admission.yaml
python3 scripts/test_day51_ablation.py $TARGET_IP --attack admission > $SNAPSHOT_DIR/ablation_admission.log
echo -e "   ✅ Admission 穿透日志及配置已归档。"

read -p ">> 2. 请将 disable_binding 设为 true (其他改回 false)，重启 Verifier。完成后按回车继续..."
cp configs/common/base.yaml $SNAPSHOT_DIR/base_ablation_binding.yaml
python3 scripts/test_day51_ablation.py $TARGET_IP --attack binding > $SNAPSHOT_DIR/ablation_binding.log
echo -e "   ✅ Binding 穿透日志及配置已归档。"

read -p ">> 3. 请将 disable_consume_lock 设为 true (其他改回 false)，重启 Verifier。完成后按回车继续..."
cp configs/common/base.yaml $SNAPSHOT_DIR/base_ablation_consume.yaml
python3 scripts/test_day51_ablation.py $TARGET_IP --attack replay > $SNAPSHOT_DIR/ablation_consume.log
echo -e "   ✅ Consume (状态机) 穿透日志及配置已归档。"

read -p ">> 4. 请将 disable_epoch 设为 true (其他改回 false)，且 duration_sec 改为 5。重启 Verifier。完成后按回车继续..."
cp configs/common/base.yaml $SNAPSHOT_DIR/base_ablation_epoch.yaml
python3 scripts/test_day51_ablation.py $TARGET_IP --attack epoch > $SNAPSHOT_DIR/ablation_epoch.log
echo -e "   ✅ Epoch (时间窗) 穿透日志及配置已归档。"

echo -e "${GREEN}[✔] Day 51 四大消融实验全部复现并留档！${NC}"

# 4. 执行 Day 52 全量跑分复现
echo -e "\n${YELLOW}▶ 第二阶段：Day 52 全量性能基准测试 (Benchmarks) 证据留档${NC}"
echo -e "${RED}⚠️ 终极跑分前的重要清理准备：${NC}"
echo -e "  1. 必须将 base.yaml 中 ablation 下的所有开关恢复为 false！"
echo -e "  2. 必须将 epoch duration_sec 恢复为 3600！"
echo -e "  3. 必须重启 Issuer 和 Verifier 进程以进入全甲状态！"
read -p ">> 全部恢复并重启完成后，按回车开始系统终极跑分..."

# [修改 1]: 记录 Benchmark 阶段最终纯净版 YAML
cp configs/common/base.yaml $SNAPSHOT_DIR/base_benchmark_clean.yaml

# 使用纯净环境运行跑分脚本，剔除本地代理干扰，保存终端输出
HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" http_proxy="" https_proxy="" all_proxy="" \
python3 scripts/run_eval_suite.py $TARGET_IP | tee $SNAPSHOT_DIR/eval_suite_output.log

# 提取生成的 JSON 并存入快照
if [ -f results/eval_report_day52.json ]; then
    cp results/eval_report_day52.json $SNAPSHOT_DIR/
    echo -e "   ✅ 跑分报告 JSON 已成功归档。"
else
    echo "[ERROR] missing: results/eval_report_day52.json. run_eval_suite.py execution likely failed or interrupted." > $SNAPSHOT_DIR/missing_eval_report.txt
    echo -e "${RED}[!] 未找到 eval_report_day52.json，已在快照中生成 missing_eval_report.txt 错误留档。${NC}"
fi

# 5. 提取服务器核心运行日志 (保留最后 1000 行作为现场证据)
echo -e "\n[*] 正在提取系统微服务后台日志..."
tail -n 1000 logs/issuer.log > $SNAPSHOT_DIR/issuer_tail.log 2>/dev/null || true
tail -n 1000 logs/verifier.log > $SNAPSHOT_DIR/verifier_tail.log 2>/dev/null || true
tail -n 1000 logs/pir_server.log > $SNAPSHOT_DIR/pir_server_tail.log 2>/dev/null || true
tail -n 1000 logs/auditor.log > $SNAPSHOT_DIR/auditor_tail.log 2>/dev/null || true

# 6. 打包终极归档
echo -e "\n${YELLOW}▶ 第三阶段：生成不可篡改的只读归档 (Artifact Tarball)${NC}"
ARCHIVE_NAME="results/PIR_Abuse_Control_Artifacts_${TIMESTAMP}.tar.gz"

# 将整个带时间戳的快照目录打包
tar -czvf $ARCHIVE_NAME -C results $(basename $SNAPSHOT_DIR) > /dev/null
echo -e "\n${GREEN}[✔] 所有的实验代码状态、中间配置、跑分结果、及运行日志已全部打包封存！${NC}"
echo -e "${GREEN}[✔] 终极归档文件位置: ${ARCHIVE_NAME}${NC}"
echo -e "\n================================================================="
echo -e "🎉 恭喜战友！《PIR 匿名抗滥用访问控制原型》历时8周，至此全线竣工！ 🎉"
echo -e "================================================================="