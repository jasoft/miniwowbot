# -*- encoding=utf8 -*-
"""
游戏操作动作模块
封装了基于 OCR 的查找、点击等操作
"""

import logging
import os
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Optional, List, Union, Dict, Any

from airtest.core.api import snapshot, touch, sleep as airtest_sleep

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

    @timer_decorator
    def find_text(
        self,
        text: str,
        timeout: float = 10,
        similarity_threshold: float = 0.7,
        occurrence: int = 1,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
        raise_exception: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        使用 OCRHelper 查找文本

        Args:
            text: 要查找的文本
            timeout: 超时时间（秒）
            similarity_threshold: 相似度阈值
            occurrence: 指定第几个出现的文字 (1-based)，默认为1
            use_cache: 是否使用缓存
            regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
            raise_exception: 超时后是否抛出异常，默认True

        Returns:
            OCR识别结果字典，包含 center, text, confidence 等信息

        Raises:
            TimeoutError: 如果超时且 raise_exception=True
            RuntimeError: 如果 OCRHelper 未初始化
        """
        if self.ocr_helper is None:
            error_msg = "❌ OCR助手未初始化，无法查找文本"
            logger.error(error_msg)
            if raise_exception:
                raise RuntimeError(error_msg)
            return None

        region_desc = f" [区域{regions}]" if regions else ""

        if occurrence > 1:
            logger.info(f"🔍 查找文本: {text} (第{occurrence}个){region_desc}")
        else:
            logger.info(f"🔍 查找文本: {text}{region_desc}")
        
        start_time = time.time()

        while time.time() - start_time < timeout:
            # 使用 OCRHelper 查找文本 (OCRHelper 内部已处理文本纠正)
            result = self.ocr_helper.capture_and_find_text(
                text,
                confidence_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
                regions=regions,
            )

            if result and result.get("found"):
                if occurrence > 1:
                    logger.info(f"✅ 找到文本: {text} (第{occurrence}个){region_desc}")
                else:
                    logger.info(f"✅ 找到文本: {text}{region_desc}")
                return result

            # 短暂休眠避免CPU占用过高
            time.sleep(0.1)

        # 超时处理
        error_msg = f"❌ 超时未找到文本: {text}"
        if occurrence > 1:
            error_msg = f"❌ 超时未找到文本: {text} (第{occurrence}个)"

        logger.warning(error_msg)

        if raise_exception:
            raise TimeoutError(error_msg)

        return None

    @timer_decorator
    def text_exists(
        self,
        texts: Union[str, List[str]],
        similarity_threshold: float = 0.7,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        检查当前界面上给定文本列表中的任意一个是否存在。
        """
        if self.ocr_helper is None:
            logger.error("❌ OCR助手未初始化，无法判断文本是否存在")
            return None

        # 规范化输入为列表
        if isinstance(texts, str):
            texts_to_check = [texts]
        else:
            try:
                texts_to_check = list(texts) if texts is not None else []
            except TypeError:
                texts_to_check = [str(texts)]

        if not texts_to_check:
            logger.warning("⚠️ text_exists 收到空的文本列表，直接返回 None")
            return None

        region_desc = f" [区域{regions}]" if regions else ""
        logger.debug(f"🔍 text_exists 检查文本列表: {texts_to_check}{region_desc}")

        # 优先使用 OCRHelper 的批量 OCR 能力
        has_bulk_ocr = hasattr(self.ocr_helper, "_get_or_create_ocr_result") and hasattr(
            self.ocr_helper, "_get_all_texts_from_json"
        )

        screenshot_path: Optional[str] = None
        if has_bulk_ocr:
            try:
                # 1) 截图一次
                base_dir = getattr(self.ocr_helper, "temp_dir", os.getcwd())
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = str(uuid.uuid4())[:8]
                screenshot_path = os.path.join(base_dir, f"text_exists_{timestamp}_{unique_id}.png")

                snapshot(filename=screenshot_path)
                logger.debug(f"📸 text_exists 截图保存到: {screenshot_path}")

                # 2) 基于缓存系统获取/创建 OCR JSON 结果
                json_file = self.ocr_helper._get_or_create_ocr_result(
                    screenshot_path,
                    use_cache=use_cache,
                    regions=regions,
                )

                if not json_file:
                    logger.info(
                        f"🔍 text_exists 未获取到 OCR JSON 结果, 文本: {texts_to_check}{region_desc}"
                    )
                else:
                    # 3) 从 JSON 中加载所有识别到的文字信息
                    all_texts = self.ocr_helper._get_all_texts_from_json(json_file)
                    if not all_texts:
                        logger.info(f"🔍 text_exists OCR 结果为空: {texts_to_check}{region_desc}")
                    else:
                        # 4) 在内存中的 OCR 结果里，按 texts_to_check 的顺序查找第一个命中的文本
                        for candidate in texts_to_check:
                            for info in all_texts:
                                text_val = info.get("text") or ""
                                conf = float(info.get("confidence") or 0.0)
                                center = info.get("center")

                                # 根据 regions 做一次坐标过滤（如果可用）
                                in_region = True
                                if regions and center:
                                    try:
                                        import cv2
                                        img = cv2.imread(screenshot_path)
                                        if img is not None and hasattr(
                                            self.ocr_helper, "_get_region_bounds"
                                        ):
                                            height, width = img.shape[:2]
                                            x, y, w, h = self.ocr_helper._get_region_bounds(
                                                (height, width), regions
                                            )
                                            cx, cy = center
                                            in_region = x <= cx <= x + w and y <= cy <= y + h
                                    except Exception as region_err:
                                        logger.warning(
                                            f"text_exists 区域过滤出错, 将退回全屏匹配: {region_err}"
                                        )

                                if conf >= similarity_threshold and candidate in text_val and in_region:
                                    logger.info(
                                        f"✅ text_exists 找到文本: {candidate}{region_desc} at {center}"
                                    )
                                    return {
                                        "found": True,
                                        "center": center,
                                        "text": text_val,
                                        "confidence": conf,
                                        "bbox": info.get("bbox"),
                                        "total_matches": 1,
                                        "selected_index": 1,
                                    }

            except Exception as e:
                logger.error(f"text_exists 使用单次 OCR 批量匹配时出错, 将回退到逐个查询模式: {e}")
            finally:
                if screenshot_path and os.path.exists(screenshot_path):
                    try:
                        os.remove(screenshot_path)
                    except Exception as cleanup_error:
                        logger.warning(f"text_exists 删除临时截图失败: {cleanup_error}")

        # 回退方案：逐个调用 capture_and_find_text
        for candidate in texts_to_check:
            result = self.ocr_helper.capture_and_find_text(
                candidate,
                confidence_threshold=similarity_threshold,
                occurrence=1,
                use_cache=use_cache,
                regions=regions,
            )

            if result and result.get("found"):
                center = result.get("center")
                logger.info(f"✅ text_exists 找到文本: {candidate}{region_desc} at {center}")
                return result

        logger.info(f"🔍 text_exists 未找到任何目标文本: {texts_to_check}{region_desc}")
        return None

    def find_text_and_click(
        self,
        text: str,
        timeout: float = 10,
        similarity_threshold: float = 0.7,
        occurrence: int = 1,
        use_cache: bool = True,
        regions: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        使用 OCRHelper 查找文本并点击
        """
        try:
            # 调用 find_text 查找文本（抛出异常）
            result = self.find_text(
                text=text,
                timeout=timeout,
                similarity_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
                regions=regions,
                raise_exception=True,
            )

            # 点击找到的位置
            assert result
            center = result["center"]
            touch(center)

            region_desc = f" [区域{regions}]" if regions else ""
            logger.info(f"✅ 成功点击: {text}{region_desc} at {center}")
            self.sleep(self.click_interval)  # 每个点击后面停顿一下等待界面刷新
            return result

        except Exception as e:
            logger.error(f"❌ 查找并点击文本失败: {text} - {e}")
            raise

        def find_text_and_click_safe(

            self,

            text: str,

            timeout: float = 10,

            similarity_threshold: float = 0.7,

            occurrence: int = 1,

            use_cache: bool = True,

            regions: Optional[List[int]] = None,

            default_return: Any = False,

        ) -> Any:

            """

            安全版本的 find_text_and_click，不会抛出异常

            """

            try:

                return self.find_text_and_click(

                    text=text,

                    timeout=timeout,

                    similarity_threshold=similarity_threshold,

                    occurrence=occurrence,

                    use_cache=use_cache,

                    regions=regions,

                )

            except Exception as e:

                region_desc = f" [区域{regions}]" if regions else ""

                logger.debug(f"⚠️ 安全查找并点击失败: {text}{region_desc} - {e}")

                return default_return

    

        @timer_decorator

        def find_all_texts(

            self,

            text: str,

            similarity_threshold: float = 0.7,

            use_cache: bool = True,

            regions: Optional[List[int]] = None,

        ) -> List[Dict[str, Any]]:

            """

            查找当前界面上所有匹配的文本数据

    

            Args:

                text: 要查找的文本

                similarity_threshold: 相似度阈值

                use_cache: 是否使用缓存

                regions: 要搜索的区域列表

    

            Returns:

                list: 包含所有找到的文字数据的列表

            """

            if self.ocr_helper is None:

                logger.error("❌ OCR助手未初始化，无法查找文本")

                return []

    

            region_desc = f" [区域{regions}]" if regions else ""

            logger.info(f"🔍 查找所有文本: {text}{region_desc}")

    

            return self.ocr_helper.capture_and_find_all_texts(

                text,

                confidence_threshold=similarity_threshold,

                use_cache=use_cache,

                regions=regions,

            )

    