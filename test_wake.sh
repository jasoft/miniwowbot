#!/bin/bash
# 测试Mac唤醒功能的脚本

LOG_FILE="$HOME/cron_logs/wake_test_$(date '+%Y-%m-%d_%H-%M-%S').log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "===== 唤醒测试日志 =====" >> "$LOG_FILE"
echo "唤醒时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "系统正常运行时间: $(uptime)" >> "$LOG_FILE"
echo "当前用户: $(whoami)" >> "$LOG_FILE"
echo "显示会话: ${DISPLAY:-未设置}" >> "$LOG_FILE"
echo "WindowServer进程: $(pgrep -x WindowServer || echo '未找到')" >> "$LOG_FILE"

# 发送系统通知
osascript -e "display notification \"Mac已成功从睡眠中唤醒！\" with title \"唤醒测试\""

echo "测试完成" >> "$LOG_FILE"
echo "=====================" >> "$LOG_FILE"

exit 0