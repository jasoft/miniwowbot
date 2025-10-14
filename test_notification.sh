#!/bin/bash
# 测试 macOS 通知

echo "🔔 测试 macOS 通知系统"
echo "===================="
echo ""

# 测试1: 基本通知
echo "测试 1: 基本通知（无声音）"
osascript -e 'display notification "这是一条测试通知" with title "测试1"'
echo "已发送，请检查通知中心（右上角）"
sleep 3
echo ""

# 测试2: 带声音的通知
echo "测试 2: 带声音的通知（Glass）"
osascript -e 'display notification "这是一条带声音的通知" with title "测试2" sound name "Glass"'
echo "已发送（应该听到声音）"
sleep 3
echo ""

# 测试3: 不同声音
echo "测试 3: 警告声音（Basso）"
osascript -e 'display notification "这是一条警告通知" with title "测试3" sound name "Basso"'
echo "已发送（应该听到低音）"
sleep 3
echo ""

# 测试4: 更响亮的声音
echo "测试 4: 响亮声音（Funk）"
osascript -e 'display notification "这是一条响亮通知" with title "测试4" sound name "Funk"'
echo "已发送"
sleep 2
echo ""

echo "===================="
echo "✅ 测试完成！"
echo ""
echo "如果没有看到通知，请检查："
echo "1. 系统设置 > 通知 > 脚本编辑器/终端 - 确保允许通知"
echo "2. 右上角是否开启了勿扰模式"
echo "3. 通知中心是否有新通知"
echo ""
echo "常用的通知声音："
echo "  - Glass   (清脆)"
echo "  - Basso   (低音警告)"
echo "  - Funk    (响亮)"
echo "  - Hero    (英雄)"
echo "  - Submarine (潜水艇)"
echo "  - Ping    (乒)"
