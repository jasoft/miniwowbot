# Loki 日志系统设置指南

## 一句话总结

用 Loki + Grafana 替代腾讯云 CLS，实现简单的日志收集和查询系统。

## 快速开始（3 步）

### 1️⃣ 启动服务

```bash
cd /Users/weiwang/Projects/miniwow
docker-compose -f docker-compose.loki.yml up -d
```

### 2️⃣ 访问 Grafana

打开浏览器访问：http://localhost:3000

- 用户名：`admin`
- 密码：`admin`

### 3️⃣ 在代码中使用

```python
from loki_logger import create_loki_logger

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

## 查看日志

### 在 Grafana 中查看

1. 点击左侧菜单的 **Explore**
2. 选择数据源 **Loki**
3. 在查询框中输入：`{app="miniwow"}`
4. 点击 **Run query** 查看日志

### 在手机上查看

1. 确保手机和电脑在同一网络
2. 在手机浏览器中访问：`http://<你的电脑IP>:3000`
3. 登录 Grafana 并查看日志

## 常用查询

```
# 查询所有日志
{app="miniwow"}

# 查询 ERROR 级别的日志
{app="miniwow"} | json | level="ERROR"

# 查询包含特定文本的日志
{app="miniwow"} |= "error"

# 查询特定模块的日志
{app="miniwow"} | json | module="emulator_manager"
```

## 停止服务

```bash
docker-compose -f docker-compose.loki.yml down
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `loki_logger.py` | Loki 日志处理器 |
| `docker-compose.loki.yml` | Docker Compose 配置 |
| `loki-config.yml` | Loki 配置文件 |
| `test_loki_logger.py` | 测试脚本 |
| `LOKI_QUICK_START.md` | 详细指南 |

## 集成到现有代码

### auto_dungeon.py

```python
# 原来的代码
from logger_config import setup_logger
logger = setup_logger(name="auto_dungeon")

# 改为
from loki_logger import create_loki_logger
logger = create_loki_logger(name="auto_dungeon")
```

### emulator_manager.py

```python
# 原来的代码
from logger_config import setup_logger
logger = setup_logger(name="emulator_manager")

# 改为
from loki_logger import create_loki_logger
logger = create_loki_logger(name="emulator_manager")
```

## 环境变量配置（可选）

在 `.env` 文件中配置：

```env
# Loki 服务地址
LOKI_URL=http://localhost:3100

# 是否启用 Loki
LOKI_ENABLED=true
```

## 常见问题

### Q: 如何修改 Grafana 密码？

1. 登录 Grafana
2. 点击左下角的用户头像
3. 选择 "Change password"

### Q: 如何删除旧日志？

Loki 默认保留所有日志。如果需要自动删除旧日志，修改 `loki-config.yml` 中的 `retention_period`。

### Q: 如何在远程服务器上部署？

1. 将 `docker-compose.loki.yml` 和 `loki-config.yml` 复制到服务器
2. 修改 `docker-compose.loki.yml` 中的端口（如果需要）
3. 运行 `docker-compose -f docker-compose.loki.yml up -d`
4. 在代码中修改 `loki_url` 为服务器地址

### Q: 如何查看 Loki 日志？

```bash
docker-compose -f docker-compose.loki.yml logs loki
```

### Q: 如何查看 Grafana 日志？

```bash
docker-compose -f docker-compose.loki.yml logs grafana
```

## 下一步

1. ✅ 启动 Loki 和 Grafana
2. ✅ 在代码中集成 Loki 日志
3. ✅ 在 Grafana 中查看日志
4. ✅ 在手机上查看日志

## 支持

- [Loki 官方文档](https://grafana.com/docs/loki/latest/)
- [Grafana 官方文档](https://grafana.com/docs/grafana/latest/)

