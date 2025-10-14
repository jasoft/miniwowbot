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
    echo "Failed to change directory to helper folder" | tee -a "$LOG_FILE"
    exit 1
}

# 确保 PATH 包含必要的路径
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 定义日志函数，同时输出到控制台和日志文件
log() {
    echo "$@" | tee -a "$LOG_FILE"
}

# 记录系统状态和唤醒信息
log "====================================="
log "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
log "执行目录: $(pwd)"
log "系统正常运行时间: $(uptime)"
log "当前用户: $(whoami)"
log "显示会话: $DISPLAY"
log "====================================="

# 等待系统完全唤醒和GUI会话准备就绪
log "等待系统和GUI会话完全准备就绪..."
sleep 1cron0

# 检查是否有活跃的GUI会话
if ! pgrep -x "WindowServer" > /dev/null; then
    log "警告: WindowServer未运行，可能GUI会话未准备就绪"
    sleep 10
fi

log "系统准备完成，开始执行副本任务..."

# 读取账号配置文件
ACCOUNTS_FILE="accounts.json"
if [ ! -f "$ACCOUNTS_FILE" ]; then
    log "❌ 账号配置文件不存在: $ACCOUNTS_FILE"
    log "💡 请复制 accounts.json.example 为 accounts.json 并填入真实账号"
    exit 1
fi

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    log "❌ 需要安装 jq 来解析 JSON 配置文件"
    log "💡 请运行: brew install jq"
    exit 1
fi

# 获取账号数量
ACCOUNT_COUNT=$(jq '.accounts | length' "$ACCOUNTS_FILE")
log "📊 找到 $ACCOUNT_COUNT 个账号配置"

# 存储所有账号的退出代码
declare -a exit_codes

# 遍历所有账号
for i in $(seq 0 $((ACCOUNT_COUNT - 1))); do
    # 读取账号信息
    ACCOUNT_NAME=$(jq -r ".accounts[$i].name" "$ACCOUNTS_FILE")
    ACCOUNT_PHONE=$(jq -r ".accounts[$i].phone" "$ACCOUNTS_FILE")
    RUN_SCRIPT=$(jq -r ".accounts[$i].run_script" "$ACCOUNTS_FILE")
    DESCRIPTION=$(jq -r ".accounts[$i].description" "$ACCOUNTS_FILE")

    log ""
    log "====================================="
    log "账号 $((i + 1))/$ACCOUNT_COUNT: $ACCOUNT_NAME"
    log "描述: $DESCRIPTION"
    log "手机号: $ACCOUNT_PHONE"
    log "====================================="

    # 加载账号
    log "🔄 加载账号: $ACCOUNT_PHONE"
    uv run auto_dungeon.py --load-account "$ACCOUNT_PHONE" 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "❌ 加载账号失败: $ACCOUNT_PHONE"
        exit_codes[$i]=1
        continue
    fi

    # 运行副本脚本
    log "🎮 运行脚本: $RUN_SCRIPT --no-prompt"
    $RUN_SCRIPT --no-prompt 2>&1 | tee -a "$LOG_FILE"
    exit_codes[$i]=${PIPESTATUS[0]}

    if [ ${exit_codes[$i]} -eq 0 ]; then
        log "✅ 账号 $ACCOUNT_NAME 完成"
    else
        log "❌ 账号 $ACCOUNT_NAME 失败 (退出代码: ${exit_codes[$i]})"
    fi
done

# 记录结束状态
log ""
log "====================================="
log "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
log "====================================="

# 统计结果
success_count=0
failed_count=0
for i in $(seq 0 $((ACCOUNT_COUNT - 1))); do
    ACCOUNT_NAME=$(jq -r ".accounts[$i].name" "$ACCOUNTS_FILE")
    if [ ${exit_codes[$i]} -eq 0 ]; then
        log "✅ $ACCOUNT_NAME: 成功"
        ((success_count++))
    else
        log "❌ $ACCOUNT_NAME: 失败 (退出代码: ${exit_codes[$i]})"
        ((failed_count++))
    fi
done

log "====================================="
log "📊 总计: $ACCOUNT_COUNT 个账号"
log "✅ 成功: $success_count 个"
log "❌ 失败: $failed_count 个"
log "====================================="

# 发送通知的函数
send_notification() {
    local title="$1"
    local message="$2"
    local sound="${3:-Submarine}"  # 默认声音

    # 尝试使用 terminal-notifier（如果已安装）
    if command -v terminal-notifier &> /dev/null; then
        terminal-notifier -title "$title" -message "$message" -sound "$sound"
    # 否则使用 osascript（系统自带）
    else
        # 使用带声音的通知
        osascript -e "display notification \"$message\" with title \"$title\" sound name \"$sound\""

        # 如果上面失败，尝试不带声音
        if [ $? -ne 0 ]; then
            osascript -e "display notification \"$message\" with title \"$title\""
        fi
    fi

    # 同时打印到终端（作为后备）
    echo "📢 通知: [$title] $message"
}

# 计算总退出代码（任一失败则失败）
if [ $failed_count -gt 0 ]; then
    exit_code=1
    # 发送失败通知（带声音提醒）
    send_notification "游戏自动化 - 失败" "异世界勇者副本运行失败，请查看日志\n失败: $failed_count 个账号" "Basso"
else
    exit_code=0
    # 发送成功通知
    send_notification "游戏自动化 - 成功" "异世界勇者副本全部运行完成\n成功: $success_count 个账号" "Glass"
fi

exit $exit_code
