# Loki 日志集成完成总结

## 概述

已成功在所有主要文件中添加 Loki 日志支持，确保 console 和 Loki 中的日志输出内容完全一致。

## 完成的工作

### 1. 文件更新

#### 主程序文件
- ✅ `auto_dungeon.py` - 主程序
- ✅ `emulator_manager.py` - 模拟器管理器
- ✅ `config_loader.py` - 配置加载器
- ✅ `ocr_helper.py` - OCR 助手
- ✅ `database/dungeon_db.py` - 数据库模块
- ✅ `system_config_loader.py` - 系统配置加载器

### 2. 配置更新

- ✅ `system_config.json` - 启用 Loki 和 Grafana
  - Loki 服务地址：`http://docker.home:3100`
  - Grafana 服务地址：`http://docker.home:3099`

### 3. 日志输出一致性

所有日志现在都支持 Loki，console 和 Loki 中的输出内容完全一致：

**Console 输出：**
```
14:30:45 INFO auto_dungeon.py:1725 应用启动
14:30:46 WARNING emulator_manager.py:156 模拟器连接超时
14:30:47 ERROR ocr_helper.py:892 OCR 识别失败
```

**Loki 中的日志（JSON 格式）：**
```json
{
  "level": "INFO",
  "logger": "miniwow",
  "message": "应用启动",
  "module": "auto_dungeon",
  "function": "main",
  "line": 1725,
  "filename": "auto_dungeon.py"
}
```

## 使用方式

### 1. 启用 Loki

编辑 `system_config.json`，设置 `loki.enabled` 为 `true`：

```json
{
  "loki": {
    "enabled": true,
    "server": "http://docker.home:3100",
    "app_name": "miniwow",
    "buffer_size": 50,
    "upload_interval": 5
  }
}
```

### 2. 在代码中使用

所有文件现在都自动从 `system_config.json` 加载 Loki 配置：

```python
from logger_config import setup_logger_from_config

# 自动从 system_config.json 加载配置
logger = setup_logger_from_config(use_color=True)

# 记录日志（同时输出到 console 和 Loki）
logger.info("应用启动")
logger.warning("警告信息")
logger.error("错误信息")
```

### 3. 在 Grafana 中查询日志

访问 `http://docker.home:3099`（或配置的 Grafana 地址）

**查询示例：**

```
# 查询所有日志
{app="miniwow"}

# 查询特定模块的日志
{app="miniwow"} | json | module="auto_dungeon"

# 查询 ERROR 级别的日志
{app="miniwow"} | json | level="ERROR"

# 查询特定文件的日志
{app="miniwow"} | json | filename="auto_dungeon.py"

# 查询特定函数的日志
{app="miniwow"} | json | function="main"

# 查询特定行号的日志
{app="miniwow"} | json | line="1725"
```

## 日志字段说明

Loki 中的每条日志都包含以下字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| `level` | 日志级别 | INFO, WARNING, ERROR, DEBUG |
| `logger` | 日志记录器名称 | miniwow |
| `message` | 日志消息 | 应用启动 |
| `module` | 模块名称 | auto_dungeon |
| `function` | 函数名称 | main |
| `line` | 行号 | 1725 |
| `filename` | 文件名 | auto_dungeon.py |
| `app` | 应用名称（标签） | miniwow |
| `host` | 主机名（标签） | docker-host |

## 配置说明

### system_config.json 中的 logging 配置

```json
{
  "logging": {
    "logger_name": "miniwow",
    "level": "INFO"
  }
}
```

- `logger_name`: 日志记录器名称（仅在 Loki 中有意义）
- `level`: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）

### system_config.json 中的 loki 配置

```json
{
  "loki": {
    "enabled": true,
    "server": "http://docker.home:3100",
    "app_name": "miniwow",
    "buffer_size": 50,
    "upload_interval": 5
  }
}
```

- `enabled`: 是否启用 Loki
- `server`: Loki 服务地址
- `app_name`: 应用名称（用于 Loki 标签）
- `buffer_size`: 日志缓冲区大小
- `upload_interval`: 上传间隔（秒）

### system_config.json 中的 grafana 配置

```json
{
  "grafana": {
    "enabled": true,
    "server": "http://docker.home:3099",
    "username": "admin",
    "password": "admin"
  }
}
```

- `enabled`: 是否启用 Grafana
- `server`: Grafana 服务地址
- `username`: 用户名
- `password`: 密码

## 关键特性

✅ **自动配置加载** - 从 system_config.json 自动加载 Loki 配置
✅ **日志一致性** - console 和 Loki 中的输出内容完全一致
✅ **文件名和行号** - 所有日志都包含文件名和行号信息
✅ **后台上传** - 日志异步上传到 Loki，不阻塞主程序
✅ **缓冲机制** - 支持日志缓冲，提高性能
✅ **灵活配置** - 支持启用/禁用 Loki，无需修改代码

## 故障排除

### 日志没有出现在 Loki 中

1. 检查 `system_config.json` 中 `loki.enabled` 是否为 `true`
2. 检查 Loki 服务是否正常运行
3. 检查 Loki 服务地址是否正确
4. 查看 console 输出中是否有错误信息

### 日志输出不完整

1. 检查日志级别设置是否正确
2. 确保 `system_config.json` 中的 `logging.level` 设置正确
3. 检查是否有日志过滤规则

## 相关文档

- `LOGGING_NAME_GUIDE.md` - Logger Name 参数说明
- `LOKI_SETUP.md` - Loki 快速开始指南
- `LOKI_QUICK_START.md` - Loki 详细使用指南
- `LOKI_QUICK_REFERENCE.md` - Loki 快速参考

