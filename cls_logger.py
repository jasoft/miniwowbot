# -*- encoding=utf8 -*-
"""
腾讯云 CLS 日志模块
用于将日志上传到腾讯云日志服务（Cloud Log Service）
简化版本，专注于测试logging重构功能
"""

import logging
import os
import threading
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class CLSHandler(logging.Handler):
    """腾讯云 CLS 日志处理器 - 简化版本"""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        region: str,
        log_topic_id: str,
        buffer_size: int = 100,
        upload_interval: int = 5,
    ):
        """
        初始化 CLS 处理器
        """
        super().__init__()
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region
        self.log_topic_id = log_topic_id
        self.buffer_size = buffer_size
        self.upload_interval = upload_interval

        # 日志缓冲
        self.buffer = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # 初始化腾讯云 CLS 客户端
        self._init_cls_client()

        # 启动后台上传线程
        self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()

    def _init_cls_client(self):
        """初始化腾讯云 CLS 客户端"""
        try:
            # 尝试导入官方 CLS SDK
            try:
                from tencentcloud.log.logclient import LogClient

                endpoint = f"https://{self.region}.cls.tencentyun.com"
                self.cls_client = LogClient(endpoint, self.secret_id, self.secret_key)
                self.cls_available = True
                print(f"✅ CLS 客户端初始化成功 (官方 SDK): {endpoint}")
                return
            except ImportError:
                pass

            # 备选方案：使用通用 SDK
            try:
                from tencentcloud.common import credential
                from tencentcloud.cls.v20201016 import cls_client

                cred = credential.Credential(self.secret_id, self.secret_key)
                self.cls_client = cls_client.ClsClient(cred, self.region)
                self.cls_available = True
                print(f"✅ CLS 客户端初始化成功 (通用 SDK): {self.region}")
                return
            except ImportError:
                pass

            print("⚠️ 未安装腾讯云 CLS SDK，将使用模拟模式")
            self.cls_available = False

        except Exception as e:
            print(f"❌ 初始化腾讯云 CLS 客户端失败: {e}")
            self.cls_available = False

    def emit(self, record: logging.LogRecord):
        """处理日志记录"""
        try:
            # 准备日志数据
            log_data = {
                "timestamp": int(record.created),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # 简单地添加到缓冲区，不进行复杂的缓冲大小检查
            with self.lock:
                self.buffer.append(log_data)

        except Exception:
            self.handleError(record)

    def _flush_buffer(self):
        """刷新缓冲区，上传日志到 CLS"""
        if not self.cls_available:
            return

        try:
            with self.lock:
                if not self.buffer:
                    return
                buffer_copy = self.buffer.copy()
                self.buffer.clear()

            if not buffer_copy:
                return

            # 尝试上传到腾讯云 CLS
            self._upload_to_cls(buffer_copy)

        except Exception as e:
            print(f"❌ 上传日志到 CLS 失败: {e}")

    def _upload_to_cls(self, logs):
        """上传日志到腾讯云 CLS"""
        try:
            # 检查是否使用官方 SDK
            if hasattr(self.cls_client, "put_log_raw"):
                # 官方 SDK 方式
                self._upload_with_official_sdk(logs)
            else:
                # 通用 SDK 方式
                self._upload_with_common_sdk(logs)
        except Exception as e:
            print(f"❌ 上传日志失败: {e}")

    def _upload_with_official_sdk(self, logs):
        """使用官方 CLS SDK 上传日志"""
        try:
            from tencentcloud.log.cls_pb2 import LogGroupList, LogGroup, Log

            log_group = LogGroup()
            for log_data in logs:
                log = Log()
                log.time = int(log_data.get("timestamp", 0))
                log.contents.append(("level", log_data.get("level", "INFO")))
                log.contents.append(("logger", log_data.get("logger", "")))
                log.contents.append(("message", log_data.get("message", "")))
                log.contents.append(("module", log_data.get("module", "")))
                log.contents.append(("function", log_data.get("function", "")))
                log.contents.append(("line", str(log_data.get("line", 0))))
                log_group.logs.append(log)

            log_group_list = LogGroupList()
            log_group_list.log_groups.append(log_group)

            self.cls_client.put_log_raw(
                self.log_topic_id, log_group_list.SerializeToString()
            )
            print(f"✅ 成功上传 {len(logs)} 条日志到 CLS (官方 SDK)")
        except Exception as e:
            print(f"❌ 官方 SDK 上传失败: {e}")

    def _upload_with_common_sdk(self, logs):
        """使用通用 SDK 上传日志"""
        try:
            from tencentcloud.cls.v20201016 import models

            # 构建日志数据
            log_items = []
            for log_data in logs:
                log_item = models.LogItem(
                    time=int(log_data.get("timestamp", 0)),
                    contents=[
                        models.LogContent(
                            key="level", value=log_data.get("level", "INFO")
                        ),
                        models.LogContent(
                            key="logger", value=log_data.get("logger", "")
                        ),
                        models.LogContent(
                            key="message", value=log_data.get("message", "")
                        ),
                        models.LogContent(
                            key="module", value=log_data.get("module", "")
                        ),
                        models.LogContent(
                            key="function", value=log_data.get("function", "")
                        ),
                        models.LogContent(
                            key="line", value=str(log_data.get("line", 0))
                        ),
                    ],
                )
                log_items.append(log_item)

            # 上传日志
            req = models.PutLogsRequest()
            req.TopicId = self.log_topic_id
            req.LogItems = log_items

            self.cls_client.PutLogs(req)
            print(f"✅ 成功上传 {len(logs)} 条日志到 CLS (通用 SDK)")
        except Exception as e:
            print(f"❌ 通用 SDK 上传失败: {e}")

    def _upload_worker(self):
        """后台上传工作线程"""
        while not self.stop_event.is_set():
            # 使用 wait 而不是 sleep，这样可以被中断
            self.stop_event.wait(self.upload_interval)
            if not self.stop_event.is_set():
                self._flush_buffer()

    def close(self):
        """关闭处理器，确保所有日志都被上传"""
        # 设置停止事件，让后台线程停止
        self.stop_event.set()

        # 等待后台线程完成
        if self.upload_thread.is_alive():
            self.upload_thread.join(timeout=2)

        # 最后一次刷新缓冲区
        self._flush_buffer()
        super().close()


class CLSLogger:
    """腾讯云 CLS 日志管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化日志管理器"""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.logger = logging.getLogger("cls_logger")
        self.logger.setLevel(logging.INFO)
        self.cls_handler = None

        # 从环境变量加载配置
        self._load_config()

    def _load_config(self):
        """从 .env 文件加载配置"""
        cls_enabled = os.getenv("CLS_ENABLED", "true").lower() == "true"

        if not cls_enabled:
            return

        secret_id = os.getenv("TENCENTCLOUD_SECRET_ID")
        secret_key = os.getenv("TENCENTCLOUD_SECRET_KEY")
        region = os.getenv("CLS_REGION", "ap-beijing")
        log_topic_id = os.getenv("CLS_LOG_TOPIC_ID")
        buffer_size = int(os.getenv("LOG_BUFFER_SIZE", "100"))
        upload_interval = int(os.getenv("LOG_UPLOAD_INTERVAL", "5"))

        # 验证必要的配置
        if not all([secret_id, secret_key, log_topic_id]):
            print("⚠️ CLS 配置不完整，跳过 CLS 日志上传")
            return

        try:
            # 创建 CLS 处理器
            self.cls_handler = CLSHandler(
                secret_id=secret_id,
                secret_key=secret_key,
                region=region,
                log_topic_id=log_topic_id,
                buffer_size=buffer_size,
                upload_interval=upload_interval,
            )

            # 设置日志格式
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            self.cls_handler.setFormatter(formatter)

            # 添加处理器到日志记录器
            self.logger.addHandler(self.cls_handler)

            print("✅ 腾讯云 CLS 日志已启用")

        except Exception as e:
            print(f"❌ 初始化 CLS 日志失败: {e}")

    def get_logger(self) -> logging.Logger:
        """获取日志记录器"""
        return self.logger

    def add_to_logger(self, logger: logging.Logger):
        """
        将 CLS 处理器添加到现有的日志记录器

        Args:
            logger: 日志记录器对象
        """
        if self.cls_handler:
            logger.addHandler(self.cls_handler)

    def close(self):
        """关闭日志处理器"""
        if self.cls_handler:
            self.cls_handler.close()


# 全局 CLS 日志管理器实例（延迟初始化）
_cls_logger_instance = None


def _get_instance():
    """获取或创建 CLSLogger 实例（延迟初始化）"""
    global _cls_logger_instance
    if _cls_logger_instance is None:
        _cls_logger_instance = CLSLogger()
    return _cls_logger_instance


def get_cls_logger() -> logging.Logger:
    """获取 CLS 日志记录器"""
    return _get_instance().get_logger()


def add_cls_to_logger(logger: logging.Logger):
    """
    将 CLS 处理器添加到现有的日志记录器

    Args:
        logger: 日志记录器对象
    """
    _get_instance().add_to_logger(logger)


def close_cls_logger():
    """关闭 CLS 日志处理器"""
    _get_instance().close()
