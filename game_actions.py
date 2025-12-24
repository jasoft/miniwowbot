# -*- encoding=utf8 -*-
"""
游戏操作动作模块
封装了基于 OCR 的查找、点击等操作，提供声明式 API
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from airtest.core.api import sleep as airtest_sleep
from airtest.core.api import touch

logger = logging.getLogger("miniwow.game_actions")


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
        elif elapsed_time < 1.0:
            logger.warning(f"🐌 {log_msg} (> 500ms)")
        else:
            logger.warning(f"🐢 {log_msg} (> 1s)")

        return result

    return wrapper


class GameElement(dict):
    """
    表示一个游戏元素（基于 OCR 识别结果）
    继承自 dict 以保持向后兼容
    """

    def __init__(self, data: Dict[str, Any], action_context: "GameActions"):
        super().__init__(data or {})
        self.action_context = action_context

    @property
    def center(self):
        return self.get("center")

    @property
    def text(self):
        return self.get("text")

    @property
    def confidence(self):
        return self.get("confidence", 0.0)

    def click(self) -> "GameElement":
        """点击该元素中心点"""
        if self.center:
            self.action_context.touch(self.center)
            self.action_context.sleep(self.action_context.click_interval)
        else:
            logger.warning("⚠️ 尝试点击不存在的元素")
        return self

    def offset_click(self, x: int = 0, y: int = 0) -> "GameElement":
        """偏移点击"""
        if self.center:
            pos = (self.center[0] + x, self.center[1] + y)
            self.action_context.touch(pos)
            self.action_context.sleep(self.action_context.click_interval)
        return self

    def sleep(self, seconds: float) -> "GameElement":
        """休眠指定时间"""
        self.action_context.sleep(seconds)
        return self

    def __repr__(self):
        return f"GameElement(text='{self.text}', center={self.center})"


class GameElementCollection(list):
    """
    游戏元素集合，支持链式操作
    """

    def __init__(self, elements: List[Dict[str, Any]], action_context: "GameActions"):
        # 将原始字典转换为 GameElement 对象
        super().__init__([GameElement(e, action_context) for e in elements])
        self.action_context = action_context

    def filter(self, predicate: Callable[[GameElement], bool]) -> "GameElementCollection":
        """过滤元素"""
        return GameElementCollection([e for e in self if predicate(e)], self.action_context)

    def contains(self, text: str) -> "GameElementCollection":
        """过滤包含指定文本的元素"""
        return self.filter(lambda e: text in (e.text or ""))

    def equals(self, text: str) -> "GameElementCollection":
        """过滤等于指定文本的元素"""
        return self.filter(lambda e: e.text == text)

    def min_confidence(self, threshold: float) -> "GameElementCollection":
        """过滤置信度"""
        return self.filter(lambda e: e.confidence >= threshold)

    def first(self) -> Optional[GameElement]:
        """获取第一个元素"""
        return self[0] if self else None

    def last(self) -> Optional[GameElement]:
        """获取最后一个元素"""
        return self[-1] if self else None

    def get(self, index: int) -> Optional[GameElement]:
        """获取指定索引的元素"""
        if 0 <= index < len(self):
            return self[index]
        return None

    def map(self, func: Callable[[GameElement], Any]) -> List[Any]:
        """对每个元素应用函数并返回结果列表"""
        return [func(e) for e in self]

    def each(self, func: Callable[[GameElement], None]) -> "GameElementCollection":
        """对每个元素执行操作（副作用），返回集合本身以支持链式调用"""
        for e in self:
            func(e)
        return self

    def click_all(self) -> "GameElementCollection":
        """点击集合中的所有元素"""
        for e in self:
            e.click()
        return self

    def is_empty(self) -> bool:
        return len(self) == 0

    def count(self) -> int:
        return len(self)


class GameActions:
    """
    封装游戏内的查找和操作逻辑
    """

    def __init__(self, ocr_helper, click_interval=1):
        """
        初始化 GameActions

        Args:
            ocr_helper: OCRHelper 实例
            click_interval: 点击后的等待时间 (秒)
        """
        self.ocr_helper = ocr_helper
        self.click_interval = click_interval

    def sleep(self, seconds: float, reason: str = ""):
        """sleep 的封装"""
        if reason:
            logger.info(f"💤 等待 {seconds} 秒, 原因是: {reason}")
        airtest_sleep(seconds)

    def touch(self, pos):
        """点击指定位置"""
        logger.debug(f"👆 点击位置: {pos}")
        touch(pos)

    @timer_decorator
    def find(
        self,
        text: str,
        timeout: float = 10,
        similarity_threshold: float = 0.7,
        occurrence: int = 1,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
        raise_exception: bool = True,
    ) -> Optional[GameElement]:
        """
        查找单个文本（带等待重试）
        """
        if self.ocr_helper is None:
            msg = "❌ OCR助手未初始化"
            logger.error(msg)
            if raise_exception:
                raise RuntimeError(msg)
            return None

        start_time = time.time()
        region_desc = f" [区域{regions}]" if regions else ""
        logger.info(f"🔍 查找: {text}{region_desc} (等待 {timeout}s)")

        while time.time() - start_time < timeout:
            result = self.ocr_helper.capture_and_find_text(
                text,
                confidence_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
                regions=regions,
            )

            if result and result.get("found"):
                logger.info(f"✅ 找到: {text}{region_desc}")
                return GameElement(result, self)

            time.sleep(0.1)

        msg = f"❌ 超时未找到: {text}{region_desc}"
        logger.warning(msg)
        if raise_exception:
            raise TimeoutError(msg)
        return None

    @timer_decorator
    def find_all(
        self,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> GameElementCollection:
        """
        获取当前屏幕（或区域）内所有的文字元素。
        返回支持链式调用的 GameElementCollection。
        """
        if self.ocr_helper is None:
            logger.error("❌ OCR助手未初始化")
            return GameElementCollection([], self)

        region_desc = f" [区域{regions}]" if regions else ""
        logger.info(f"🔍 扫描所有文字{region_desc}")

        results = self.ocr_helper.capture_and_get_all_texts(
            use_cache=use_cache,
            regions=regions,
        )

        return GameElementCollection(results, self)

    # --- 兼容旧 API / 快捷方式 ---

    def find_text(self, *args, **kwargs) -> Optional[GameElement]:
        """find 的别名，保持兼容性"""
        return self.find(*args, **kwargs)

    def find_all_texts(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """find_all 的原始数据版本兼容"""
        # 注意：这里可能会因为参数变化而破坏一些调用，
        # 但既然要重构为声明式，旧的传参 find_all(text) 应该被废弃。
        # 如果需要保持完全兼容，可以判断第一个参数是否为 str。
        if args and isinstance(args[0], str):
            # 旧版 find_all(text, ...) 逻辑
            text = args[0]
            similarity_threshold = kwargs.get("similarity_threshold", 0.7)
            use_cache = kwargs.get("use_cache", True)
            regions = kwargs.get("regions", None)
            
            logger.info(f"⚠️ 使用旧版 find_all(text='{text}') 兼容模式")
            results = self.ocr_helper.capture_and_find_all_texts(
                text,
                confidence_threshold=similarity_threshold,
                use_cache=use_cache,
                regions=regions,
            )
            return results
        
        # 新版 find_all() 逻辑
        collection = self.find_all(**kwargs)
        return list(collection)

    def text_exists(
        self,
        texts: Union[str, List[str]],
        similarity_threshold: float = 0.7,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> Optional[GameElement]:
        """
        检查文本是否存在
        """
        if self.ocr_helper is None:
            return None

        # 规范化输入
        texts_to_check = [texts] if isinstance(texts, str) else list(texts)
        if not texts_to_check:
            return None

        # 回退到循环检查以保持原来的高性能批量逻辑(虽然底层未完全优化，但逻辑上是找第一个命中的)
        for text in texts_to_check:
            res = self.ocr_helper.capture_and_find_text(
                text,
                confidence_threshold=similarity_threshold,
                use_cache=use_cache,
                regions=regions,
            )
            if res and res.get("found"):
                logger.info(f"✅ text_exists 找到: {text}")
                return GameElement(res, self)

        return None

    def find_text_and_click(self, text: str, **kwargs) -> GameElement:
        """查找并点击"""
        el = self.find(text, **kwargs)
        if el:
            el.click()
        return el

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