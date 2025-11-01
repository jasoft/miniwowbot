# Docker 环境设置指南

## 前置要求

### 1. 安装 Docker

#### macOS

**方式 1：使用 Homebrew（推荐）**
```bash
brew install docker
```

**方式 2：使用 OrbStack（推荐，更轻量）**
```bash
brew install orbstack
```

**方式 3：使用 Docker Desktop**
- 访问 https://www.docker.com/products/docker-desktop
- 下载并安装 Docker Desktop for Mac

#### Linux

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 添加当前用户到 docker 组（避免使用 sudo）
sudo usermod -aG docker $USER
```

#### Windows

- 访问 https://www.docker.com/products/docker-desktop
- 下载并安装 Docker Desktop for Windows

### 2. 验证 Docker 安装

```bash
docker --version
docker-compose --version
```

应该看到类似的输出：
```
Docker version 24.0.0, build abcdef
Docker Compose version v2.20.0
```

## 启动 Loki 和 Grafana

### 方式 1：使用 Docker Compose（推荐）

```bash
# 进入项目目录
cd /Users/weiwang/Projects/miniwow

# 启动服务
docker-compose -f docker-compose.loki.yml up -d

# 查看服务状态
docker-compose -f docker-compose.loki.yml ps
```

### 方式 2：手动启动容器

```bash
# 启动 Loki
docker run -d \
  --name loki \
  -p 3100:3100 \
  -v $(pwd)/loki-config.yml:/etc/loki/local-config.yml \
  grafana/loki:latest

# 启动 Grafana
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  grafana/grafana:latest
```

## 访问服务

### Grafana Web UI

- 地址：http://localhost:3000
- 用户名：`admin`
- 密码：`admin`

### Loki API

- 地址：http://localhost:3100
- 推送日志：POST http://localhost:3100/loki/api/v1/push

## 常见问题

### Q: Docker daemon 未运行

**错误信息：**
```
Cannot connect to the Docker daemon at unix:///Users/weiwang/.orbstack/run/docker.sock
```

**解决方案：**

1. **如果使用 OrbStack：**
   ```bash
   # 启动 OrbStack
   open /Applications/OrbStack.app
   ```

2. **如果使用 Docker Desktop：**
   ```bash
   # 启动 Docker Desktop
   open /Applications/Docker.app
   ```

3. **如果使用 Homebrew 安装的 Docker：**
   ```bash
   # 启动 Docker 服务
   colima start  # 如果使用 colima
   # 或
   sudo systemctl start docker  # Linux
   ```

### Q: 端口已被占用

**错误信息：**
```
Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:3000 -> 0.0.0.0:0: listen tcp 0.0.0.0:3000: bind: address already in use
```

**解决方案：**

```bash
# 查看占用端口的进程
lsof -i :3000
lsof -i :3100

# 杀死进程
kill -9 <PID>

# 或者修改 docker-compose.loki.yml 中的端口
# 将 "3000:3000" 改为 "3001:3000"
# 将 "3100:3100" 改为 "3101:3100"
```

### Q: 容器启动失败

**解决方案：**

```bash
# 查看容器日志
docker-compose -f docker-compose.loki.yml logs loki
docker-compose -f docker-compose.loki.yml logs grafana

# 重启容器
docker-compose -f docker-compose.loki.yml restart

# 完全重建
docker-compose -f docker-compose.loki.yml down
docker-compose -f docker-compose.loki.yml up -d
```

### Q: 如何停止服务

```bash
# 停止容器
docker-compose -f docker-compose.loki.yml stop

# 删除容器
docker-compose -f docker-compose.loki.yml down

# 删除容器和数据卷
docker-compose -f docker-compose.loki.yml down -v
```

## 数据持久化

默认情况下，Loki 和 Grafana 的数据存储在 Docker 数据卷中。

### 查看数据卷

```bash
docker volume ls | grep loki
```

### 备份数据

```bash
# 备份 Loki 数据
docker run --rm -v miniwow_loki_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/loki-backup.tar.gz -C /data .

# 备份 Grafana 数据
docker run --rm -v miniwow_grafana_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/grafana-backup.tar.gz -C /data .
```

## 性能优化

### 增加内存限制

编辑 `docker-compose.loki.yml`：

```yaml
services:
  loki:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
  
  grafana:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

### 增加 CPU 限制

```yaml
services:
  loki:
    deploy:
      resources:
        limits:
          cpus: '1'
        reservations:
          cpus: '0.5'
```

## 下一步

1. ✅ 安装 Docker
2. ✅ 启动 Loki 和 Grafana
3. ✅ 访问 Grafana Web UI
4. ✅ 配置数据源
5. ✅ 查看日志

## 支持

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 官方文档](https://docs.docker.com/compose/)
- [OrbStack 官方文档](https://orbstack.dev/)

