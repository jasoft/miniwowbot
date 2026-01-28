"""
设备连接工具模块

提供设备相关的公共工具函数。
"""
import logging
import threading

from airtest.core.api import connect_device

logger = logging.getLogger(__name__)


def connect_device_with_timeout(conn_str: str, timeout: int = 30) -> None:
    """
    使用线程超时机制连接设备

    Args:
        conn_str: 连接字符串，如 'Android://127.0.0.1:5037/127.0.0.1:5555'
        timeout: 超时时间（秒），默认30秒

    Raises:
        TimeoutError: 连接超时
        Exception: 连接过程中的其他错误
    """
    result = {"success": False, "error": None}

    def connect():
        try:
            connect_device(conn_str)
            result["success"] = True
        except Exception as e:
            result["error"] = e

    thread = threading.Thread(target=connect)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        logger.error(f"   ❌ 连接设备超时 ({timeout}秒)")
        raise TimeoutError(f"连接设备超时 ({timeout}秒)")
    if result["error"]:
        raise result["error"]
