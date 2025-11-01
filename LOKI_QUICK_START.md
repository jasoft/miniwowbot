# Loki 日志系统 - 快速开始指南

## 概述

这是一个简单的日志收集和查询系统，基于 Loki + Grafana，可以：
- 📱 通过手机 APP 查看日志
- 🌐 通过网络浏览器查看日志
- 🔍 快速搜索和过滤日志
- 📊 实时监控应用状态

## 快速开始（5 分钟）

### 第 1 步：启动 Loki 和 Grafana

```bash
# 进入项目目录
cd /Users/weiwang/Projects/miniwow

# 启动 Docker 容器
docker-compose -f docker-compose.loki.yml up -d
```

### 第 2 步：验证服务

```bash
# 检查容器是否运行
docker-compose -f docker-compose.loki.yml ps

# 应该看到两个容器：loki 和 grafana
```

### 第 3 步：访问 Grafana

1. 打开浏览器，访问 http://localhost:3000
2. 用户名：`admin`
3. 密码：`admin`
4. 首次登录会要求修改密码（可选）

### 第 4 步：在代码中使用

```python
from logstash_logger import create_loki_logger

# 创建日志记录器
logger = create_loki_logger(
    name="miniwow",
    level="INFO",
    loki_url="http://localhost:3100",
    enable_loki=True,
)

# 记录日志
logger.info("应用启动")
logger.warning("警告信息")
logger.error("错误信息")
```

### 第 5 步：在 Grafana 中查看日志

1. 点击左侧菜单的 "Explore"
2. 选择数据源 "Loki"
3. 在查询框中输入标签过滤：`{app="miniwow"}`
4. 点击 "Run query" 查看日志

## 日志查询语法

### 基本查询

```
# 查询所有 miniwow 应用的日志
{app="miniwow"}

# 查询特定主机的日志
{app="miniwow", host="my-host"}

# 查询包含特定文本的日志
{app="miniwow"} |= "error"

# 查询不包含特定文本的日志
{app="miniwow"} != "debug"
```

### 高级查询

```
# 查询 ERROR 级别的日志
{app="miniwow"} | json | level="ERROR"

# 查询特定模块的日志
{app="miniwow"} | json | module="emulator_manager"

# 统计日志数量
{app="miniwow"} | json | level="ERROR" | stats count()
```

## 环境变量配置

在 `.env` 文件中配置（可选）：

```env
# Loki 服务地址
LOKI_URL=http://localhost:3100

# 是否启用 Loki
LOKI_ENABLED=true
```

## 常见问题

### Q: 如何停止 Loki 和 Grafana？

```bash
docker-compose -f docker-compose.loki.yml down
```

### Q: 如何查看日志？

1. 在 Grafana 中点击 "Explore"
2. 选择 "Loki" 数据源
3. 输入查询条件，如 `{app="miniwow"}`

### Q: 如何删除旧日志？

Loki 默认保留所有日志。如果需要自动删除旧日志，修改 `loki-config.yml` 中的 `retention_period`。

### Q: 如何在手机上查看日志？

1. 确保手机和电脑在同一网络
2. 在手机浏览器中访问 `http://<你的电脑IP>:3000`
3. 登录 Grafana 并查看日志

### Q: 如何修改 Grafana 密码？

1. 登录 Grafana
2. 点击左下角的用户头像
3. 选择 "Change password"

## 集成到现有代码

### 方式 1：替换现有日志配置

```python
# 原来的代码
from logger_config import setup_logger
logger = setup_logger(name="auto_dungeon")

# 改为
from logstash_logger import create_loki_logger
logger = create_loki_logger(name="auto_dungeon")
```

### 方式 2：同时使用控制台和 Loki

```python
from logstash_logger import create_loki_logger

# 创建日志记录器，同时输出到控制台和 Loki
logger = create_loki_logger(
    name="auto_dungeon",
    level="INFO",
    loki_url="http://localhost:3100",
    enable_loki=True,
)
```

## 架构说明

```
┌─────────────────────────────────────────────────────────┐
│                   Python 应用                            │
│  (auto_dungeon.py, emulator_manager.py, 等)             │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ 日志记录
                     ▼
┌─────────────────────────────────────────────────────────┐
│              logstash_logger.py                          │
│  (LokiHandler - 缓冲和上传日志)                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTP POST
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Loki (3100)                            │
│  (日志存储和查询)                                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ 查询
                     ▼
┌─────────────────────────────────────────────────────────┐
│                Grafana (3000)                           │
│  (Web UI - 浏览器和手机 APP)                            │
└─────────────────────────────────────────────────────────┘
```

## 下一步

1. 启动 Loki 和 Grafana
2. 运行测试脚本：`python test_loki_logger.py`
3. 在 Grafana 中查看日志
4. 集成到你的应用代码中

## 支持

如有问题，请参考：
- [Loki 官方文档](https://grafana.com/docs/loki/latest/)
- [Grafana 官方文档](https://grafana.com/docs/grafana/latest/)

