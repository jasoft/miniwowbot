#!/bin/bash
# 多角色配置使用示例

echo "======================================"
echo "多角色配置使用示例"
echo "======================================"
echo ""

# 示例1：使用默认配置
echo "示例1：使用默认配置（所有副本）"
echo "命令: python auto_dungeon_simple.py"
echo ""

# 示例2：使用主力角色配置
echo "示例2：使用主力角色配置"
echo "命令: python auto_dungeon_simple.py -c configs/main_character.json"
echo ""

# 示例3：使用小号配置
echo "示例3：使用小号配置"
echo "命令: python auto_dungeon_simple.py -c configs/alt_character.json"
echo ""

# 示例4：查看不同配置的进度
echo "示例4：查看不同配置的进度"
echo "命令: python view_progress.py -c default"
echo "命令: python view_progress.py -c main_character"
echo "命令: python view_progress.py -c alt_character"
echo ""

# 示例5：创建自定义配置
echo "示例5：创建自定义配置"
echo "命令: cp configs/default.json configs/my_character.json"
echo "然后编辑 configs/my_character.json"
echo "运行: python auto_dungeon_simple.py -c configs/my_character.json"
echo ""

echo "======================================"
echo "更多信息请查看 README.md"
echo "======================================"

