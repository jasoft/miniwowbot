# Loki 配置文件名称标签使用指南

## 概述

在 Loki 中添加了配置文件名称作为标签，便于区分不同账号和职业的日志。

## 功能说明

### 标签结构

现在 Loki 中的日志包含以下标签：

| 标签 | 说明 | 示例 |
|------|------|------|
| `app` | 应用名称 | miniwow |
| `host` | 主机名 | docker-host |
| `config` | 配置文件名称 | account1, account2, warrior, mage |

### 工作原理

1. **初始化日志** - 程序启动时，先初始化基础日志
2. **加载配置** - `initialize_configs()` 函数加载配置文件
3. **获取配置名称** - 从配置文件名称提取标签值（如 `account1.json` → `account1`）
4. **重新初始化日志** - 使用配置名称作为 Loki 标签重新初始化日志
5. **后续日志** - 所有后续日志都会包含 `config` 标签

## 使用方式

### 配置文件命名

配置文件名称会直接作为 Loki 标签值，建议使用有意义的名称：

```
configs/
├── account1.json      # 账号1 配置
├── account2.json      # 账号2 配置
├── warrior.json       # 战士职业配置
├── mage.json          # 法师职业配置
└── default.json       # 默认配置
```

### 在 Grafana 中查询

#### 查询特定配置的日志

```
# 查询 account1 配置的所有日志
{config="account1"}

# 查询 account2 配置的所有日志
{config="account2"}

# 查询 warrior 配置的所有日志
{config="warrior"}
```

#### 组合查询

```
# 查询 account1 配置的 ERROR 级别日志
{config="account1"} | json | level="ERROR"

# 查询 account1 配置中 auto_dungeon.py 的日志
{config="account1"} | json | filename="auto_dungeon.py"

# 查询 account1 配置中特定函数的日志
{config="account1"} | json | function="run_dungeon_traversal"

# 查询 account1 配置中特定行号的日志
{config="account1"} | json | line="1725"

# 查询 account1 配置中包含特定关键词的日志
{config="account1"} | json | message=~"副本|完成"
```

#### 多配置查询

```
# 查询 account1 和 account2 的日志
{config=~"account1|account2"}

# 查询所有账号配置的日志（排除 default）
{config!="default"}

# 查询所有职业配置的日志
{config=~"warrior|mage|archer|priest"}
```

### 日志示例

**Loki 中的日志：**

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

**对应的 Loki 标签：**
```
app: miniwow
host: docker-host
config: account1
```

## 代码示例

### 在 auto_dungeon.py 中的使用

```python
# 初始化配置
initialize_configs(args.config, args.env_overrides)

# 此时日志已经重新初始化，包含 config 标签
logger.info("应用启动")  # 这条日志会包含 config 标签
```

### 自定义 Loki 标签

如果需要添加其他标签，可以在调用 `setup_logger_from_config()` 时传递：

```python
from logger_config import setup_logger_from_config

# 添加自定义标签
logger = setup_logger_from_config(
    use_color=True,
    loki_labels={
        "config": "account1",
        "env": "production",
        "version": "1.0.0"
    }
)
```

## 优势

✅ **账号隔离** - 不同账号的日志可以独立查询和分析
✅ **职业区分** - 不同职业配置的日志可以区分
✅ **灵活查询** - 在 Grafana 中可以按配置名称过滤日志
✅ **便于调试** - 快速定位特定账号/职业的问题
✅ **性能监控** - 可以对比不同配置的性能表现
✅ **问题追踪** - 快速定位特定配置出现的问题

## 常见场景

### 场景 1：调试特定账号的问题

```
# 查询 account1 的所有 ERROR 日志
{config="account1"} | json | level="ERROR"
```

### 场景 2：对比不同账号的性能

```
# 查询 account1 的副本完成日志
{config="account1"} | json | message=~"完成区域"

# 查询 account2 的副本完成日志
{config="account2"} | json | message=~"完成区域"
```

### 场景 3：监控所有账号的错误

```
# 查询所有账号的 ERROR 日志
{app="miniwow"} | json | level="ERROR"
```

### 场景 4：分析特定职业的行为

```
# 查询 warrior 职业的所有日志
{config="warrior"}

# 查询 warrior 职业的技能使用日志
{config="warrior"} | json | message=~"技能|释放"
```

## 相关文档

- `LOKI_INTEGRATION_COMPLETE.md` - Loki 集成完成总结
- `LOGGING_NAME_GUIDE.md` - Logger Name 参数说明
- `LOKI_SETUP.md` - Loki 快速开始指南

