"""
auto_dungeon 工具函数模块
"""

import logging
import os
import sys
from typing import Optional

from airtest.core.api import sleep as airtest_sleep
from auto_dungeon_config import STOP_FILE

logger = logging.getLogger(__name__)


def _describe_sleep_caller(depth: int = 2) -> str:
    """返回调用栈上指定深度处的函数名，用于给未注明原因的等待补上下文。

    Args:
        depth: 相对本函数自身的栈深度。0 是本函数，1 是 ``sleep``，
            2（默认）是真正调用 ``sleep`` 的业务函数。

    Returns:
        str: 形如 ``未注明（调用 _open_exchange_tab）`` 的描述；取不到时返回 ``未注明原因``。
    """
    try:
        return f"未注明（调用 {sys._getframe(depth).f_code.co_name}）"
    except Exception:
        return "未注明原因"


def sleep(seconds: float, reason: Optional[str] = None) -> None:
    """等待指定秒数，并把等待原因写进日志。

    Args:
        seconds: 等待的秒数。
        reason: 等待原因。省略时自动取调用方函数名，避免日志里出现
            ``[需要填写原因]`` 这种开发期占位符（历史上每天约 150 条）。
    """
    logger.info(f"💤 等待 {seconds} 秒, 原因是: {reason or _describe_sleep_caller()}")
    airtest_sleep(seconds)


def normalize_emulator_name(name: Optional[str]) -> Optional[str]:
    """规范化模拟器名称"""
    if not name:
        return name
    name = str(name).strip()
    if name.lower().startswith("android://"):
        try:
            parts = name.split("/")
            if parts:
                return parts[-1].strip()
        except Exception:
            return name
    return name


def check_stop_signal() -> bool:
    """检查停止信号文件"""
    if os.path.exists(STOP_FILE):
        logger.warning(f"\n⛔ 检测到停止信号文件: {STOP_FILE}")
        logger.warning("⛔ 正在优雅地停止执行...")
        try:
            os.remove(STOP_FILE)
            logger.info("✅ 已删除停止信号文件")
        except Exception as e:
            logger.error(f"❌ 删除停止文件失败: {e}")
        return True
    return False
