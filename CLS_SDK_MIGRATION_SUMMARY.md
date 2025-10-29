# CLS 日志模块 SDK 迁移总结

## 📋 概述

本文档总结了腾讯云 CLS 日志模块从通用 SDK 迁移到官方 CLS SDK 的所有改动。

---

## 🔍 问题分析

### 原始问题
- ❌ 集成测试超时
- ❌ 腾讯云 CLS 控制台中看不到日志
- ❌ 日志无法正确上传

### 根本原因
使用了**错误的 SDK**：
- **错误的 SDK**：`tencentcloud-sdk-python`（通用腾讯云 API SDK）
- **正确的 SDK**：`tencentcloud-cls-sdk-python`（官方 CLS 专用 SDK）

两个 SDK 的 API 完全不同：

| 方面 | 错误的 SDK | 正确的 SDK |
|------|----------|----------|
| 导入路径 | `tencentcloud.cls.v20201016.cls_client` | `tencentcloud.log.logclient` |
| 客户端类 | `ClsClient` | `LogClient` |
| Endpoint | `{region}.cls.tencentyun.com` | `https://{region}.cls.tencentcs.com` |
| 日志格式 | JSON 格式 | Protocol Buffer 格式 |
| 上传方法 | `UploadLog(request)` | `put_log_raw(topic_id, log_group_list)` |

---

## ✅ 修复内容

### 1. 修改 `_init_cls_client()` 方法

**改进前：**
```python
from tencentcloud.cls.v20201016 import cls_client
# 错误的 endpoint 格式
endpoint = "cls.tencentcloudapi.com"
```

**改进后：**
```python
from tencentcloud.log.logclient import LogClient

# 正确的 endpoint 格式
endpoint = f"https://{self.region}.cls.tencentcs.com"
self.cls_client = LogClient(endpoint, self.secret_id, self.secret_key)
```

### 2. 修改 `_flush_buffer()` 方法

**改进前：**
```python
# 使用 JSON 格式和通用 API
from tencentcloud.cls.v20201016.models import UploadLogRequest
request = UploadLogRequest()
# ... 构建 JSON 格式的请求
```

**改进后：**
```python
# 使用 Protocol Buffer 格式
from tencentcloud.log.cls_pb2 import LogGroupList

log_group_list = LogGroupList()
log_group = log_group_list.logGroupList.add()
# ... 构建 Protocol Buffer 格式的日志

self.cls_client.put_log_raw(self.log_topic_id, log_group_list)
```

### 3. 移除不必要的参数

- ❌ 移除 `log_set_id` 参数（官方 SDK 不需要）
- ✅ 保留 `log_topic_id` 参数

### 4. 改进时间戳处理

- **改进前**：毫秒时间戳 `int(record.created * 1000)`
- **改进后**：秒级时间戳 `int(record.created)`

---

## 📝 修改的文件

### `cls_logger.py`
- 更新 `CLSHandler.__init__()` 方法签名（移除 `log_set_id`）
- 更新 `_init_cls_client()` 方法（使用官方 SDK）
- 更新 `_flush_buffer()` 方法（使用 Protocol Buffer 格式）
- 更新 `_load_config()` 方法（移除 `log_set_id` 配置）

### `CHANGELOG.md`
- 添加 SDK 迁移的详细记录

---

## 🚀 安装依赖

```bash
# 安装官方 CLS SDK
pip install tencentcloud-cls-sdk-python

# 或使用 uv
uv pip install tencentcloud-cls-sdk-python
```

---

## 📋 配置说明

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

**注意**：不再需要 `CLS_LOG_SET_ID` 参数。

---

## 💻 使用方式

### 方式 1：使用全局 CLS 日志记录器

```python
from cls_logger import get_cls_logger

logger = get_cls_logger()
logger.info("这是一条日志")
```

### 方式 2：将 CLS 处理器添加到现有日志记录器

```python
import logging
from cls_logger import add_cls_to_logger

logger = logging.getLogger("my_app")
add_cls_to_logger(logger)
logger.info("这是一条日志")
```

### 方式 3：关闭 CLS 日志处理器

```python
from cls_logger import close_cls_logger

close_cls_logger()
```

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

## ✨ 关键改进

1. ✅ **正确的 SDK**：使用官方 CLS 专用 SDK
2. ✅ **正确的 API**：使用 `LogClient` 和 `put_log_raw()` 方法
3. ✅ **正确的格式**：使用 Protocol Buffer 格式
4. ✅ **正确的 Endpoint**：使用 `https://{region}.cls.tencentcs.com`
5. ✅ **简化配置**：移除不必要的 `log_set_id` 参数

---

## 📚 参考资源

- [腾讯云 CLS SDK 官方文档](https://github.com/TencentCloud/tencentcloud-cls-sdk-python)
- [腾讯云 CLS API 文档](https://cloud.tencent.com/document/product/614/16873)

---

## 🎯 下一步

1. ✅ 安装官方 CLS SDK
2. ✅ 更新 `.env` 文件配置
3. ✅ 运行测试脚本验证功能
4. ✅ 在腾讯云控制台查看日志

---

## 📞 故障排查

### 问题：导入失败 - "No module named 'tencentcloud.log'"

**解决方案**：安装官方 CLS SDK
```bash
pip install tencentcloud-cls-sdk-python
```

### 问题：日志未上传

**检查清单**：
1. ✅ 确认 `.env` 文件中的凭证正确
2. ✅ 确认 `CLS_ENABLED=true`
3. ✅ 确认 `CLS_LOG_TOPIC_ID` 正确
4. ✅ 检查网络连接
5. ✅ 查看控制台输出的错误信息

### 问题：连接超时

**解决方案**：
1. 检查网络连接
2. 确认 endpoint 格式正确
3. 检查腾讯云账户是否有效

---

## 📊 版本信息

- **修改日期**：2025-10-29
- **SDK 版本**：tencentcloud-cls-sdk-python v1.0.4+
- **Python 版本**：3.8+


