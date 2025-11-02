# -*- encoding=utf8 -*-
"""
Loki 日志模块
将日志发送到 Loki 服务进行集中管理和查询
"""

import logging
import os
import threading
import json
from typing import Optional, Dict
import requests

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class LokiHandler(logging.Handler):
    """Loki 日志处理器"""

    def __init__(
        self,
        loki_url: str,
        app_name: str = "miniwow",
        buffer_size: int = 50,
        upload_interval: int = 5,
        labels: Optional[Dict[str, str]] = None,
    ):
        """
        初始化 Loki 处理器

        Args:
            loki_url: Loki 服务地址，如 http://localhost:3100
            app_name: 应用名称
            buffer_size: 缓冲区大小
            upload_interval: 上传间隔（秒）
            labels: 额外的标签
        """
        super().__init__()
        self.loki_url = loki_url.rstrip("/")
        self.app_name = app_name
        self.buffer_size = buffer_size
        self.upload_interval = upload_interval

        # 初始化标签
        self.labels = {"app": app_name, "host": os.getenv("HOSTNAME", "unknown")}
        if labels:
            self.labels.update(labels)

        # 日志缓冲
        self.buffer = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # 启动后台上传线程
        self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()

    def emit(self, record: logging.LogRecord):
        """处理日志记录"""
        try:
            # 准备日志数据
            log_entry = {
                "timestamp": int(record.created * 1e9),  # Loki 需要纳秒时间戳
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # 尝试添加到缓冲区，使用非阻塞方式
            acquired = self.lock.acquire(blocking=False)
            if acquired:
                try:
                    self.buffer.append(log_entry)
                finally:
                    self.lock.release()
            else:
                # 如果无法获取锁，直接上传此条日志
                self._do_upload([log_entry])

        except Exception:
            self.handleError(record)

    def _upload_worker(self):
        """后台上传工作线程"""
        try:
            while not self.stop_event.is_set():
                # 等待指定的时间间隔
                if self.stop_event.wait(self.upload_interval):
                    # 被设置为停止
                    break

                # 刷新缓冲区
                with self.lock:
                    if self.buffer:
                        buffer_copy = self.buffer.copy()
                        self.buffer.clear()
                    else:
                        buffer_copy = []

                if buffer_copy:
                    self._do_upload(buffer_copy)

        except Exception as e:
            print(f"⚠️ 后台上传线程错误: {e}")

    def _do_upload(self, logs):
        """执行上传"""
        if not logs:
            return

        try:
            # 构建 Loki 请求格式
            streams = []
            for log_entry in logs:
                stream = {
                    "stream": self.labels,
                    "values": [
                        [
                            str(log_entry["timestamp"]),
                            json.dumps(
                                {
                                    "level": log_entry["level"],
                                    "logger": log_entry["logger"],
                                    "message": log_entry["message"],
                                    "module": log_entry["module"],
                                    "function": log_entry["function"],
                                    "line": log_entry["line"],
                                },
                                ensure_ascii=False,
                            ),
                        ]
                    ],
                }
                streams.append(stream)

            # 发送到 Loki
            payload = {"streams": streams}
            headers = {"Content-Type": "application/json; charset=utf-8"}
            response = requests.post(
                f"{self.loki_url}/loki/api/v1/push",
                json=payload,
                headers=headers,
                timeout=5,
            )

            if response.status_code == 204:
                print(f"✅ 成功上传 {len(logs)} 条日志到 Loki")
            else:
                print(
                    f"⚠️ 上传日志到 Loki 失败: {response.status_code} - {response.text}"
                )

        except requests.exceptions.Timeout:
            print("⚠️ 上传日志到 Loki 超时")
        except requests.exceptions.ConnectionError:
            print(f"⚠️ 无法连接到 Loki 服务: {self.loki_url}")
        except Exception as e:
            print(f"❌ 上传日志到 Loki 失败: {e}")

    def close(self):
        """关闭处理器"""
        try:
            # 设置停止事件
            self.stop_event.set()

            # 等待后台线程停止（非阻塞）
            if self.upload_thread.is_alive():
                self.upload_thread.join(timeout=1)

            # 最后一次刷新缓冲区（非阻塞方式）
            buffer_copy = []
            acquired = self.lock.acquire(blocking=False)
            if acquired:
                try:
                    if self.buffer:
                        buffer_copy = self.buffer.copy()
                        self.buffer.clear()
                finally:
                    self.lock.release()

            if buffer_copy:
                self._do_upload(buffer_copy)

        except Exception as e:
            print(f"⚠️ 关闭处理器失败: {e}")
        finally:
            super().close()


def create_loki_logger(
    name: str = "miniwow",
    level: str = "INFO",
    log_format: str = None,
    loki_url: str = None,
    enable_loki: bool = True,
) -> logging.Logger:
    """
    创建一个带 Loki 支持的日志记录器

    Args:
        name: 日志记录器名称（仅在 Loki 中有意义，console 输出中不显示）
              用于在 Loki 中作为 logger 标签，区分不同模块的日志
              示例: "miniwow", "miniwow.auto_dungeon", "miniwow.emulator_manager"
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式字符串，默认为 "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
                   如需在 console 中显示 logger name，可添加 %(name)s
        loki_url: Loki 服务地址，如 http://localhost:3100
        enable_loki: 是否启用 Loki 日志上传

    Returns:
        配置好的日志记录器

    Note:
        - name 参数仅在 Loki 中有意义，用于日志查询和过滤
        - console 输出中默认不显示 logger name
        - 如需在 console 中显示 logger name，可在 log_format 中添加 %(name)s
    """
    # 从环境变量加载配置
    if loki_url is None:
        loki_url = os.getenv("LOKI_URL", "http://localhost:3100")

    if enable_loki is None:
        enable_loki = os.getenv("LOKI_ENABLED", "true").lower() == "true"

    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False

    # 清除已有的处理器
    logger.handlers.clear()

    # 默认日志格式
    if log_format is None:
        log_format = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    formatter = logging.Formatter(log_format, datefmt="%H:%M:%S")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 如果启用 Loki，添加 Loki 处理器
    if enable_loki:
        try:
            loki_handler = LokiHandler(
                loki_url=loki_url,
                app_name=name,
            )
            logger.addHandler(loki_handler)
            print(f"✅ Loki 日志处理器已启用: {loki_url}")
        except Exception as e:
            print(f"⚠️ 添加 Loki 处理器失败: {e}")

    return logger
