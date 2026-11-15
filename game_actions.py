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
from vibe_ocr.game_actions import GameElement, GameElementCollection

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

    def find(
        self,
        text: str,
        timeout: float = 1,
        similarity_threshold: float = 0.7,
        occurrence: int = 1,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
        raise_exception: bool = False,
        exact: bool = False,
    ) -> GameElement:
        """按文本查找元素，可选完全匹配（``exact``）。

        为什么项目侧要自己实现 ``exact``：上游 ``vibe_ocr`` 的 ``find()`` 在
        源码里 2026-09-18 就加了 ``exact`` 参数，但**没有发布到 PyPI**
        （本地源码与 PyPI 的 0.1.6 同版本号、内容不同）。本项目
        ``pyproject.toml`` 依赖的是 ``vibe-ocr>=0.1.5``，一旦 ``uv sync``
        装回 PyPI 版本，``exact`` 就会消失：``find(exact=True)`` 抛
        ``TypeError``，而 ``find_text_and_click_safe`` 会把异常吞成 ``False``
        —— 表现为「领取按钮点了但返回 False」，静默失效。

        2026-11-15 真机实证：11-14 10:59 一次 ``uv run`` 触发 sync 把本地源码
        换成 PyPI 0.1.6，次日「领取主题奖励」里 ``find_text(exact=False)``
        直接抛 ``TypeError``，整步中断，上缴/宝箱/券兑换全线跳过。

        这里自行实现，且在 ``exact=False`` 时**不向父类传 ``exact``**，因此
        无论装的是哪个版本都能工作。

        Args:
            text: 目标文本。
            timeout: 最长等待秒数。
            similarity_threshold: OCR 置信度下限。
            occurrence: 取第几个匹配（1 起）；越界时沿用父类语义返回最后一个。
            use_cache: 是否复用 OCR 缓存。
            regions: 限定搜索区域编号列表。
            raise_exception: 未找到时是否抛 ``TimeoutError``。
            exact: 为 ``True`` 时要求文本去除首尾空白后完全相等，
                避免「确定」命中「确定要兑换这件商品吗？」这类提示语。

        Returns:
            GameElement: 命中的元素；未找到时返回空元素（``bool()`` 为 False）。
        """
        if not exact:
            return super().find(
                text,
                timeout=timeout,
                similarity_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
                regions=regions,
                raise_exception=raise_exception,
            )

        target = (text or "").strip()
        start_time = time.time()
        first_attempt = True
        while first_attempt or (time.time() - start_time < timeout):
            first_attempt = False
            matches = (
                self.find_all(use_cache=use_cache, regions=regions)
                .filter(lambda element: (element.text or "").strip() == target)
                .min_confidence(similarity_threshold)
            )
            if matches:
                return matches.get(occurrence - 1)
            if time.time() - start_time >= timeout:
                break
            time.sleep(0.1)

        msg = f"Not found (exact): '{text}'"
        logger.debug(msg)
        if raise_exception:
            raise TimeoutError(msg)
        return GameElement.empty(self)

    # 兼容性方法：find_text_and_click_safe
    # 父类没有这个方法，这里保留作为扩展
    def find_text_and_click_safe(self, text: str, default_return=False, **kwargs) -> Any:
        """安全查找并点击。

        异常一律降级为 ``default_return``，但**必须留痕**：这里曾用裸
        ``except Exception: return default_return``，把 ``exact`` 参数不被
        支持引发的 ``TypeError`` 吞成 ``False``，于是「领取按钮没被点击」
        在日志里只表现为一行 ``点击结果=False``，2026-11-15 之前无人发现。

        Args:
            text: 目标文本。
            default_return: 未命中或发生异常时的返回值。
            **kwargs: 透传给 :meth:`find` 的参数。

        Returns:
            Any: 命中的元素；否则为 ``default_return``。
        """
        try:
            kwargs["raise_exception"] = False
            el = self.find(text, **kwargs)
            if el:
                el.click()
                return el
            return default_return
        except Exception as exc:
            logger.warning(
                "⚠️ find_text_and_click_safe(%r) 异常，已降级为 %r: %s", text, default_return, exc
            )
            return default_return
