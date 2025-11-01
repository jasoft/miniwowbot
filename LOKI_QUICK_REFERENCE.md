# Loki 快速参考卡片

## 🚀 快速开始（3 步）

### 1️⃣ 启动服务
```bash
docker-compose -f docker-compose.loki.yml up -d
```

### 2️⃣ 访问 Grafana
```
http://localhost:3000
用户名: admin
密码: admin
```

### 3️⃣ 在代码中使用
```python
from logstash_logger import create_loki_logger

logger = create_loki_logger(name="miniwow")
logger.info("应用启动")
```

---

## 📊 常用命令

### Docker 操作

```bash
# 启动服务
docker-compose -f docker-compose.loki.yml up -d

# 停止服务
docker-compose -f docker-compose.loki.yml stop

# 删除服务
docker-compose -f docker-compose.loki.yml down

# 查看日志
docker-compose -f docker-compose.loki.yml logs -f loki
docker-compose -f docker-compose.loki.yml logs -f grafana

# 查看状态
docker-compose -f docker-compose.loki.yml ps
```

### Python 代码

```python
# 创建日志记录器
from logstash_logger import create_loki_logger

logger = create_loki_logger(
    name="miniwow",
    level="INFO",
    loki_url="http://localhost:3100",
    enable_loki=True,
)

# 记录日志
logger.info("信息")
logger.warning("警告")
logger.error("错误")
logger.debug("调试")
```

---

## 🔍 日志查询

### 在 Grafana 中查询

1. 点击 **Explore**
2. 选择 **Loki** 数据源
3. 输入查询条件
4. 点击 **Run query**

### 常用查询

```
# 查询所有日志
{app="miniwow"}

# 查询 ERROR 级别
{app="miniwow"} | json | level="ERROR"

# 查询包含特定文本
{app="miniwow"} |= "error"

# 查询特定模块
{app="miniwow"} | json | module="emulator_manager"

# 统计日志数量
{app="miniwow"} | json | level="ERROR" | stats count()
```

---

## 🔧 配置文件

### logstash_logger.py

```python
# 创建日志记录器的参数
create_loki_logger(
    name="app_name",           # 应用名称
    level="INFO",              # 日志级别
    log_format=None,           # 日志格式
    loki_url="http://localhost:3100",  # Loki 地址
    enable_loki=True,          # 是否启用 Loki
)
```

### docker-compose.loki.yml

```yaml
# 修改端口
services:
  loki:
    ports:
      - "3100:3100"  # 改为 "3101:3100"
  
  grafana:
    ports:
      - "3000:3000"  # 改为 "3001:3000"
```

### loki-config.yml

```yaml
# 修改日志保留时间
table_manager:
  retention_period: 720h  # 30 天

# 修改日志级别
server:
  log_level: debug  # info, debug, warn, error
```

---

## 🐛 常见问题

### Docker daemon 未运行

```bash
# macOS - 启动 OrbStack
open /Applications/OrbStack.app

# macOS - 启动 Docker Desktop
open /Applications/Docker.app

# Linux
sudo systemctl start docker
```

### 端口已被占用

```bash
# 查看占用端口的进程
lsof -i :3000
lsof -i :3100

# 杀死进程
kill -9 <PID>
```

### 容器启动失败

```bash
# 查看错误日志
docker-compose -f docker-compose.loki.yml logs loki

# 重新启动
docker-compose -f docker-compose.loki.yml restart
```

### 无法连接到 Loki

```bash
# 检查 Loki 是否运行
docker-compose -f docker-compose.loki.yml ps

# 检查网络连接
curl http://localhost:3100/ready

# 检查日志
docker-compose -f docker-compose.loki.yml logs loki
```

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `logstash_logger.py` | Loki 日志处理器 |
| `docker-compose.loki.yml` | Docker Compose 配置 |
| `loki-config.yml` | Loki 配置文件 |
| `test_loki_logger.py` | 完整测试脚本 |
| `test_loki_basic.py` | 基本功能测试 |
| `LOKI_SETUP.md` | 简单设置指南 |
| `LOKI_QUICK_START.md` | 详细快速开始 |
| `DOCKER_SETUP.md` | Docker 环境设置 |

---

## 📞 获取帮助

- 查看 `LOKI_SETUP.md` - 简单设置指南
- 查看 `LOKI_QUICK_START.md` - 详细快速开始
- 查看 `DOCKER_SETUP.md` - Docker 环境设置
- 查看 `LOKI_IMPLEMENTATION_SUMMARY.md` - 实现总结

---

## ✅ 检查清单

- [ ] 已安装 Docker
- [ ] 已启动 Loki 和 Grafana
- [ ] 已访问 Grafana Web UI
- [ ] 已在代码中集成 Loki 日志
- [ ] 已在 Grafana 中查看日志
- [ ] 已在手机上查看日志

---

## 🎯 下一步

1. 启动 Loki 和 Grafana
2. 在代码中集成 Loki 日志
3. 在 Grafana 中查看日志
4. 在手机上查看日志
5. 根据需要调整配置

---

**最后更新：2025-11-01**

