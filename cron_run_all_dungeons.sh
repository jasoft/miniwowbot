
# 使用 osascript 在独立终端窗口中运行两个模拟器的副本脚本
# 启动后立即退出，让终端窗口独立运行

# 切换到脚本目录
SCRIPT_DIR="/Users/weiwang/Projects/miniwow"
cd "$SCRIPT_DIR" || {
    echo "❌ 无法切换到目录: $SCRIPT_DIR"
    exit 1
}

# 创建日志目录
LOG_DIR="$HOME/cron_logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

echo "====================================="
echo "🚀 启动两个模拟器的副本脚本"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "====================================="



# 模拟器 1: emulator-5554 (使用默认配置)
EMU1="127.0.0.1:5555"
LOG1="$LOG_DIR/emu_5554_$TIMESTAMP.log"

echo ""
echo "📱 模拟器 1: $EMU1"
echo "⚙️  配置: 默认"
echo "📝 日志: $LOG1"

# 使用 osascript 启动终端窗口
osascript -e "tell application \"Terminal\"" \
          -e "activate" \
          -e "do script \"cd '$SCRIPT_DIR' && export PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH' && echo '🎮 开始运行副本 - 模拟器: $EMU1' | /usr/bin/tee -a '$LOG1' && echo '⚙️  配置文件: 默认' | /usr/bin/tee -a '$LOG1' && ./run_all_dungeons.sh --emulator $EMU1 2>&1 | /usr/bin/tee -a '$LOG1' && echo '✅ 模拟器 $EMU1 完成' | /usr/bin/tee -a '$LOG1' || echo '❌ 模拟器 $EMU1 失败' | /usr/bin/tee -a '$LOG1'; echo '按任意键关闭窗口...'; read\"" \
          -e "end tell"

echo "✅ 已启动终端窗口: $EMU1"

# 间隔 2 秒再启动第二个
sleep 2

# 模拟器 2: emulator-5564 (使用 mage_alt 配置)
EMU2="127.0.0.1:5565"
LOG2="$LOG_DIR/emu_5564_$TIMESTAMP.log"

echo ""
echo "📱 模拟器 2: $EMU2"
echo "⚙️  配置: mage_alt"
echo "📝 日志: $LOG2"

# 使用 osascript 启动终端窗口
osascript -e "tell application \"Terminal\"" \
          -e "activate" \
          -e "do script \"cd '$SCRIPT_DIR' && export PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH' && echo '🎮 开始运行副本 - 模拟器: $EMU2' | /usr/bin/tee -a '$LOG2' && echo '⚙️  配置文件: mage_alt' | /usr/bin/tee -a '$LOG2' && ./run_all_dungeons.sh mage_alt --emulator $EMU2 2>&1 | /usr/bin/tee -a '$LOG2' && echo '✅ 模拟器 $EMU2 完成' | /usr/bin/tee -a '$LOG2' || echo '❌ 模拟器 $EMU2 失败' | /usr/bin/tee -a '$LOG2'; echo '按任意键关闭窗口...'; read\"" \
          -e "end tell"

echo "✅ 已启动终端窗口: $EMU2"

echo ""
echo "====================================="
echo "✅ 两个终端窗口已启动"
echo "====================================="
echo ""
echo "💡 提示："
echo "   - 模拟器 $EMU1: 使用默认配置"
echo "   - 模拟器 $EMU2: 使用 mage_alt 配置"
echo "   - 每个模拟器在独立的终端窗口中运行"
echo "   - 日志文件保存在: $LOG_DIR"
echo ""

exit 0
