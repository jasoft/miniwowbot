# Loki 标签详细解析 - 完整 Demo

## 核心概念

### 1. Loki 的两层数据结构

Loki 采用 **两层数据结构**：

```
┌─────────────────────────────────────────────────────────┐
│ 第一层：标签（Labels）- 用于索引和查询                    │
│ 例如：{app="miniwow", config="account1", host="docker"}  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 第二层：日志内容（Log Content）- JSON 格式的详细信息      │
│ {                                                        │
│   "level": "INFO",                                       │
│   "logger": "miniwow",                                   │
│   "message": "应用启动",                                 │
│   "module": "auto_dungeon",                              │
│   "function": "main",                                    │
│   "line": 1725                                           │
│ }                                                        │
└─────────────────────────────────────────────────────────┘
```

### 2. 标签 vs 日志内容的区别

| 特性 | 标签（Labels） | 日志内容（Content） |
|------|----------------|-------------------|
| **作用** | 用于索引和快速查询 | 存储详细的日志信息 |
| **查询性能** | ⚡ 快速（数据库索引） | 🐢 较慢（需要扫描内容） |
| **数据量** | 💾 少（通常 5-10 个） | 📊 多（可以很大） |
| **示例** | `app`, `config`, `host` | `level`, `message`, `module` |
| **Grafana 查询** | `{app="miniwow"}` | `\| json \| level="ERROR"` |

---

## 详细 Demo：从代码到 Loki

### 第一步：初始化 Loki Handler

```python
from loki_logger import LokiHandler

# 创建 Loki 处理器，指定标签
loki_handler = LokiHandler(
    loki_url="http://docker.home:3100",
    app_name="miniwow",
    labels={
        "config": "account1",      # 自定义标签
        "env": "production"        # 自定义标签
    }
)
```

**此时 Loki Handler 内部的标签为：**
```python
self.labels = {
    "app": "miniwow",              # 自动添加
    "host": "docker-host",         # 自动添加
    "config": "account1",          # 自定义添加
    "env": "production"            # 自定义添加
}
```

### 第二步：记录日志

```python
logger.info("应用启动")
```

**Python logging 模块创建 LogRecord：**
```python
LogRecord(
    name="miniwow",
    level=20,  # INFO
    pathname="/Users/weiwang/Projects/miniwow/auto_dungeon.py",
    lineno=1725,
    msg="应用启动",
    args=(),
    exc_info=None,
    func="main",
    ...
)
```

### 第三步：LokiHandler.emit() 处理日志

```python
def emit(self, record: logging.LogRecord):
    # 提取日志信息
    log_entry = {
        "timestamp": int(record.created * 1e9),  # 纳秒时间戳
        "level": record.levelname,               # "INFO"
        "logger": record.name,                   # "miniwow"
        "message": record.getMessage(),          # "应用启动"
        "module": record.module,                 # "auto_dungeon"
        "function": record.funcName,             # "main"
        "line": record.lineno,                   # 1725
    }
    # 添加到缓冲区
    self.buffer.append(log_entry)
```

### 第四步：构建 Loki 请求格式

```python
def _do_upload(self, logs):
    streams = []
    for log_entry in logs:
        stream = {
            "stream": self.labels,  # ← 标签（第一层）
            "values": [
                [
                    str(log_entry["timestamp"]),
                    json.dumps({                # ← 日志内容（第二层）
                        "level": log_entry["level"],
                        "logger": log_entry["logger"],
                        "message": log_entry["message"],
                        "module": log_entry["module"],
                        "function": log_entry["function"],
                        "line": log_entry["line"],
                    }, ensure_ascii=False)
                ]
            ],
        }
        streams.append(stream)
    
    payload = {"streams": streams}
    requests.post(f"{self.loki_url}/loki/api/v1/push", json=payload)
```

**发送到 Loki 的 JSON 格式：**
```json
{
  "streams": [
    {
      "stream": {
        "app": "miniwow",
        "host": "docker-host",
        "config": "account1",
        "env": "production"
      },
      "values": [
        [
          "1730534445000000000",
          "{\"level\":\"INFO\",\"logger\":\"miniwow\",\"message\":\"应用启动\",\"module\":\"auto_dungeon\",\"function\":\"main\",\"line\":1725}"
        ]
      ]
    }
  ]
}
```

### 第五步：Loki 存储和索引

```
Loki 数据库中的存储结构：

标签组合（唯一的 stream）：
{app="miniwow", host="docker-host", config="account1", env="production"}
    ↓
时间序列数据：
    时间戳1 → 日志内容1（JSON）
    时间戳2 → 日志内容2（JSON）
    时间戳3 → 日志内容3（JSON）
    ...
```

---

## 在 Grafana 中查询

### 查询方式 1：使用标签快速查询（⚡ 快速）

```
# 查询 account1 的所有日志
{config="account1"}

# 查询 account1 且 production 环境的日志
{config="account1", env="production"}

# 查询所有应用的日志
{app="miniwow"}
```

**查询流程：**
1. Loki 使用标签索引快速定位数据
2. 返回所有匹配标签的日志流
3. ⚡ 非常快速

### 查询方式 2：使用日志内容过滤（🐢 较慢）

```
# 查询 account1 中 level 为 ERROR 的日志
{config="account1"} | json | level="ERROR"

# 查询 account1 中包含 "副本" 的日志
{config="account1"} | json | message=~"副本"

# 查询 account1 中 auto_dungeon.py 的日志
{config="account1"} | json | filename="auto_dungeon.py"
```

**查询流程：**
1. Loki 使用标签索引快速定位数据
2. 对每条日志的内容进行 JSON 解析
3. 按条件过滤
4. 🐢 相对较慢（但仍然很快）

### 查询方式 3：组合查询（最灵活）

```
# 查询 account1 中 ERROR 级别且来自 auto_dungeon.py 的日志
{config="account1"} | json | level="ERROR" | filename="auto_dungeon.py"

# 查询 account1 或 account2 中的 ERROR 日志
{config=~"account1|account2"} | json | level="ERROR"

# 查询所有配置中的 ERROR 日志
{app="miniwow"} | json | level="ERROR"
```

---

## 标签设计最佳实践

### ✅ 好的标签设计

```python
# 标签数量适中（5-10 个）
labels = {
    "app": "miniwow",           # 应用名称
    "config": "account1",       # 配置文件
    "env": "production",        # 环境
    "version": "1.0.0",         # 版本
    "region": "asia"            # 地区
}

# 标签值有限且离散
# ✅ 好：config="account1", config="account2"
# ❌ 差：config="用户输入的任意字符串"
```

### ❌ 不好的标签设计

```python
# ❌ 标签太多
labels = {
    "app": "miniwow",
    "config": "account1",
    "message": "应用启动",      # ❌ 不应该作为标签
    "timestamp": "2025-11-02",  # ❌ 不应该作为标签
    "user_id": "12345",         # ❌ 高基数，不适合作为标签
}

# ❌ 标签值无限制
labels = {
    "user_message": user_input  # ❌ 用户输入可能导致标签爆炸
}
```

---

## 性能对比

### 场景：查询 100 万条日志

| 查询方式 | 查询语句 | 性能 | 说明 |
|---------|---------|------|------|
| 标签查询 | `{config="account1"}` | ⚡⚡⚡ 毫秒级 | 使用索引，最快 |
| 标签+JSON | `{config="account1"} \| json \| level="ERROR"` | ⚡⚡ 秒级 | 先用索引，再过滤 |
| 全文搜索 | `{app="miniwow"} \| "副本"` | ⚡ 秒-分钟级 | 需要扫描所有内容 |

---

## 完整代码示例

```python
from logger_config import setup_logger_from_config

# 方式 1：使用默认标签
logger = setup_logger_from_config(use_color=True)

# 方式 2：添加自定义标签
logger = setup_logger_from_config(
    use_color=True,
    loki_labels={
        "config": "account1",
        "env": "production"
    }
)

# 记录日志
logger.info("应用启动")           # 包含所有标签
logger.warning("警告信息")        # 包含所有标签
logger.error("错误信息")          # 包含所有标签

# 在 Grafana 中查询
# {config="account1"} | json | level="ERROR"
```

---

## 总结

### 关键点

1. **标签是索引** - 用于快速定位日志流
2. **日志内容是详情** - 存储在标签对应的流中
3. **标签应该有限** - 通常 5-10 个，值应该离散
4. **日志内容可以无限** - 可以包含任意详细信息
5. **查询优化** - 先用标签过滤，再用内容过滤

### 何时使用标签

✅ **应该作为标签：**
- 应用名称（app）
- 环境（env）
- 配置文件（config）
- 主机名（host）
- 版本号（version）

❌ **不应该作为标签：**
- 日志消息
- 用户 ID（高基数）
- 时间戳
- 任意用户输入

