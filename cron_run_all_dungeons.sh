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
LOCK_FILE="/tmp/cron_dungeons_$TIMESTAMP.lock"

# 切换到脚本目录
cd "/Users/weiwang/Projects/异世界勇者.air/helper" || {
    echo "Failed to change directory to helper folder" | tee -a "$LOG_FILE"
    exit 1
}

# 确保 PATH 包含必要的路径
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 定义日志函数，同时输出到控制台和日志文件（带文件锁防止混乱）
log() {
    # 使用文件锁确保日志写入的原子性
    (
        flock -x 200
        echo "$@" | tee -a "$LOG_FILE"
    ) 200>"$LOCK_FILE"
}

# 存储所有后台进程的 PID
declare -a background_pids

# 清理函数：杀死所有后台进程
cleanup() {
    log ""
    log "⛔ 收到中断信号，正在清理..."

    # 创建停止信号文件，让 Python 脚本优雅地停止
    touch ".stop_dungeon"
    log "📝 已创建停止信号文件: .stop_dungeon"

    # 给 Python 脚本一些时间来优雅地停止
    sleep 2

    # 杀死所有后台进程
    for pid in "${background_pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log "🔪 杀死进程 PID: $pid"
            kill -TERM "$pid" 2>/dev/null
            sleep 1
            # 如果进程仍在运行，强制杀死
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
        fi
    done

    # 删除停止信号文件
    rm -f ".stop_dungeon"

    log "✅ 清理完成"
    exit 130  # 128 + 2 (SIGINT)
}

# 设置信号处理器
trap cleanup SIGINT SIGTERM

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
sleep 10

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

# 检查是否启用多模拟器并行运行
PARALLEL_MODE=false
if [ "$1" = "--parallel" ]; then
    PARALLEL_MODE=true
    log "🚀 启用多模拟器并行运行模式"
fi

# 遍历所有账号
if [ "$PARALLEL_MODE" = true ]; then
    # 并行模式：同时启动所有模拟器和账号
    log "📱 准备并行启动 $ACCOUNT_COUNT 个账号..."

    declare -a pids

    for i in $(seq 0 $((ACCOUNT_COUNT - 1))); do
        # 读取账号信息
        ACCOUNT_NAME=$(jq -r ".accounts[$i].name" "$ACCOUNTS_FILE")
        ACCOUNT_PHONE=$(jq -r ".accounts[$i].phone" "$ACCOUNTS_FILE")
        RUN_SCRIPT=$(jq -r ".accounts[$i].run_script" "$ACCOUNTS_FILE")
        DESCRIPTION=$(jq -r ".accounts[$i].description" "$ACCOUNTS_FILE")
        EMULATOR=$(jq -r ".accounts[$i].emulator // empty" "$ACCOUNTS_FILE")

        # 为每个账号创建独立的日志文件
        ACCOUNT_LOG_FILE="$LOG_DIR/account_${ACCOUNT_PHONE}_$TIMESTAMP.log"

        log ""
        log "====================================="
        log "账号 $((i + 1))/$ACCOUNT_COUNT: $ACCOUNT_NAME"
        log "描述: $DESCRIPTION"
        log "手机号: $ACCOUNT_PHONE"
        if [ -n "$EMULATOR" ]; then
            log "模拟器: $EMULATOR"
        fi
        log "📝 日志文件: $ACCOUNT_LOG_FILE"
        log "====================================="

        # 在后台启动账号加载和脚本运行
        (
            # 加载账号
            echo "🔄 加载账号: $ACCOUNT_PHONE" | tee -a "$ACCOUNT_LOG_FILE"
            if [ -n "$EMULATOR" ]; then
                uv run auto_dungeon.py --load-account "$ACCOUNT_PHONE" --emulator "$EMULATOR" 2>&1 | tee -a "$ACCOUNT_LOG_FILE"
            else
                uv run auto_dungeon.py --load-account "$ACCOUNT_PHONE" 2>&1 | tee -a "$ACCOUNT_LOG_FILE"
            fi

            if [ ${PIPESTATUS[0]} -ne 0 ]; then
                echo "❌ 加载账号失败: $ACCOUNT_PHONE" | tee -a "$ACCOUNT_LOG_FILE"
                exit 1
            fi

            # 运行副本脚本
            echo "🎮 运行脚本: $RUN_SCRIPT --no-prompt" | tee -a "$ACCOUNT_LOG_FILE"
            if [ -n "$EMULATOR" ]; then
                $RUN_SCRIPT --no-prompt --emulator "$EMULATOR" 2>&1 | tee -a "$ACCOUNT_LOG_FILE"
            else
                $RUN_SCRIPT --no-prompt 2>&1 | tee -a "$ACCOUNT_LOG_FILE"
            fi
            exit_code=${PIPESTATUS[0]}

            if [ $exit_code -eq 0 ]; then
                echo "✅ 账号 $ACCOUNT_NAME 完成" | tee -a "$ACCOUNT_LOG_FILE"
            else
                echo "❌ 账号 $ACCOUNT_NAME 失败 (退出代码: $exit_code)" | tee -a "$ACCOUNT_LOG_FILE"
            fi
            exit $exit_code
        ) &

        pids[$i]=$!
        background_pids+=("${pids[$i]}")
        log "📌 后台进程 PID: ${pids[$i]}"

        # 模拟器之间间隔启动，避免资源竞争
        sleep 3
    done

    # 等待所有后台进程完成（使用 wait -n 使其可中断）
    log ""
    log "⏳ 等待所有账号处理完成..."

    # 使用 wait -n 替代 wait，这样可以被信号中断
    remaining_pids=("${pids[@]}")
    while [ ${#remaining_pids[@]} -gt 0 ]; do
        # 等待任意一个进程完成
        wait -n 2>/dev/null
        wait_status=$?

        # 更新剩余的 PID 列表
        new_remaining=()
        for pid in "${remaining_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                new_remaining+=("$pid")
            else
                # 进程已完成，获取其退出代码
                wait "$pid" 2>/dev/null
                exit_code=$?
                # 查找对应的账号索引
                for j in $(seq 0 $((ACCOUNT_COUNT - 1))); do
                    if [ "${pids[$j]}" = "$pid" ]; then
                        exit_codes[$j]=$exit_code
                        ACCOUNT_NAME=$(jq -r ".accounts[$j].name" "$ACCOUNTS_FILE")
                        if [ $exit_code -eq 0 ]; then
                            log "✅ 后台进程 $pid (账号 $ACCOUNT_NAME) 完成"
                        else
                            log "❌ 后台进程 $pid (账号 $ACCOUNT_NAME) 失败 (退出代码: $exit_code)"
                        fi
                        break
                    fi
                done
            fi
        done
        remaining_pids=("${new_remaining[@]}")
    done
else
    # 顺序模式：依次处理每个账号
    for i in $(seq 0 $((ACCOUNT_COUNT - 1))); do
        # 读取账号信息
        ACCOUNT_NAME=$(jq -r ".accounts[$i].name" "$ACCOUNTS_FILE")
        ACCOUNT_PHONE=$(jq -r ".accounts[$i].phone" "$ACCOUNTS_FILE")
        RUN_SCRIPT=$(jq -r ".accounts[$i].run_script" "$ACCOUNTS_FILE")
        DESCRIPTION=$(jq -r ".accounts[$i].description" "$ACCOUNTS_FILE")
        EMULATOR=$(jq -r ".accounts[$i].emulator // empty" "$ACCOUNTS_FILE")

        # 为每个账号创建独立的日志文件
        ACCOUNT_LOG_FILE="$LOG_DIR/account_${ACCOUNT_PHONE}_$TIMESTAMP.log"

        log ""
        log "====================================="
        log "账号 $((i + 1))/$ACCOUNT_COUNT: $ACCOUNT_NAME"
        log "描述: $DESCRIPTION"
        log "手机号: $ACCOUNT_PHONE"
        if [ -n "$EMULATOR" ]; then
            log "模拟器: $EMULATOR"
        fi
        log "📝 日志文件: $ACCOUNT_LOG_FILE"
        log "====================================="

        # 加载账号
        log "🔄 加载账号: $ACCOUNT_PHONE"
        if [ -n "$EMULATOR" ]; then
            uv run auto_dungeon.py --load-account "$ACCOUNT_PHONE" --emulator "$EMULATOR" 2>&1 | tee -a "$ACCOUNT_LOG_FILE" &
            pid=$!
        else
            uv run auto_dungeon.py --load-account "$ACCOUNT_PHONE" 2>&1 | tee -a "$ACCOUNT_LOG_FILE" &
            pid=$!
        fi

        background_pids+=("$pid")
        wait "$pid"
        load_status=$?

        if [ $load_status -ne 0 ]; then
            log "❌ 加载账号失败: $ACCOUNT_PHONE"
            exit_codes[$i]=1
            continue
        fi

        # 运行副本脚本
        log "🎮 运行脚本: $RUN_SCRIPT --no-prompt"
        if [ -n "$EMULATOR" ]; then
            $RUN_SCRIPT --no-prompt --emulator "$EMULATOR" 2>&1 | tee -a "$ACCOUNT_LOG_FILE" &
        else
            $RUN_SCRIPT --no-prompt 2>&1 | tee -a "$ACCOUNT_LOG_FILE" &
        fi
        pid=$!
        background_pids+=("$pid")
        wait "$pid"
        exit_codes[$i]=$?

        if [ ${exit_codes[$i]} -eq 0 ]; then
            log "✅ 账号 $ACCOUNT_NAME 完成"
        else
            log "❌ 账号 $ACCOUNT_NAME 失败 (退出代码: ${exit_codes[$i]})"
        fi
    done
fi

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

# 发送 Bark 通知
log ""
log "📱 发送 Bark 通知..."
uv run send_cron_notification.py "$success_count" "$failed_count" "$ACCOUNT_COUNT" 2>&1 | tee -a "$LOG_FILE"
if [ $? -eq 0 ]; then
    log "✅ Bark 通知发送成功"
else
    log "⚠️ Bark 通知发送失败或未启用"
fi

# 清理锁文件
rm -f "$LOCK_FILE"

exit $exit_code
