# CLS 日志模块设置指南

## 📋 概述

本指南说明如何使用腾讯云 CLS 日志模块将日志上传到腾讯云日志服务。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装官方 CLS SDK
pip install tencentcloud-cls-sdk-python

# 或使用 uv
uv pip install tencentcloud-cls-sdk-python
```

### 2. 配置环境变量

编辑 `.env` 文件，填入腾讯云凭证：

```env
CLS_ENABLED=true
TENCENTCLOUD_SECRET_ID=your_secret_id
TENCENTCLOUD_SECRET_KEY=your_secret_key
CLS_REGION=ap-nanjing
CLS_LOG_TOPIC_ID=your_log_topic_id
LOG_BUFFER_SIZE=100
LOG_UPLOAD_INTERVAL=5
```

**参数说明**：
- `CLS_ENABLED`：是否启用 CLS 日志（true/false）
- `TENCENTCLOUD_SECRET_ID`：腾讯云 API Secret ID
- `TENCENTCLOUD_SECRET_KEY`：腾讯云 API Secret Key
- `CLS_REGION`：日志服务所在地域（如 ap-nanjing）
- `CLS_LOG_TOPIC_ID`：日志主题 ID
- `LOG_BUFFER_SIZE`：缓冲区大小（条数）
- `LOG_UPLOAD_INTERVAL`：上传间隔（秒）

### 3. 在代码中使用

#### 方式 1：使用全局 CLS 日志记录器

```python
from cls_logger import get_cls_logger

logger = get_cls_logger()
logger.info("这是一条日志")
logger.warning("这是一条警告")
logger.error("这是一条错误")
```

#### 方式 2：将 CLS 处理器添加到现有日志记录器

```python
import logging
from cls_logger import add_cls_to_logger

logger = logging.getLogger("my_app")
add_cls_to_logger(logger)
logger.info("这条日志会上传到腾讯云 CLS")
```

#### 方式 3：在 auto_dungeon.py 中使用

```python
import logging
from cls_logger import add_cls_to_logger

# 现有的日志配置
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 添加 CLS 处理器
add_cls_to_logger(logger)

# 现在所有日志都会上传到腾讯云 CLS
logger.info("副本开始运行")
```

### 4. 验证功能

运行测试脚本：

```bash
python test_cls_final.py
```

### 5. 查看日志

1. 登录腾讯云控制台
2. 进入日志服务 (CLS)
3. 选择对应的日志主题
4. 查看日志是否已上传

---

## 📝 API 参考

### `get_cls_logger()`

获取全局 CLS 日志记录器。

```python
from cls_logger import get_cls_logger

logger = get_cls_logger()
logger.info("日志内容")
```

### `add_cls_to_logger(logger)`

将 CLS 处理器添加到现有的日志记录器。

```python
import logging
from cls_logger import add_cls_to_logger

logger = logging.getLogger("my_app")
add_cls_to_logger(logger)
```

### `close_cls_logger()`

关闭 CLS 日志处理器，确保所有日志都被上传。

```python
from cls_logger import close_cls_logger

close_cls_logger()
```

---

## 🔍 故障排查

### 问题 1：导入失败 - "No module named 'tencentcloud.log'"

**原因**：未安装官方 CLS SDK

**解决方案**：
```bash
pip install tencentcloud-cls-sdk-python
```

### 问题 2：日志未上传

**检查清单**：
1. ✅ 确认 `.env` 文件中的凭证正确
2. ✅ 确认 `CLS_ENABLED=true`
3. ✅ 确认 `CLS_LOG_TOPIC_ID` 正确
4. ✅ 检查网络连接
5. ✅ 查看控制台输出的错误信息

### 问题 3：连接超时

**原因**：网络连接问题或 endpoint 配置错误

**解决方案**：
1. 检查网络连接
2. 确认 endpoint 格式正确：`https://{region}.cls.tencentcs.com`
3. 检查腾讯云账户是否有效

### 问题 4：权限错误

**原因**：Secret ID 或 Secret Key 错误

**解决方案**：
1. 登录腾讯云控制台
2. 进入 API 密钥管理
3. 确认 Secret ID 和 Secret Key 正确
4. 检查 API 密钥是否有 CLS 权限

---

## 📊 日志格式

上传到腾讯云 CLS 的日志包含以下字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| `level` | 日志级别 | INFO, WARNING, ERROR |
| `logger` | 日志记录器名称 | cls_logger |
| `message` | 日志消息 | 这是一条日志 |
| `module` | 模块名称 | auto_dungeon |
| `function` | 函数名称 | run_dungeon |
| `line` | 行号 | 123 |
| `timestamp` | 时间戳 | 1635000000 |

---

## 🧪 测试

### 运行集成测试

```bash
python test_cls_final.py
```

### 运行单元测试

```bash
pytest tests/test_cls_logger.py -v
```

---

## 📚 相关文档

- [CLS SDK 迁移总结](CLS_SDK_MIGRATION_SUMMARY.md)
- [CLS 最终实现总结](CLS_FINAL_IMPLEMENTATION.md)
- [腾讯云 CLS 官方文档](https://cloud.tencent.com/document/product/614)
- [腾讯云 CLS SDK GitHub](https://github.com/TencentCloud/tencentcloud-cls-sdk-python)

---

## ✨ 总结

CLS 日志模块已成功配置，现在可以将日志上传到腾讯云 CLS 服务。按照上述步骤进行配置和使用即可。


