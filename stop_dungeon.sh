#!/bin/bash
# 停止正在运行的 auto_dungeon.py 脚本
# 通过创建停止信号文件实现优雅停止

STOP_FILE=".stop_dungeon"

echo "========================================"
echo "停止 Auto Dungeon 执行"
echo "========================================"
echo ""

# 检查是否有正在运行的进程
if pgrep -f "auto_dungeon.py" > /dev/null; then
    echo "✓ 检测到正在运行的 auto_dungeon.py 进程"
    echo ""
    echo "创建停止信号文件: $STOP_FILE"
    touch "$STOP_FILE"
    echo "✓ 停止信号已发送"
    echo ""
    echo "📝 脚本将在当前副本完成后优雅停止"
    echo "⏳ 请等待几秒钟..."
    echo ""

    # 等待最多30秒，检查进程是否停止
    for i in {1..30}; do
        sleep 1
        if ! pgrep -f "auto_dungeon.py" > /dev/null; then
            echo "✅ 进程已成功停止"
            # 清理停止文件（如果还存在）
            if [ -f "$STOP_FILE" ]; then
                rm "$STOP_FILE"
            fi
            exit 0
        fi
        echo -n "."
    done

    echo ""
    echo "⚠️  进程仍在运行，可能需要更长时间"
    echo "💡 提示: 如果需要强制停止，使用以下命令:"
    echo "   pkill -f auto_dungeon.py"
    echo ""
else
    echo "ℹ️  没有检测到正在运行的 auto_dungeon.py 进程"
    echo ""
    # 清理可能残留的停止文件
    if [ -f "$STOP_FILE" ]; then
        echo "清理残留的停止信号文件..."
        rm "$STOP_FILE"
        echo "✓ 已清理"
    fi
fi

echo "========================================"
