# 智能跳过功能使用指南

## 概述

从 v4.1.1 开始，脚本会在选择角色前先检查当日进度。如果所有选定的副本都已完成，脚本会直接退出，避免不必要的设备连接和角色选择操作。

## 功能特点

### 1. 智能检测

脚本会在执行前检查：
- 今日已完成的副本数量
- 配置中选定的副本总数
- 如果 `已完成数量 >= 选定数量`，则跳过所有操作

### 2. 优化流程

**旧流程**：
1. 加载配置
2. 连接设备
3. 初始化 OCR
4. 选择角色
5. 检查进度
6. 发现已完成，退出

**新流程**：
1. 加载配置
2. **检查进度**
3. **如果已完成，直接退出**
4. 如果有剩余，才连接设备
5. 初始化 OCR
6. 选择角色
7. 执行副本遍历

### 3. 节省资源

- ✅ 避免不必要的设备连接
- ✅ 避免不必要的 OCR 初始化
- ✅ 避免不必要的角色选择操作
- ✅ 快速退出，节省时间

## 日志示例

### 示例 1：所有副本已完成

```
============================================================
🎮 副本自动遍历脚本
============================================================

✅ 配置加载成功: configs/warrior.json
📝 配置名称: warrior
⚔️ 角色职业: 战士
🌍 区域数量: 10
🎯 副本总数: 97
✅ 选定副本: 43

📊 今天已通关 43 个副本
  ✅ 风暴群岛 - 真理之地
  ✅ 风暴群岛 - 预言神殿
  ✅ 军团领域 - 大墓地密室
  ✅ 军团领域 - 军团要塞
  ✅ 军团领域 - 军团神殿
  ... 还有 38 个

📊 总计: 10 个区域, 97 个副本
📊 选定: 43 个副本
📊 已完成: 43 个副本

============================================================
🎉 今天所有选定的副本都已完成！
============================================================
💤 无需执行任何操作，脚本退出
```

### 示例 2：还有剩余副本

```
============================================================
🎮 副本自动遍历脚本
============================================================

✅ 配置加载成功: configs/warrior.json
📝 配置名称: warrior
⚔️ 角色职业: 战士
🌍 区域数量: 10
🎯 副本总数: 97
✅ 选定副本: 43

📊 今天已通关 20 个副本
  ✅ 风暴群岛 - 真理之地
  ✅ 风暴群岛 - 预言神殿
  ✅ 军团领域 - 大墓地密室
  ✅ 军团领域 - 军团要塞
  ✅ 军团领域 - 军团神殿

📊 总计: 10 个区域, 97 个副本
📊 选定: 43 个副本
📊 已完成: 20 个副本
📊 剩余: 23 个副本待通关

⚔️ 选择角色: 战士
🔍 查找文本: 设置
✅ 找到并点击: 设置
...
```

## 使用场景

### 场景 1：定时任务

如果你使用定时任务（如 cron）每小时运行一次脚本：

```bash
# 每小时运行一次
0 * * * * cd /path/to/helper && python auto_dungeon.py -c configs/warrior.json
```

脚本会自动检测：
- 第一次运行：执行副本遍历
- 完成后的运行：快速退出，不执行任何操作

### 场景 2：手动重复运行

如果你手动运行脚本多次：

```bash
# 第一次运行 - 执行副本遍历
python auto_dungeon.py -c configs/warrior.json

# 第二次运行 - 快速退出
python auto_dungeon.py -c configs/warrior.json
```

第二次运行会立即退出，不会重复执行。

### 场景 3：多角色配置

如果你有多个角色配置：

```bash
# 战士配置 - 43 个副本
python auto_dungeon.py -c configs/warrior.json

# 法师配置 - 30 个副本
python auto_dungeon.py -c configs/mage.json

# 猎人配置 - 50 个副本
python auto_dungeon.py -c configs/hunter.json
```

每个配置的进度独立记录，互不影响。

## 技术细节

### 检测逻辑

```python
# 计算选定的副本总数
total_selected_dungeons = sum(
    sum(1 for d in dungeons if d.get("selected", True))
    for dungeons in zone_dungeons.values()
)

# 获取已完成的副本数量
completed_count = db.get_today_completed_count()

# 检查是否所有选定的副本都已完成
if completed_count >= total_selected_dungeons:
    logger.info("🎉 今天所有选定的副本都已完成！")
    logger.info("💤 无需执行任何操作，脚本退出")
    return
```

### 执行流程

```python
def main():
    # 1. 加载配置
    config_loader = load_config(args.config)
    zone_dungeons = config_loader.get_zone_dungeons()
    
    # 2. 检查进度（不连接设备）
    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        completed_count = db.get_today_completed_count()
        total_selected = sum(...)
        
        # 3. 如果已完成，直接退出
        if completed_count >= total_selected:
            return
    
    # 4. 如果有剩余，才初始化设备
    connect_device("Android:///")
    ocr_helper = OCRHelper(output_dir="output")
    
    # 5. 选择角色
    if char_class:
        select_character(char_class)
    
    # 6. 执行副本遍历
    with DungeonProgressDB(...) as db:
        # 遍历副本...
```

## 配置示例

### 选定部分副本

```json
{
  "description": "战士配置 - 只打简单副本",
  "class": "战士",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": true },
      { "name": "预言神殿", "selected": false },
      { "name": "风暴神殿", "selected": true }
    ],
    "军团领域": [
      { "name": "大墓地密室", "selected": true },
      { "name": "军团要塞", "selected": false }
    ]
  }
}
```

在这个配置中：
- 总副本数：5 个
- 选定副本：3 个（真理之地、风暴神殿、大墓地密室）
- 当这 3 个副本都完成后，脚本会跳过

### 选定所有副本

```json
{
  "description": "默认配置 - 打所有副本",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": true },
      { "name": "预言神殿", "selected": true },
      { "name": "风暴神殿", "selected": true }
    ]
  }
}
```

在这个配置中：
- 总副本数：3 个
- 选定副本：3 个
- 当所有 3 个副本都完成后，脚本会跳过

## 常见问题

### Q1: 如何强制重新执行？

**A**: 有两种方法：

1. **清除今日进度**：
   ```bash
   python view_progress.py -c warrior --clear-today
   ```

2. **修改配置文件**：
   - 添加更多选定的副本
   - 或者使用不同的配置文件

### Q2: 如何查看今日进度？

**A**: 使用进度查看工具：
```bash
python view_progress.py -c warrior
```

### Q3: 为什么显示的选定数量和我配置的不一样？

**A**: 检查以下几点：
1. 确认配置文件中 `selected` 字段的值
2. 如果 `selected` 字段缺失，默认为 `true`
3. 使用 `view_progress.py` 查看详细信息

### Q4: 可以禁用这个功能吗？

**A**: 这个功能是自动的，无法禁用。但你可以：
1. 清除今日进度后重新运行
2. 使用不同的配置文件（不同的 `config_name`）

## 优势总结

1. **节省时间** - 快速检测，避免不必要的操作
2. **节省资源** - 不连接设备，不初始化 OCR
3. **安全可靠** - 避免重复执行，防止误操作
4. **日志清晰** - 明确显示完成状态
5. **适合自动化** - 完美配合定时任务

## 相关文档

- [CHANGELOG.md](../CHANGELOG.md) - 版本更新日志
- [README.md](../README.md) - 项目说明
- [CHARACTER_SELECTION_GUIDE.md](CHARACTER_SELECTION_GUIDE.md) - 角色选择指南
- [MULTI_CONFIG_GUIDE.md](MULTI_CONFIG_GUIDE.md) - 多配置使用指南

---

**版本**: 4.1.1  
**日期**: 2025-01-07  
**状态**: ✅ 已实现并测试

