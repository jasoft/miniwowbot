# 多角色配置指南

## 概述

从 v4.0.0 开始，脚本支持多角色配置功能。你可以为每个角色创建独立的配置文件，每个配置都有自己的副本选择和进度记录。

## 核心概念

### 配置文件
- 使用 JSON 格式存储副本配置
- 每个配置文件对应一个角色或一种打法
- 配置文件名（不含扩展名）作为配置名称

### 进度隔离
- 不同配置的进度完全独立
- 数据库使用 `config_name` 字段区分
- 可以同时管理多个角色的进度

## 快速开始

### 1. 选择预设配置

```bash
# 默认配置（所有副本）
python auto_dungeon_simple.py

# 主力角色配置
python auto_dungeon_simple.py -c configs/main_character.json

# 小号配置
python auto_dungeon_simple.py -c configs/alt_character.json
```

### 2. 创建自定义配置

```bash
# 复制默认配置
cp configs/default.json configs/warrior.json

# 编辑配置文件
# 修改 selected 字段选择要打的副本

# 使用自定义配置
python auto_dungeon_simple.py -c configs/warrior.json
```

### 3. 查看进度

```bash
# 查看默认配置进度
python view_progress.py

# 查看主力角色进度
python view_progress.py -c main_character

# 查看自定义配置进度
python view_progress.py -c warrior
```

## 配置文件详解

### 基本结构

```json
{
  "description": "配置描述",
  "ocr_correction_map": {
    "梦魔丛林": "梦魇丛林"
  },
  "zone_dungeons": {
    "风暴群岛": [
      {"name": "真理之地", "selected": true},
      {"name": "预言神殿", "selected": false}
    ]
  }
}
```

### 字段说明

#### description
- **类型**：字符串（可选）
- **说明**：配置文件的描述信息
- **示例**：`"主力角色配置 - 只打高价值副本"`

#### ocr_correction_map
- **类型**：对象
- **说明**：OCR 识别纠正映射表
- **格式**：`{"错误文本": "正确文本"}`
- **用途**：纠正 OCR 常见的识别错误

#### zone_dungeons
- **类型**：对象
- **说明**：副本配置字典
- **格式**：`{"区域名称": [副本列表]}`

#### 副本对象
- **name**：副本名称（必填）
- **selected**：是否选定（必填）
  - `true`：会打这个副本
  - `false`：跳过这个副本

## 使用场景

### 场景1：主力角色
只打高价值副本，节省时间

```json
{
  "description": "主力角色 - 高价值副本",
  "zone_dungeons": {
    "风暴群岛": [
      {"name": "真理之地", "selected": true},
      {"name": "预言神殿", "selected": true},
      {"name": "海底王宫", "selected": false}
    ]
  }
}
```

### 场景2：小号角色
只打简单副本，避免失败

```json
{
  "description": "小号 - 简单副本",
  "zone_dungeons": {
    "风暴群岛": [
      {"name": "真理之地", "selected": true},
      {"name": "预言神殿", "selected": false},
      {"name": "海底王宫", "selected": true}
    ]
  }
}
```

### 场景3：材料收集
只打产出特定材料的副本

```json
{
  "description": "材料收集 - 装备材料",
  "zone_dungeons": {
    "风暴群岛": [
      {"name": "真理之地", "selected": true},
      {"name": "预言神殿", "selected": false}
    ]
  }
}
```

## 进度管理

### 查看进度

```bash
# 查看今天的通关记录
python view_progress.py -c main_character --today

# 查看最近7天的统计
python view_progress.py -c main_character --recent 7

# 查看各区域统计
python view_progress.py -c main_character --zones
```

### 清理进度

```bash
# 清除今天的记录
python view_progress.py -c main_character --clear-today

# 清除所有记录
python view_progress.py -c main_character --clear-all
```

## 最佳实践

### 1. 命名规范
- 使用有意义的文件名：`warrior_main.json`、`mage_alt.json`
- 避免使用中文文件名
- 使用小写字母和下划线

### 2. 配置管理
- 为每个角色创建独立配置
- 在 `description` 字段中详细说明用途
- 定期备份配置文件

### 3. 版本控制
- 使用 Git 管理配置文件
- 提交前检查 JSON 格式
- 添加有意义的提交信息

### 4. 测试配置
- 创建新配置后先测试
- 检查副本名称是否正确
- 验证 selected 字段设置

## 常见问题

### Q: 如何切换角色？
A: 使用不同的配置文件运行脚本：
```bash
python auto_dungeon_simple.py -c configs/character1.json
python auto_dungeon_simple.py -c configs/character2.json
```

### Q: 配置文件修改后需要重启吗？
A: 是的，每次运行脚本时会重新加载配置文件。

### Q: 不同配置的进度会互相影响吗？
A: 不会，每个配置的进度完全独立。

### Q: 如何备份配置？
A: 直接复制 JSON 文件即可：
```bash
cp configs/main_character.json configs/main_character.backup.json
```

### Q: 配置文件格式错误怎么办？
A: 使用在线 JSON 验证工具检查格式，或查看错误提示信息。

### Q: 可以在运行时切换配置吗？
A: 不可以，需要停止当前运行，然后使用新配置重新启动。

## 高级技巧

### 1. 批量创建配置
使用脚本批量生成配置文件：
```bash
for char in warrior mage rogue; do
  cp configs/default.json configs/${char}.json
done
```

### 2. 配置模板
创建配置模板，方便快速创建新配置：
```bash
cp configs/default.json configs/template.json
```

### 3. 配置对比
使用 diff 工具对比不同配置：
```bash
diff configs/main_character.json configs/alt_character.json
```

### 4. 自动化运行
创建脚本自动运行多个配置：
```bash
#!/bin/bash
for config in configs/*.json; do
  echo "Running with $config"
  python auto_dungeon_simple.py -c $config
done
```

## 故障排除

### 配置文件加载失败
- 检查文件路径是否正确
- 验证 JSON 格式是否正确
- 确认文件编码为 UTF-8

### 副本名称不匹配
- 确保副本名称与游戏中完全一致
- 检查是否有多余的空格
- 使用 OCR 纠正映射处理识别错误

### 进度记录异常
- 检查配置名称是否正确
- 确认数据库文件未损坏
- 尝试清除今天的记录重新开始

## 更新日志

### v4.0.0
- 首次引入多角色配置功能
- 支持 JSON 配置文件
- 数据库添加配置名称字段
- 提供三个预设配置

## 相关文档

- [README.md](../README.md) - 项目总览
- [CHANGELOG.md](../CHANGELOG.md) - 更新日志
- [configs/README.md](../configs/README.md) - 配置文件说明

