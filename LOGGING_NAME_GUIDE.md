# 日志记录器名称（Logger Name）指南

## 概述

在 Python logging 系统中，`name` 参数是日志记录器的唯一标识符。它用于：
1. 区分不同模块或组件的日志
2. 在 Loki 中作为 `logger` 标签，用于日志查询和过滤
3. 支持日志记录器的层级结构

## 什么是 Logger Name？

### 定义

Logger Name 是通过 `logging.getLogger(name)` 创建或获取日志记录器时指定的字符串标识符。

### 示例

```python
import logging

# 创建名为 "miniwow" 的日志记录器
logger = logging.getLogger("miniwow")

# 创建名为 "miniwow.auto_dungeon" 的日志记录器
logger = logging.getLogger("miniwow.auto_dungeon")

# 创建名为 "miniwow.emulator_manager" 的日志记录器
logger = logging.getLogger("miniwow.emulator_manager")
```

## Logger Name 的作用

### 1. 日志来源识别

在 Loki 中，每条日志都会包含 `logger` 字段，用于标识日志的来源：

```json
{
  "level": "INFO",
  "logger": "miniwow.auto_dungeon",
  "message": "应用启动",
  "module": "auto_dungeon",
  "function": "main",
  "line": 1725
}
```

### 2. 日志查询过滤

在 Grafana 中，可以使用 logger 字段进行查询和过滤：

```
# 查询所有 miniwow 应用的日志
{app="miniwow"}

# 查询特定模块的日志
{app="miniwow"} | json | logger="miniwow.auto_dungeon"

# 查询包含特定文本的日志
{app="miniwow"} | json | logger=~"miniwow\\..*"
```

### 3. 日志记录器层级

Python logging 支持日志记录器的层级结构，使用点号（`.`）分隔：

```
root
├── miniwow
│   ├── auto_dungeon
│   ├── emulator_manager
│   └── ocr_helper
└── other_app
```

## 配置 Logger Name

### 方式 1：在代码中指定

```python
from logger_config import setup_logger

# 为特定模块创建日志记录器
logger = setup_logger(name="miniwow.auto_dungeon")
```

### 方式 2：从系统配置文件加载

在 `system_config.json` 中配置：

```json
{
  "logging": {
    "description": "日志配置 - 用于 logger_config.py 中的 setup_logger() 函数",
    "logger_name": "miniwow",
    "level": "INFO"
  }
}
```

然后在代码中使用：

```python
from logger_config import setup_logger_from_config

# 从配置文件加载日志配置
logger = setup_logger_from_config()
```

### 方式 3：使用 Loki 日志记录器

```python
from loki_logger import create_loki_logger

# 创建带 Loki 支持的日志记录器
logger = create_loki_logger(
    name="miniwow.auto_dungeon",
    level="INFO",
    loki_url="http://localhost:3100",
    enable_loki=True,
)
```

## 最佳实践

### 1. 使用模块名作为 Logger Name

```python
# 在 auto_dungeon.py 中
logger = setup_logger(name="miniwow.auto_dungeon")

# 在 emulator_manager.py 中
logger = setup_logger(name="miniwow.emulator_manager")

# 在 ocr_helper.py 中
logger = setup_logger(name="miniwow.ocr_helper")
```

### 2. 使用统一的前缀

所有应用的日志记录器都应该使用统一的前缀（如 `miniwow`），便于在 Loki 中查询：

```python
# ✅ 推荐
logger = setup_logger(name="miniwow.module_name")

# ❌ 不推荐
logger = setup_logger(name="my_logger")
```

### 3. 避免过长的名称

Logger Name 应该简洁明了，避免过长：

```python
# ✅ 推荐
logger = setup_logger(name="miniwow.auto_dungeon")

# ❌ 不推荐
logger = setup_logger(name="miniwow.auto_dungeon.main.run_dungeon_traversal")
```

## 在 Loki 中查询

### 查询特定模块的日志

```
{app="miniwow"} | json | logger="miniwow.auto_dungeon"
```

### 查询多个模块的日志

```
{app="miniwow"} | json | logger=~"miniwow\\.(auto_dungeon|emulator_manager)"
```

### 查询特定级别的日志

```
{app="miniwow"} | json | logger="miniwow.auto_dungeon" | level="ERROR"
```

## 总结

- **Logger Name** 是日志记录器的唯一标识符
- 用于区分不同模块的日志来源
- 在 Loki 中作为 `logger` 标签，用于日志查询和过滤
- 应该使用统一的前缀和模块名称
- 可以在代码中指定，也可以从配置文件加载

