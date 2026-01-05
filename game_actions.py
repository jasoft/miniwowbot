# -*- encoding=utf8 -*-
"""
游戏操作动作模块
封装了基于 OCR 的查找、点击等操作，提供声明式 API
所有查找逻辑均基于 find_all() 的集合操作实现
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from airtest.core.api import sleep as airtest_sleep
from airtest.core.api import touch

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


class GameElement(dict):
    """
    表示一个游戏元素（基于 OCR 识别结果）
    """

    def __init__(self, data: Dict[str, Any], action_context: "GameActions"):
        super().__init__(data or {})
        self.action_context = action_context
        # 兼容旧代码，确保 result.get("found") 返回 True
        self["found"] = True

    def __bool__(self):
        """
        明确对象的布尔值行为
        普通 GameElement 默认为 True (因为 found=True)
        """
        return self.get("found", False)

    @staticmethod
    def empty(action_context: "GameActions") -> "GameElement":
        """工厂方法：创建一个空的 GameElement (Null Object)"""
        return NullGameElement(action_context)

    @property
    def center(self) -> Tuple[int, int]:
        if self.get("center"):
            return tuple(self["center"])
        return (0, 0)

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


class NullGameElement(GameElement):
    """
    空的游戏元素 (Null Object Pattern)
    用于替代 None，支持链式调用但不执行实际操作
    """

    def __init__(self, action_context: "GameActions"):
        super().__init__({}, action_context)
        self["found"] = False

    def __bool__(self):
        return False

    def __repr__(self):
        return "NullGameElement()"

    @property
    def center(self) -> Tuple[int, int]:
        return (0, 0)

    def click(self) -> "GameElement":
        logger.debug("👻 NullGameElement click (ignored)")
        return self

    def offset_click(self, x: int = 0, y: int = 0) -> "GameElement":
        logger.debug("👻 NullGameElement offset_click (ignored)")
        return self

    def sleep(self, seconds: float) -> "GameElement":
        logger.debug(f"👻 NullGameElement sleep {seconds}s (ignored)")
        return self


class GameElementCollection(list):
    """
    游戏元素集合，支持链式操作
    """

    def __init__(self, elements: List[Dict[str, Any]], action_context: "GameActions"):
        # 将原始字典转换为 GameElement 对象
        super().__init__([GameElement(e, action_context) for e in elements])
        self.action_context = action_context

    def filter(self, predicate: Callable[[GameElement], bool]) -> "GameElementCollection":
        """通用过滤"""
        return GameElementCollection([e for e in self if predicate(e)], self.action_context)

    def contains(self, text: str) -> "GameElementCollection":
        """保留文本包含指定内容的元素"""
        return self.filter(lambda e: text in (e.text or ""))

    def equals(self, text: str) -> "GameElementCollection":
        """保留文本完全匹配的元素"""
        return self.filter(lambda e: e.text == text)

    def min_confidence(self, threshold: float) -> "GameElementCollection":
        """保留置信度大于阈值的元素"""
        return self.filter(lambda e: e.confidence >= threshold)

    def first(self) -> GameElement:
        """获取第一个元素"""
        return self[0] if self else GameElement.empty(self.action_context)

    def last(self) -> GameElement:
        """获取最后一个元素"""
        return self[-1] if self else GameElement.empty(self.action_context)

    def get(self, index: int) -> GameElement:
        """
        获取指定索引的元素 (0-based)
# 兼容性修改：如果 index 超过列表长度，返回最后一个元素 (Legacy vibe_ocr behavior)
ocr_helper: "vibe_ocr.OCRHelper" 实例
        """
        if not self:
            return GameElement.empty(self.action_context)

        if index >= len(self):
            return self[-1]

        if 0 <= index < len(self):
            return self[index]

        return GameElement.empty(self.action_context)

    def map(self, func: Callable[[GameElement], Any]) -> List[Any]:
        """对每个元素应用函数"""
        return [func(e) for e in self]

    def each(self, func: Callable[[GameElement], None]) -> "GameElementCollection":
        """执行副作用操作"""
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

    def size(self) -> int:
        return len(self)


class GameActions:
    """
    封装游戏内的查找和操作逻辑
    所有高级查找功能均基于 find_all() 实现
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
    def find_all(
        self,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> GameElementCollection:
        """
        声明式 API 入口：获取当前屏幕所有文字元素
        这是唯一直接调用 vibe_ocr.OCRHelper 截图识别的函数
        """
        if self.ocr_helper is None:
            logger.error("❌ OCR助手未初始化")
            return GameElementCollection([], self)

        results = self.ocr_helper.capture_and_get_all_texts(
            use_cache=use_cache,
            regions=regions,
        )

        logger.debug(f"📊 find_all 识别到 {len(results)} 个文字元素")
        # log all texts and positions
        # for idx, result in enumerate(results):
        #     logger.debug(f"  [{idx}] {result['text']} at {result['center']}")

        return GameElementCollection(results, self)

    def find(
        self,
        text: str,
        timeout: float = 1,
        similarity_threshold: float = 0.7,
        occurrence: int = 1,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
        raise_exception: bool = False,
    ) -> GameElement:
        """
        基于 find_all 实现的 find
        """
        start_time = time.time()
        region_desc = f" [区域{regions}]" if regions else ""
        logger.debug(f"🔍 查找: {text}{region_desc} (等待 {timeout}s)")

        first_attempt = True
        while first_attempt or (time.time() - start_time < timeout):
            first_attempt = False
            # 使用集合操作查找匹配项
            el = (
                self.find_all(use_cache=use_cache, regions=regions)
                .contains(text)
                .min_confidence(similarity_threshold)
                .get(occurrence - 1)
            )

            if el:
                logger.info(f"✅ 找到: {text}{region_desc} at {el.center}")
                return el

            if time.time() - start_time >= timeout:
                break
            time.sleep(0.1)

        msg = f"❌ 超时未找到: {text}{region_desc}"
        logger.debug(msg)
        if raise_exception:
            raise TimeoutError(msg)
        return GameElement.empty(self)

    def text_exists(
        self,
        texts: Union[str, List[str]],
        similarity_threshold: float = 0.7,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> GameElement:
        """
        基于 find_all 实现的 text_exists
        """
        if self.ocr_helper is None:
            return GameElement.empty(self)

        # 规范化输入
        texts_to_check = [texts] if isinstance(texts, str) else list(texts)
        if not texts_to_check:
            return GameElement.empty(self)

        # 获取一次全集，然后在内存中匹配
        collection = self.find_all(use_cache=use_cache, regions=regions).min_confidence(
            similarity_threshold
        )

        for text in texts_to_check:
            el = collection.contains(text).first()
            if el:
                logger.info(f"✅ text_exists 找到: {text} at {el.center}")
                return el

        return GameElement.empty(self)

    # --- 快捷方法 ---

    def find_text(self, *args, **kwargs) -> GameElement:
        """find 的别名"""
        return self.find(*args, **kwargs)

    def find_all_texts(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """向后兼容的原始列表返回版本"""
        # 如果调用者传递了 text 参数（旧版 API），特殊处理
        if args and isinstance(args[0], str):
            text = args[0]
            kwargs.pop("similarity_threshold", None)  # 移除无关参数
            collection = self.find_all(**kwargs).contains(text)
            return list(collection)

        return list(self.find_all(**kwargs))

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
