# -*- encoding=utf8 -*-
"""
腾讯云 CLS 日志模块
用于将日志上传到腾讯云日志服务（Cloud Log Service）
"""

import logging
import os
import threading
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class CLSHandler(logging.Handler):
    """腾讯云 CLS 日志处理器"""

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

        Args:
            secret_id: 腾讯云 API Secret ID
            secret_key: 腾讯云 API Secret Key
            region: 地域（如 ap-nanjing）
            log_topic_id: 日志主题 ID
            buffer_size: 缓冲区大小（条数）
            upload_interval: 上传间隔（秒）
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
            from tencentcloud.log.logclient import LogClient

            # 构建 endpoint: https://{region}.cls.tencentcs.com
            endpoint = f"https://{self.region}.cls.tencentcs.com"

            # 创建 CLS 客户端
            self.cls_client = LogClient(endpoint, self.secret_id, self.secret_key)
            self.cls_available = True
            print(f"✅ CLS 客户端初始化成功: {endpoint}")
        except ImportError:
            print(
                "⚠️ 未安装腾讯云 CLS SDK，请运行: pip install tencentcloud-cls-sdk-python"
            )
            self.cls_available = False
        except Exception as e:
            print(f"❌ 初始化腾讯云 CLS 客户端失败: {e}")
            self.cls_available = False

    def emit(self, record: logging.LogRecord):
        """处理日志记录"""
        try:
            log_entry = self.format(record)
            log_data = {
                "timestamp": int(record.created),
                "level": record.levelname,
                "logger": record.name,
                "message": log_entry,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            should_flush = False
            with self.lock:
                self.buffer.append(log_data)
                if len(self.buffer) >= self.buffer_size:
                    should_flush = True

            if should_flush:
                self._flush_buffer()

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

            from tencentcloud.log.cls_pb2 import LogGroupList

            log_group_list = LogGroupList()
            log_group = log_group_list.logGroupList.add()
            log_group.filename = "python.log"
            log_group.source = "127.0.0.1"

            for log_data in buffer_copy:
                log = log_group.logs.add()
                log.time = int(log_data["timestamp"])

                contents = [
                    ("level", log_data["level"]),
                    ("logger", log_data["logger"]),
                    ("message", log_data["message"]),
                    ("module", log_data["module"]),
                    ("function", log_data["function"]),
                    ("line", str(log_data["line"])),
                ]

                for key, value in contents:
                    content = log.contents.add()
                    content.key = key
                    content.value = str(value)

            self.cls_client.put_log_raw(self.log_topic_id, log_group_list)
            print(f"✅ 上传 {len(buffer_copy)} 条日志到 CLS")

        except Exception as e:
            print(f"❌ 上传日志到 CLS 失败: {e}")

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
