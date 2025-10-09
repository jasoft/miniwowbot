#!/bin/bash
# 异世界勇者副本定时任务管理脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本目录
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
DAILY_PLIST="$LAUNCH_AGENTS_DIR/com.weiwang.dungeons.daily.plist"
CLEANUP_PLIST="$LAUNCH_AGENTS_DIR/com.weiwang.dungeons.cleanup.plist"
LOG_DIR="$HOME/cron_logs"

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
${BLUE}异世界勇者副本定时任务管理脚本${NC}

使用方法:
  ./manage_dungeons_schedule.sh [命令]

命令:
  status          显示任务状态
  start           启动定时任务
  stop            停止定时任务
  restart         重启定时任务
  test            手动运行一次副本任务
  test-wake       测试Mac唤醒功能
  logs            查看最近的日志
  clean-logs      手动清理旧日志
  uninstall       完全卸载定时任务
  help            显示此帮助信息

示例:
  ./manage_dungeons_schedule.sh status
  ./manage_dungeons_schedule.sh test
  ./manage_dungeons_schedule.sh logs

EOF
}

show_status() {
    print_info "检查launchd任务状态..."
    echo ""
    
    # 检查任务是否已加载
    if launchctl list | grep -q "com.weiwang.dungeons.daily"; then
        print_success "每日副本任务已加载"
    else
        print_error "每日副本任务未加载"
    fi
    
    if launchctl list | grep -q "com.weiwang.dungeons.cleanup"; then
        print_success "日志清理任务已加载"
    else
        print_error "日志清理任务未加载"
    fi
    
    echo ""
    print_info "任务详细信息:"
    launchctl list | grep "com.weiwang.dungeons" | while read -r line; do
        echo "  $line"
    done
    
    echo ""
    print_info "下次运行时间: 每天早上 6:05"
    print_info "日志目录: $LOG_DIR"
    print_info "日志文件数量: $(ls -1 "$LOG_DIR"/dungeons_*.log 2>/dev/null | wc -l)"
}

start_jobs() {
    print_info "启动定时任务..."
    
    if [ -f "$DAILY_PLIST" ]; then
        launchctl load "$DAILY_PLIST" 2>/dev/null
        print_success "每日副本任务已启动"
    else
        print_error "每日副本任务配置文件不存在: $DAILY_PLIST"
    fi
    
    if [ -f "$CLEANUP_PLIST" ]; then
        launchctl load "$CLEANUP_PLIST" 2>/dev/null
        print_success "日志清理任务已启动"
    else
        print_error "日志清理任务配置文件不存在: $CLEANUP_PLIST"
    fi
}

stop_jobs() {
    print_info "停止定时任务..."
    
    launchctl unload "$DAILY_PLIST" 2>/dev/null
    print_success "每日副本任务已停止"
    
    launchctl unload "$CLEANUP_PLIST" 2>/dev/null
    print_success "日志清理任务已停止"
}

restart_jobs() {
    print_info "重启定时任务..."
    stop_jobs
    sleep 1
    start_jobs
}

test_run() {
    print_info "手动运行一次副本任务..."
    print_warning "这将立即开始运行所有角色的副本，请确保游戏已启动"
    read -p "确认要继续吗? (y/N): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        launchctl start com.weiwang.dungeons.daily
        print_success "任务已启动，请查看日志了解运行情况"
        sleep 2
        show_logs
    else
        print_info "已取消"
    fi
}

show_logs() {
    print_info "显示最近的日志文件..."
    
    # 显示最新的3个日志文件
    ls -t "$LOG_DIR"/dungeons_*.log 2>/dev/null | head -3 | while read -r logfile; do
        echo ""
        print_info "文件: $(basename "$logfile")"
        echo "----------------------------------------"
        tail -20 "$logfile"
        echo "----------------------------------------"
    done
    
    # 显示launchd自身的日志
    if [ -f "$LOG_DIR/launchd_dungeons_stderr.log" ]; then
        echo ""
        print_info "Launchd错误日志:"
        echo "----------------------------------------"
        cat "$LOG_DIR/launchd_dungeons_stderr.log"
        echo "----------------------------------------"
    fi
}

clean_logs() {
    print_info "清理30天前的日志文件..."
    
    count=$(find "$LOG_DIR" -name "dungeons_*.log" -mtime +30 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        find "$LOG_DIR" -name "dungeons_*.log" -mtime +30 -delete
        print_success "已删除 $count 个旧日志文件"
    else
        print_info "没有需要清理的旧日志文件"
    fi
}

test_wake() {
    print_info "测试Mac唤醒功能..."
    print_warning "这将创建一个临时定时任务，在2分钟后尝试唤醒Mac"
    
    # 计算2分钟后的时间
    current_minute=$(date '+%M' | sed 's/^0//')
    current_hour=$(date '+%H' | sed 's/^0//')
    test_minute=$((current_minute + 2))
    test_hour=$current_hour
    
    if [ $test_minute -ge 60 ]; then
        test_minute=$((test_minute - 60))
        test_hour=$((test_hour + 1))
    fi
    
    if [ $test_hour -ge 24 ]; then
        test_hour=0
    fi
    
    print_info "将在 $(printf '%02d:%02d' $test_hour $test_minute) 测试唤醒"
    
    # 创建临时测试配置
    cat > "/tmp/test_wake.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.weiwang.dungeons.waketest</string>
    <key>Program</key>
    <string>/Users/weiwang/Projects/异世界勇者.air/helper/test_wake.sh</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$test_hour</integer>
        <key>Minute</key>
        <integer>$test_minute</integer>
    </dict>
    <key>WakeSystem</key>
    <true/>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
</dict>
</plist>
EOF
    
    # 加载测试任务
    cp "/tmp/test_wake.plist" "$HOME/Library/LaunchAgents/com.weiwang.dungeons.waketest.plist"
    launchctl load "$HOME/Library/LaunchAgents/com.weiwang.dungeons.waketest.plist"
    
    print_success "测试任务已设置，现在可以让Mac进入睡眠模式"
    print_info "按Cmd+Option+Eject或关闭显示器让Mac进入睡眠"
    print_info "如果成功，Mac将在2分钟后唤醒并显示通知"
    
    read -p "测试完成后按回车清理测试任务..."
    
    # 清理测试任务
    launchctl unload "$HOME/Library/LaunchAgents/com.weiwang.dungeons.waketest.plist" 2>/dev/null
    rm -f "$HOME/Library/LaunchAgents/com.weiwang.dungeons.waketest.plist"
    rm -f "/tmp/test_wake.plist"
    
    print_success "测试任务已清理"
    print_info "检查 $LOG_DIR 中的 wake_test_*.log 文件查看测试结果"
}

uninstall_jobs() {
    print_warning "这将完全删除所有定时任务配置"
    read -p "确认要卸载吗? (y/N): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        print_info "卸载定时任务..."
        
        # 停止任务
        stop_jobs
        
        # 删除配置文件
        rm -f "$DAILY_PLIST"
        rm -f "$CLEANUP_PLIST"
        
        print_success "定时任务已完全卸载"
        print_info "日志文件保留在: $LOG_DIR"
    else
        print_info "已取消"
    fi
}

# 主函数
main() {
    case "${1:-help}" in
        "status")
            show_status
            ;;
        "start")
            start_jobs
            ;;
        "stop")
            stop_jobs
            ;;
        "restart")
            restart_jobs
            ;;
        "test")
            test_run
            ;;
        "test-wake")
            test_wake
            ;;
        "logs")
            show_logs
            ;;
        "clean-logs")
            clean_logs
            ;;
        "uninstall")
            uninstall_jobs
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

main "$@"