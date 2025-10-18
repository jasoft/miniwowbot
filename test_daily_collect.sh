#!/bin/bash
# 测试 daily_collect 功能的便捷脚本

echo "========================================"
echo "测试 daily_collect 功能 - 真机测试"
echo "========================================"
echo ""
echo "⚠️  注意事项："
echo "  1. 确保安卓设备/模拟器已连接"
echo "  2. 游戏应该已经打开"
echo "  3. 建议在主界面运行测试"
echo ""
echo "检查设备连接..."
adb devices
echo ""

# 询问是否继续
read -p "是否继续运行测试? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "已取消测试"
    exit 1
fi

echo ""
echo "运行 daily_collect 测试..."
echo ""

# 运行测试
pytest tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration -v -s --tb=short

echo ""
echo "========================================"
echo "测试完成"
echo "========================================"
