# 数据库迁移指南

## 概述

从 v4.0.0 开始，数据库添加了 `config_name` 字段以支持多角色配置。如果你有旧的数据库文件，需要进行迁移。

## 自动迁移

数据库会在首次使用新版本时自动创建 `config_name` 字段。但是，为了确保数据完整性，建议手动运行迁移脚本。

## 迁移步骤

### 1. 备份数据库

在迁移之前，请先备份你的数据库文件：

```bash
cp database/dungeon_progress.db database/dungeon_progress.db.backup
```

### 2. 检查数据库状态

数据库已经自动迁移完成。你可以验证迁移结果：

```python
import sqlite3

conn = sqlite3.connect("database/dungeon_progress.db")
cursor = conn.cursor()

# 检查字段
cursor.execute("PRAGMA table_info(dungeon_progress)")
columns = cursor.fetchall()
print("表结构:")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

# 检查数据
cursor.execute("SELECT config_name, COUNT(*) FROM dungeon_progress GROUP BY config_name")
stats = cursor.fetchall()
print("\n按配置统计:")
for config, count in stats:
    print(f"  {config}: {count} 条记录")

conn.close()
```

### 3. 验证迁移

运行测试以验证迁移是否成功：

```bash
pytest tests/test_database.py -v
```

## 迁移后的数据结构

### 旧结构

```sql
CREATE TABLE dungeon_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    zone_name TEXT NOT NULL,
    dungeon_name TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    completed_at TEXT,
    UNIQUE(date, zone_name, dungeon_name)
);
```

### 新结构

```sql
CREATE TABLE dungeon_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT NOT NULL DEFAULT 'default',
    date TEXT NOT NULL,
    zone_name TEXT NOT NULL,
    dungeon_name TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    completed_at TEXT,
    UNIQUE(config_name, date, zone_name, dungeon_name)
);
```

## 数据迁移说明

- 所有旧数据的 `config_name` 都被设置为 `'default'`
- 唯一索引已更新为包含 `config_name`
- 旧的索引已被删除

## 常见问题

### Q: 迁移会丢失数据吗？

A: 不会。迁移过程会保留所有数据，只是添加了 `config_name` 字段。

### Q: 如果迁移失败怎么办？

A: 迁移脚本会自动创建备份文件（格式：`dungeon_progress.db.backup_YYYYMMDD_HHMMSS`）。如果迁移失败，可以使用备份文件恢复：

```bash
cp database/dungeon_progress.db.backup_YYYYMMDD_HHMMSS database/dungeon_progress.db
```

### Q: 可以回滚到旧版本吗？

A: 可以，但需要先恢复备份文件。新版本的数据库结构与旧版本不兼容。

### Q: 迁移后如何使用？

A: 迁移后，你可以继续使用默认配置（所有旧数据都在 `default` 配置下），或者创建新的配置文件：

```bash
# 使用默认配置（包含所有旧数据）
python auto_dungeon_simple.py

# 使用新配置
python auto_dungeon_simple.py -c configs/main_character.json
```

### Q: 如何查看不同配置的进度？

A: 使用 `view_progress.py` 并指定配置名称：

```bash
# 查看默认配置（旧数据）
python view_progress.py -c default

# 查看其他配置
python view_progress.py -c main_character
```

## 备份文件管理

迁移过程会创建备份文件。建议：

1. 保留最近的 2-3 个备份文件
2. 定期清理旧的备份文件
3. 在重要操作前手动创建备份

```bash
# 查看所有备份文件
ls -lh database/*.backup*

# 删除旧备份（保留最新的）
# 请谨慎操作！
```

## 技术细节

### 迁移过程

1. 创建新表 `dungeon_progress_new`
2. 复制所有数据，设置 `config_name = 'default'`
3. 删除旧表
4. 重命名新表为 `dungeon_progress`
5. 创建新索引

### 索引变化

**旧索引：**
- `idx_date_zone_dungeon` (date, zone_name, dungeon_name) UNIQUE
- `dungeonprogress_date` (date)
- `dungeonprogress_zone_name` (zone_name)

**新索引：**
- `dungeonprogress_config_name_date_zone_name_dungeon_name` (config_name, date, zone_name, dungeon_name) UNIQUE
- `dungeonprogress_config_name` (config_name)
- `dungeonprogress_date` (date)
- `dungeonprogress_zone_name` (zone_name)

## 相关文档

- [CHANGELOG.md](CHANGELOG.md) - 版本更新日志
- [README.md](README.md) - 项目说明
- [docs/MULTI_CONFIG_GUIDE.md](docs/MULTI_CONFIG_GUIDE.md) - 多配置使用指南

