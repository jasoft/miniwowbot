# -*- encoding=utf8 -*-
"""
游戏操作动作模块
封装了基于 vibe-ocr 的查找、点击等操作，提供声明式 API
所有查找逻辑均基于 vibe-ocr.GameActions 实现
"""

import logging
import time
from functools import wraps
from typing import Any, List, Optional

from vibe_ocr.game_actions import GameActions as BaseGameActions

# Re-export classes from library
from vibe_ocr.game_actions import GameElementCollection

logger = logging.getLogger("bottools.game_actions")


def timer_decorator(func):
    """
    装饰器：计算函数的执行时间
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_time = time.perf_counter() - start_time

        log_msg = f"{func.__name__} 执行时间: {elapsed_time:.4f}秒"
        if elapsed_time < 0.01:
            logger.debug(f"⚡ {log_msg} (< 10ms)")
        elif elapsed_time < 0.5:
            logger.debug(f"⏱️ {log_msg}")
        elif elapsed_time < 2.0:
            logger.debug(f"🐌 {log_msg} (> 500ms)")
        else:
            logger.warning(f"🐢 {log_msg} (> 1s)")

        return result

    return wrapper


class GameActions(BaseGameActions):
    """
    封装游戏内的查找和操作逻辑
    继承自 vibe_ocr.GameActions，添加了本地特有的日志和计时装饰器
    """

    def __init__(self, ocr_helper, click_interval=1):
        super().__init__(ocr_helper, click_interval)

    @timer_decorator
    def find_all(
        self,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> GameElementCollection:
        """
        覆盖父类方法以添加计时装饰器
        """
        return super().find_all(use_cache=use_cache, regions=regions)

    # 兼容性方法：find_text_and_click_safe
    # 父类没有这个方法，这里保留作为扩展
    def find_text_and_click_safe(self, text: str, default_return=False, **kwargs) -> Any:
        """安全查找并点击"""
        try:
            kwargs["raise_exception"] = False
            el = self.find(text, **kwargs)
            if el:
                el.click()
                return el
            return default_return
        except Exception:
            return default_return
