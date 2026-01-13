"""
副本自动遍历脚本 - 主入口

本文件只保留入口点，所有核心逻辑已迁移到 auto_dungeon_core.py。
"""
from auto_dungeon_core import main_wrapper, send_bark_notification

# 向后兼容：导出常用函数
__all__ = ["main_wrapper", "send_bark_notification"]
