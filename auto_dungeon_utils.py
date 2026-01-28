"""
auto_dungeon 工具函数模块
"""

import logging
import os
from typing import Optional

from airtest.core.api import sleep as airtest_sleep
from auto_dungeon_config import STOP_FILE

logger = logging.getLogger(__name__)

def sleep(seconds: float, reason: str = "[需要填写原因]") -> None:
    """sleep 的封装"""
    logger.info(f"💤 等待 {seconds} 秒, 原因是: {reason}")
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
