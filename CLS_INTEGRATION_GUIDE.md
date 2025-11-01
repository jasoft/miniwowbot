# 腾讯云 CLS 日志集成指南

## 概述

本项目集成了腾讯云 CLS（Cloud Log Service）日志服务，支持将应用日志实时上传到腾讯云日志服务。

## 功能特性

- ✅ 自动日志上传到腾讯云 CLS
- ✅ 日志缓冲机制，提高性能
- ✅ 后台异步上传，不阻塞主程序
- ✅ 单例模式，全局统一管理
- ✅ 支持与现有日志系统集成
- ✅ 环境变量配置
- ✅ 支持两种腾讯云 SDK（官方 CLS SDK 和通用 SDK）

## 安装依赖

### 方式 1: 使用官方 CLS SDK（推荐）

```bash
pip install tencentcloud-cls-sdk-python
```

### 方式 2: 使用通用 SDK

```bash
pip install tencentcloud-sdk-python
```

### 方式 3: 同时安装两个 SDK

```bash
pip install tencentcloud-cls-sdk-python tencentcloud-sdk-python
```

## 配置

### 1. 创建 .env 文件

复制 `.env.example` 为 `.env`，并填入腾讯云凭证：

```env
# 启用 CLS 日志
CLS_ENABLED=true

# 腾讯云 API 密钥
TENCENTCLOUD_SECRET_ID=your_secret_id_here
TENCENTCLOUD_SECRET_KEY=your_secret_key_here

# CLS 配置
CLS_REGION=ap-beijing
CLS_LOG_TOPIC_ID=your_log_topic_id_here

# 日志缓冲配置
LOG_BUFFER_SIZE=100
LOG_UPLOAD_INTERVAL=5
```

### 2. 获取腾讯云凭证

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 [访问管理](https://console.cloud.tencent.com/cam/capi) 页面
3. 创建或获取 API 密钥（Secret ID 和 Secret Key）

### 3. 创建 CLS 日志主题

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 [CLS 日志服务](https://console.cloud.tencent.com/cls/overview)
3. 创建日志集和日志主题
4. 获取日志主题 ID

## 使用方法

### 方式 1: 使用 setup_logger 启用 CLS

```python
from logger_config import setup_logger

# 创建日志记录器，启用 CLS
logger = setup_logger(
    name="my_app",
    level="INFO",
    enable_cls=True,  # 启用 CLS
)

# 记录日志
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
```

### 方式 2: 将 CLS 添加到现有日志记录器

```python
import logging
from cls_logger import add_cls_to_logger

# 创建日志记录器
logger = logging.getLogger(__name__)

# 添加 CLS 处理器
add_cls_to_logger(logger)

# 记录日志
logger.info("这条日志会上传到 CLS")
```

### 方式 3: 使用 CLS 专用日志记录器

```python
from cls_logger import get_cls_logger

# 获取 CLS 日志记录器
logger = get_cls_logger()

# 记录日志
logger.info("这条日志会上传到 CLS")
```

## 配置参数说明

### logger_config.setup_logger()

```python
def setup_logger(
    name: Optional[str] = None,
    level: str = "INFO",
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
    use_color: bool = True,
    enable_cls: bool = False,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式
        date_format: 时间格式
        use_color: 是否使用彩色日志
        enable_cls: 是否启用腾讯云 CLS 日志上传

    Returns:
        配置好的日志记录器
    """
```

### 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| CLS_ENABLED | 是否启用 CLS | true |
| TENCENTCLOUD_SECRET_ID | 腾讯云 Secret ID | 无 |
| TENCENTCLOUD_SECRET_KEY | 腾讯云 Secret Key | 无 |
| CLS_REGION | CLS 地域 | ap-beijing |
| CLS_LOG_TOPIC_ID | 日志主题 ID | 无 |
| LOG_BUFFER_SIZE | 日志缓冲区大小 | 100 |
| LOG_UPLOAD_INTERVAL | 日志上传间隔（秒） | 5 |

## 工作流程

```
日志记录
   ↓
CLSHandler.emit()
   ↓
添加到缓冲区
   ↓
缓冲区满或定时上传
   ↓
后台线程上传到 CLS
   ↓
腾讯云 CLS 服务
```

## 性能优化

1. **日志缓冲机制**：减少网络请求，提高性能
2. **异步上传**：不阻塞主程序
3. **可配置参数**：可根据需要调整缓冲区大小和上传间隔

## 故障排查

### 问题 1: CLS 客户端初始化失败

**症状**: 日志中出现 "❌ 初始化腾讯云 CLS 客户端失败"

**解决方案**:
1. 检查是否安装了腾讯云 SDK
2. 检查 .env 文件中的凭证是否正确
3. 检查网络连接

### 问题 2: 日志未上传到 CLS

**症状**: 日志在控制台输出，但未出现在 CLS 控制台

**解决方案**:
1. 检查 CLS_ENABLED 是否设置为 true
2. 检查日志主题 ID 是否正确
3. 检查腾讯云凭证是否有权限访问 CLS
4. 等待日志上传间隔（默认 5 秒）

### 问题 3: 性能下降

**症状**: 应用运行变慢

**解决方案**:
1. 增加 LOG_BUFFER_SIZE（减少上传频率）
2. 增加 LOG_UPLOAD_INTERVAL（减少上传频率）
3. 降低日志级别（减少日志数量）

## 示例

查看 `example_cls_integration.py` 了解更多使用示例。

运行示例：

```bash
python example_cls_integration.py
```

## 相关文件

- `cls_logger.py` - 腾讯云 CLS 日志模块
- `logger_config.py` - 通用日志配置模块
- `example_cls_integration.py` - 集成示例
- `.env.example` - 环境变量配置模板

## 支持的 SDK

### 官方 CLS SDK

- 包名: `tencentcloud-cls-sdk-python`
- 优点: 专为 CLS 设计，性能更好
- 缺点: 功能相对单一

### 通用 SDK

- 包名: `tencentcloud-sdk-python`
- 优点: 支持所有腾讯云服务
- 缺点: 功能复杂，性能相对较低

## 常见问题

**Q: 如何禁用 CLS 日志？**

A: 在 .env 文件中设置 `CLS_ENABLED=false`

**Q: 如何修改日志上传间隔？**

A: 在 .env 文件中修改 `LOG_UPLOAD_INTERVAL` 的值

**Q: 如何查看 CLS 日志？**

A: 登录腾讯云控制台，进入 CLS 日志服务，选择对应的日志主题

## 许可证

MIT

