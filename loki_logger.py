# -*- encoding=utf8 -*-
"""
Loki 日志模块
将日志发送到 Loki 服务进行集中管理和查询
"""

import json
import logging
import os
import queue
import threading
import time
from typing import Dict, Optional

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
        app_name: str = "lokilog",
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
        self.buffer_size = max(1, buffer_size)
        self.upload_interval = max(0.01, upload_interval)

        # 初始化标签
        self.labels = {"app": app_name, "host": os.getenv("HOSTNAME", "unknown")}
        if labels:
            self.labels.update(labels)

        # 日志上传队列与控制
        self.queue: "queue.SimpleQueue[Optional[Dict]]" = queue.SimpleQueue()
        self._sentinel = object()
        self.stop_event = threading.Event()

        # 创建 HTTP Session，禁用代理以避免代理导致的连接问题
        self._session = requests.Session()
        self._session.trust_env = False  # 禁用从环境变量读取代理设置

        # 启动后台上传线程
        self.upload_thread = threading.Thread(
            target=self._upload_worker,
            name=f"LokiUploader-{app_name}",
            daemon=True,
        )
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

            # 将日志入队，由后台线程负责上传
            self.queue.put(log_entry)
        except Exception:
            self.handleError(record)

    def _upload_worker(self):
        """后台上传工作线程"""
        batch = []
        last_flush_at = time.monotonic()

        try:
            while True:
                timeout = max(
                    0.0, self.upload_interval - (time.monotonic() - last_flush_at)
                )

                try:
                    log_entry = self.queue.get(timeout=timeout)
                except queue.Empty:
                    if batch:
                        self._flush_batch(batch)
                        last_flush_at = time.monotonic()
                    if self.stop_event.is_set():
                        break
                    continue

                if log_entry is self._sentinel:
                    if batch:
                        self._flush_batch(batch)
                    break

                batch.append(log_entry)
                now = time.monotonic()
                if (
                    len(batch) >= self.buffer_size
                    or (now - last_flush_at) >= self.upload_interval
                ):
                    self._flush_batch(batch)
                    last_flush_at = now

        except Exception as e:
            print(f"⚠️ 后台上传线程错误: {e}")
        finally:
            if batch:
                self._flush_batch(batch)

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

            # 发送到 Loki（使用 Session 以禁用代理）
            payload = {"streams": streams}
            headers = {"Content-Type": "application/json; charset=utf-8"}
            response = self._session.post(
                f"{self.loki_url}/loki/api/v1/push",
                json=payload,
                headers=headers,
                timeout=5,
            )

            if response.status_code != 204:
                print(
                    f"⚠️ 上传日志到 Loki 失败: {response.status_code} - {response.text}"
                )

        except requests.exceptions.Timeout:
            print("⚠️ 上传日志到 Loki 超时")
        except requests.exceptions.ConnectionError:
            print(f"⚠️ 无法连接到 Loki 服务: {self.loki_url}")
        except Exception as e:
            print(f"❌ 上传日志到 Loki 失败: {e}")

    def _flush_batch(self, batch):
        """上传当前批次并清空"""
        if not batch:
            return

        logs = list(batch)
        try:
            self._do_upload(logs)
        finally:
            batch.clear()

    def close(self):
        """关闭处理器"""
        try:
            # 设置停止事件并通知后台线程
            self.stop_event.set()
            if self.upload_thread.is_alive():
                self.queue.put(self._sentinel)
                self.upload_thread.join(timeout=self.upload_interval + 1)

            # 兜底处理：如果线程意外仍存活或队列中还有数据，主线程直接刷新
            pending = []
            while True:
                try:
                    item = self.queue.get_nowait()
                except queue.Empty:
                    break

                if item is self._sentinel:
                    continue
                pending.append(item)

            if pending:
                self._do_upload(pending)

        except Exception as e:
            print(f"⚠️ 关闭处理器失败: {e}")
        finally:
            super().close()


def create_loki_logger(
    name: str = "lokilog",
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
              示例: "lokilog", "lokilog.auto_dungeon", "lokilog.emulator_manager"
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式字符串，默认为 "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s"
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
        log_format = (
            "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s"
        )

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
