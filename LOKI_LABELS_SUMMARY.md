# Loki 标签概念总结

## 你的问题的答案

### Q: 是只写入一行 message 然后 Grafana 会自动解析其中的某些字段，还是要自行指定标签？

### A: 两者都需要！

Loki 采用 **两层数据结构**：

```
第一层：标签（Labels）- 需要自行指定
  {app="miniwow", config="account1", host="docker-host"}
  ↓
第二层：日志内容（Content）- 自动提取和存储
  {"level":"INFO", "message":"应用启动", "module":"auto_dungeon", ...}
```

---

## 核心概念

### 1. 标签（Labels）

**定义**：用于索引和快速查询的键值对

**特点**：
- 数量有限（通常 5-10 个）
- 值离散且有限（< 1000 个不同值）
- 用于数据库索引
- 查询速度快（⚡⚡⚡ 毫秒级）

**示例**：
```python
labels = {
    "app": "miniwow",           # 应用名称
    "config": "account1",       # 配置文件
    "host": "docker-host",      # 主机名
    "env": "production"         # 环境
}
```

**在代码中指定**：
```python
from logger_config import setup_logger_from_config

logger = setup_logger_from_config(
    use_color=True,
    loki_labels={
        "config": "account1",
        "env": "production"
    }
)
```

### 2. 日志内容（Log Content）

**定义**：存储在标签对应的流中的详细日志信息

**特点**：
- 数量无限
- 可以包含任意详细信息
- 用于详细查询和分析
- 查询速度相对较慢（⚡⚡ 秒级）

**示例**：
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

**自动提取**：
```python
# 在 loki_logger.py 中自动提取
log_entry = {
    "level": record.levelname,      # 从 LogRecord 提取
    "logger": record.name,          # 从 LogRecord 提取
    "message": record.getMessage(), # 从 LogRecord 提取
    "module": record.module,        # 从 LogRecord 提取
    "function": record.funcName,    # 从 LogRecord 提取
    "line": record.lineno,          # 从 LogRecord 提取
}
```

---

## 数据流向

```
Python 代码
  ↓
logger.info("应用启动")
  ↓
logging.LogRecord
  ↓
LokiHandler.emit()
  ↓
提取日志信息 + 标签
  ↓
缓冲区
  ↓
后台线程（每 5 秒）
  ↓
构建 Loki 请求格式
  ↓
HTTP POST 到 Loki
  ↓
Loki 服务
  ↓
Loki 数据库
  ↓
Grafana 查询
```

---

## Loki 请求格式

```json
{
  "streams": [
    {
      "stream": {
        "app": "miniwow",
        "config": "account1",
        "host": "docker-host"
      },
      "values": [
        [
          "1730534445000000000",
          "{\"level\":\"INFO\",\"message\":\"应用启动\",\"module\":\"auto_dungeon\",\"function\":\"main\",\"line\":1725}"
        ]
      ]
    }
  ]
}
```

**说明**：
- `stream` 字段：标签（用于索引）
- `values` 字段：时间戳 + 日志内容（JSON）

---

## Stream 概念

**Stream = 标签组合 + 时间序列日志**

```
Stream 1: {app="miniwow", config="account1"}
  ├─ 时间戳1 → 日志内容1
  ├─ 时间戳2 → 日志内容2
  └─ 时间戳3 → 日志内容3

Stream 2: {app="miniwow", config="account2"}
  ├─ 时间戳1 → 日志内容1
  └─ 时间戳2 → 日志内容2
```

**关键点**：
- 相同标签的日志进入同一个 Stream
- 不同标签创建不同的 Stream
- 每个 Stream 是一个独立的时间序列

---

## Grafana 查询

### 查询方式 1：仅使用标签（⚡⚡⚡ 最快）

```
{config="account1"}
```

性能：毫秒级

### 查询方式 2：标签 + JSON 过滤（⚡⚡ 较快）

```
{config="account1"} | json | level="ERROR"
```

性能：秒级

### 查询方式 3：全文搜索（⚡ 较慢）

```
{app="miniwow"} | "副本"
```

性能：秒-分钟级

---

## 标签设计最佳实践

### ✅ 应该作为标签

- `app` - 应用名称
- `config` - 配置文件名
- `env` - 环境（dev, prod）
- `host` - 主机名
- `version` - 版本号
- `region` - 地区

### ❌ 不应该作为标签

- `level` - 放在日志内容中
- `message` - 放在日志内容中
- `user_id` - 高基数，放在日志内容中
- `timestamp` - Loki 已有
- 任意用户输入 - 可能导致标签爆炸

---

## 性能对比

| 查询方式 | 查询语句 | 性能 | 说明 |
|---------|---------|------|------|
| 标签查询 | `{config="account1"}` | ⚡⚡⚡ 毫秒级 | 使用索引，最快 |
| 标签+JSON | `{config="account1"} \| json \| level="ERROR"` | ⚡⚡ 秒级 | 先用索引，再过滤 |
| 全文搜索 | `{app="miniwow"} \| "副本"` | ⚡ 秒-分钟级 | 需要扫描所有内容 |

---

## 实际代码示例

### 初始化日志（带标签）

```python
from logger_config import setup_logger_from_config

# 在 auto_dungeon.py 中
logger = setup_logger_from_config(
    use_color=True,
    loki_labels={
        "config": "account1"  # 配置文件名称
    }
)

# 记录日志
logger.info("应用启动")
logger.error("连接失败")
```

### 在 Grafana 中查询

```
# 查询 account1 的所有日志
{config="account1"}

# 查询 account1 的 ERROR 日志
{config="account1"} | json | level="ERROR"

# 查询 account1 中 auto_dungeon.py 的日志
{config="account1"} | json | filename="auto_dungeon.py"

# 查询 account1 或 account2 的日志
{config=~"account1|account2"}
```

---

## 关键要点总结

1. **标签是索引** - 用于快速定位日志流
2. **日志内容是详情** - 存储在标签对应的流中
3. **标签应该有限** - 通常 5-10 个，值应该离散
4. **日志内容可以无限** - 可以包含任意详细信息
5. **查询优化** - 先用标签过滤，再用内容过滤
6. **相同标签进入同一 Stream** - 便于时间序列分析
7. **不同标签创建不同 Stream** - 便于隔离和查询

---

## 相关文档

- `LOKI_LABELS_DETAILED_GUIDE.md` - 详细的标签解析和 demo
- `LOKI_ARCHITECTURE_VISUAL.md` - 架构可视化指南
- `demo_loki_labels.py` - 可运行的 Python demo
- `LOKI_CONFIG_LABEL_GUIDE.md` - 配置文件名称标签使用指南

