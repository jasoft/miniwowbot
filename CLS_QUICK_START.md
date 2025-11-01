# 腾讯云 CLS 日志集成 - 快速开始指南

## 5 分钟快速开始

### 第 1 步：安装依赖

```bash
# 安装官方 CLS SDK（推荐）
pip install tencentcloud-cls-sdk-python

# 或者安装通用 SDK
pip install tencentcloud-sdk-python
```

### 第 2 步：配置凭证

1. 复制 `.env.example` 为 `.env`
2. 填入腾讯云凭证：

```env
CLS_ENABLED=true
TENCENTCLOUD_SECRET_ID=your_secret_id_here
TENCENTCLOUD_SECRET_KEY=your_secret_key_here
CLS_REGION=ap-beijing
CLS_LOG_TOPIC_ID=your_log_topic_id_here
```

### 第 3 步：使用日志

#### 方式 1：最简单的方式

```python
from logger_config import setup_logger

# 创建日志记录器，启用 CLS
logger = setup_logger(name="my_app", enable_cls=True)

# 记录日志
logger.info("Hello, CLS!")
logger.error("Something went wrong!")
```

#### 方式 2：添加到现有日志记录器

```python
import logging
from cls_logger import add_cls_to_logger

logger = logging.getLogger(__name__)
add_cls_to_logger(logger)

logger.info("This log will be sent to CLS")
```

#### 方式 3：在 auto_dungeon.py 中使用

```python
from logger_config import setup_logger

# 在 auto_dungeon.py 中替换现有的日志配置
logger = setup_logger(name="auto_dungeon", enable_cls=True)
```

### 第 4 步：验证

运行示例代码：

```bash
python example_cls_integration.py
```

查看输出，应该看到类似的信息：

```
✅ CLS 客户端初始化成功 (通用 SDK): ap-beijing
✅ 腾讯云 CLS 日志已启用
```

## 常见问题

### Q: 如何获取腾讯云凭证？

A: 
1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 [访问管理](https://console.cloud.tencent.com/cam/capi)
3. 创建或获取 API 密钥

### Q: 如何创建 CLS 日志主题？

A:
1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 [CLS 日志服务](https://console.cloud.tencent.com/cls/overview)
3. 创建日志集和日志主题
4. 获取日志主题 ID

### Q: 日志多久会上传到 CLS？

A: 默认每 5 秒上传一次，或者缓冲区满 100 条日志时上传。可以在 `.env` 中修改：

```env
LOG_BUFFER_SIZE=100
LOG_UPLOAD_INTERVAL=5
```

### Q: 如何禁用 CLS？

A: 在 `.env` 中设置：

```env
CLS_ENABLED=false
```

### Q: 支持哪些 SDK？

A: 支持两种 SDK：
- 官方 CLS SDK (`tencentcloud-cls-sdk-python`) - 推荐
- 通用 SDK (`tencentcloud-sdk-python`) - 备选

系统会自动选择可用的 SDK。

## 下一步

- 查看 [CLS_INTEGRATION_GUIDE.md](CLS_INTEGRATION_GUIDE.md) 了解更多详情
- 查看 [example_cls_integration.py](example_cls_integration.py) 了解更多示例
- 在 [腾讯云 CLS 控制台](https://console.cloud.tencent.com/cls/overview) 查看日志

## 支持

如有问题，请参考：
- [腾讯云 CLS 文档](https://cloud.tencent.com/document/product/614)
- [腾讯云 CLS SDK 文档](https://github.com/TencentCloud/tencentcloud-cls-sdk-python)

