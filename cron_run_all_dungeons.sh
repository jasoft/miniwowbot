#!/bin/bash
# 自动化副本运行的 cron 包装脚本
# 每天早上6:05自动执行所有角色的副本

# 设置环境变量
export DISPLAY=:0
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8

# 创建日志目录
LOG_DIR="$HOME/cron_logs"
mkdir -p "$LOG_DIR"

# 生成时间戳和日志文件名
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/dungeons_$TIMESTAMP.log"

# 切换到脚本目录
cd "/Users/weiwang/Projects/异世界勇者.air/helper" || {
    echo "Failed to change directory to helper folder" >> "$LOG_FILE"
    exit 1
}

# 确保 PATH 包含必要的路径
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 记录系统状态和唤醒信息
echo "=====================================" >> "$LOG_FILE"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "执行目录: $(pwd)" >> "$LOG_FILE"
echo "系统正常运行时间: $(uptime)" >> "$LOG_FILE"
echo "当前用户: $(whoami)" >> "$LOG_FILE"
echo "显示会话: $DISPLAY" >> "$LOG_FILE"
echo "=====================================" >> "$LOG_FILE"

# 等待系统完全唤醒和GUI会话准备就绪
echo "等待系统和GUI会话完全准备就绪..." >> "$LOG_FILE"
sleep 30

# 检查是否有活跃的GUI会话
if ! pgrep -x "WindowServer" > /dev/null; then
    echo "警告: WindowServer未运行，可能GUI会话未准备就绪" >> "$LOG_FILE"
    sleep 10
fi

echo "系统准备完成，开始执行副本任务..." >> "$LOG_FILE"

# 运行主脚本，并将输出重定向到日志文件
./run_all_dungeons.sh --no-prompt >> "$LOG_FILE" 2>&1

# 记录结束状态
exit_code=$?
echo "" >> "$LOG_FILE"
echo "=====================================" >> "$LOG_FILE"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "退出代码: $exit_code" >> "$LOG_FILE"
echo "=====================================" >> "$LOG_FILE"

# 如果有错误，发送通知（可选）
if [ $exit_code -ne 0 ]; then
    # 可以在这里添加通知逻辑，比如发送邮件或者系统通知
    osascript -e "display notification \"异世界勇者副本运行失败，请查看日志\" with title \"游戏自动化\""
fi

exit $exit_code