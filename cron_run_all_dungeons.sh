#!/bin/bash
# Cron 任务启动脚本
# 用于从 launchd 启动两个模拟器的副本脚本，并将日志输出到 Loki

# 切换到脚本目录
SCRIPT_DIR="/Users/weiwang/Projects/miniwow"
cd "$SCRIPT_DIR" || {
    echo "❌ 无法切换到目录: $SCRIPT_DIR"
    exit 1
}

# 设置环境变量
export LOKI_URL="${LOKI_URL:-http://localhost:3100}"
export LOKI_ENABLED="${LOKI_ENABLED:-true}"

# 调用 Python 启动器
python3 "$SCRIPT_DIR/cron_launcher.py"
exit $?


