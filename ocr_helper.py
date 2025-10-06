"""
OCR Helper Class - 基于PaddleOCR的文字识别和定位工具类
提供统一的接口供外部调用，输入图像文件和要查找的文字，返回文字所在的图片区域
"""

from paddleocr import PaddleOCR
import json
import os
import time
import cv2
from airtest.core.api import *
from airtest.aircv.cal_confidence import cal_ccoeff_confidence
import logging
import coloredlogs


class OCRHelper:
    """OCR辅助工具类，封装PaddleOCR功能"""

    def __init__(
        self,
        output_dir="output",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    ):
        """
        初始化OCR Helper

        Args:
            output_dir (str): 输出目录路径
            use_doc_orientation_classify (bool): 是否使用文档方向分类模型
            use_doc_unwarping (bool): 是否使用文本图像矫正模型
            use_textline_orientation (bool): 是否使用文本行方向分类模型
        """
        self.output_dir = output_dir
        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            lang="ch",
            cpu_threads=16,
        )

        # 创建输出目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # 配置彩色日志（需要先初始化，因为缓存加载时会用到）
        self.logger = logging.getLogger(f"{__name__}.OCRHelper")
        # 防止日志重复：移除已有的 handlers
        self.logger.handlers.clear()
        self.logger.propagate = False

        coloredlogs.install(
            level="DEBUG",
            logger=self.logger,
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
            level_styles={
                "debug": {"color": "cyan"},
                "info": {"color": "blue"},
                "warning": {"color": "yellow"},
                "error": {"color": "red"},
                "critical": {"color": "red", "bold": True},
            },
        )

        # 初始化缓存
        # 格式: [(image_path, json_file_path), ...]
        self.ocr_cache = []
        self.cache_dir = os.path.join(self.output_dir, "cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        # 缓存相似度阈值（95%以上认为是同一张图）
        self.cache_similarity_threshold = 0.95

        # 加载已有的缓存（需要在 logger 初始化之后）
        self._load_existing_cache()

    def _load_existing_cache(self):
        """
        加载缓存目录中已有的缓存文件
        """
        try:
            if not os.path.exists(self.cache_dir):
                return

            # 查找所有缓存文件对
            cache_files = os.listdir(self.cache_dir)
            cache_pairs = {}

            # 将图片和 JSON 文件配对
            for filename in cache_files:
                if filename.startswith("cache_") and filename.endswith(".png"):
                    # 提取缓存 ID
                    cache_id = filename.replace("cache_", "").replace(".png", "")
                    json_filename = f"cache_{cache_id}_res.json"

                    image_path = os.path.join(self.cache_dir, filename)
                    json_path = os.path.join(self.cache_dir, json_filename)

                    # 检查对应的 JSON 文件是否存在
                    if os.path.exists(json_path):
                        cache_pairs[cache_id] = (image_path, json_path)

            # 按 ID 排序并加载到缓存列表
            for cache_id in sorted(
                cache_pairs.keys(), key=lambda x: int(x) if x.isdigit() else 0
            ):
                self.ocr_cache.append(cache_pairs[cache_id])

            if self.ocr_cache:
                self.logger.info(f"💾 加载了 {len(self.ocr_cache)} 个缓存文件")
        except Exception as e:
            self.logger.error(f"加载缓存失败: {e}")

    def _find_similar_cached_image(self, current_image_path):
        """
        查找缓存中是否有相似的图片

        Args:
            current_image_path (str): 当前图片路径

        Returns:
            str: 缓存的 JSON 文件路径，如果没有找到则返回 None
        """
        try:
            current_img = cv2.imread(current_image_path)
            if current_img is None:
                return None

            # 遍历缓存，查找相似图片
            for cached_img_path, cached_json_path in self.ocr_cache:
                if not os.path.exists(cached_img_path) or not os.path.exists(
                    cached_json_path
                ):
                    continue

                cached_img = cv2.imread(cached_img_path)
                if cached_img is None:
                    continue

                # 调整图片尺寸一致以便比较
                if current_img.shape != cached_img.shape:
                    cached_img = cv2.resize(
                        cached_img, (current_img.shape[1], current_img.shape[0])
                    )

                # 计算相似度
                similarity = cal_ccoeff_confidence(current_img, cached_img)

                if similarity >= self.cache_similarity_threshold:
                    self.logger.info(
                        f"💾 找到相似缓存图片 (相似度: {similarity * 100:.1f}%)"
                    )
                    return cached_json_path

            return None
        except Exception as e:
            self.logger.error(f"查找相似缓存图片失败: {e}")
            return None

    def _save_to_cache(self, image_path, json_file):
        """
        保存图片和 OCR 结果到缓存

        Args:
            image_path (str): 图片路径
            json_file (str): JSON 文件路径
        """
        try:
            import shutil

            # 为缓存创建唯一的文件名
            cache_id = len(self.ocr_cache)
            cache_image_name = f"cache_{cache_id}.png"
            cache_json_name = f"cache_{cache_id}_res.json"

            cache_image_path = os.path.join(self.cache_dir, cache_image_name)
            cache_json_path = os.path.join(self.cache_dir, cache_json_name)

            # 复制图片到缓存目录
            shutil.copy2(image_path, cache_image_path)

            # 复制 JSON 到缓存目录
            if os.path.exists(json_file):
                shutil.copy2(json_file, cache_json_path)
                # 保存缓存记录
                self.ocr_cache.append((cache_image_path, cache_json_path))
                self.logger.debug(
                    f"💾 缓存已保存 (图片数: {len(self.ocr_cache)}, JSON: {cache_json_name})"
                )
            else:
                self.logger.error(f"JSON 文件不存在，无法缓存: {json_file}")
        except Exception as e:
            self.logger.error(f"保存缓存失败: {e}")

    def _predict_with_timing(self, image_path):
        """
        执行 OCR 识别并记录耗时

        Args:
            image_path (str): 图像文件路径

        Returns:
            OCR 识别结果
        """
        start_time = time.time()
        result = self.ocr.predict(image_path)
        elapsed_time = time.time() - start_time

        filename = os.path.basename(image_path)
        self.logger.info(f"⏱️ OCR识别耗时: {elapsed_time:.3f}秒 (文件: {filename})")

        return result

    def _get_or_create_ocr_result(self, image_path, use_cache=True):
        """
        获取或创建 OCR 识别结果（带缓存）

        Args:
            image_path (str): 图像文件路径
            use_cache (bool): 是否使用缓存，默认为 True

        Returns:
            str: JSON 文件路径
        """
        # 如果启用缓存，检查缓存中是否有相似图片
        if use_cache:
            cached_json = self._find_similar_cached_image(image_path)
            if cached_json:
                return cached_json

        # 缓存未命中或禁用缓存，执行 OCR 识别
        result = self._predict_with_timing(image_path)

        if result and len(result) > 0:
            # 先保存到 output 目录（标准流程）
            for res in result:
                res.save_to_json(self.output_dir)

            # 获取 JSON 文件路径
            json_file = os.path.join(
                self.output_dir,
                os.path.basename(image_path).replace(".png", "_res.json"),
            )

            # 如果启用缓存，同时保存到缓存
            if use_cache and os.path.exists(json_file):
                self._save_to_cache(image_path, json_file)

            return json_file

        return None

    def find_text_in_image(
        self,
        image_path,
        target_text,
        confidence_threshold=0.5,
        occurrence=1,
        use_cache=True,
    ):
        """
        在指定图像中查找目标文字的位置

        Args:
            image_path (str): 图像文件路径
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True

        Returns:
            dict: 包含以下信息的字典
                - found (bool): 是否找到文字
                - center (tuple): 文字中心坐标 (x, y)，未找到时为None
                - text (str): 实际识别到的文字，未找到时为None
                - confidence (float): 置信度，未找到时为None
                - bbox (list): 文字边界框坐标，未找到时为None
                - total_matches (int): 总共找到的匹配数量
                - selected_index (int): 实际选择的索引 (1-based)
        """
        try:
            # 获取或创建 OCR 结果（带缓存）
            json_file = self._get_or_create_ocr_result(image_path, use_cache=use_cache)

            if not json_file:
                self.logger.warning(f"OCR识别结果为空: {image_path}")
                return {
                    "found": False,
                    "center": None,
                    "text": None,
                    "confidence": None,
                    "bbox": None,
                    "total_matches": 0,
                    "selected_index": 0,
                }

            # 从 JSON 中查找目标文字
            return self._find_text_in_json(
                json_file, target_text, confidence_threshold, occurrence
            )

        except Exception as e:
            self.logger.error(f"图像OCR识别出错: {e}")
            return {
                "found": False,
                "center": None,
                "text": None,
                "confidence": None,
                "bbox": None,
                "total_matches": 0,
                "selected_index": 0,
            }

    def capture_and_find_text(
        self,
        target_text,
        confidence_threshold=0.5,
        screenshot_path="/tmp/screenshot.png",
        occurrence=1,
        use_cache=True,
    ):
        """
        截图并查找目标文字的位置

        Args:
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            screenshot_path (str): 截图保存路径
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True

        Returns:
            dict: 包含查找结果的字典，格式同find_text_in_image
        """
        try:
            # 截图
            snapshot(filename=screenshot_path)
            self.logger.info(f"截图保存到: {screenshot_path}")

            # 在截图中查找文字
            return self.find_text_in_image(
                screenshot_path,
                target_text,
                confidence_threshold,
                occurrence,
                use_cache,
            )

        except Exception as e:
            self.logger.error(f"截图和识别过程出错: {e}")
            return {
                "found": False,
                "center": None,
                "text": None,
                "confidence": None,
                "bbox": None,
                "total_matches": 0,
                "selected_index": 0,
            }

    def find_and_click_text(
        self,
        target_text,
        confidence_threshold=0.5,
        screenshot_path="/tmp/screenshot.png",
        occurrence=1,
        use_cache=True,
    ):
        """
        截图、查找文字并点击其中心点

        Args:
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            screenshot_path (str): 截图保存路径
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True

        Returns:
            bool: 是否成功找到并点击
        """
        result = self.capture_and_find_text(
            target_text, confidence_threshold, screenshot_path, occurrence, use_cache
        )

        if result["found"]:
            center = result["center"]
            self.logger.info(f"点击位置: {center}")
            touch(center)
            return True
        else:
            self.logger.warning(f"无法点击，未找到文字: '{target_text}'")
            return False

    def _find_text_in_json(
        self, json_file_path, target_text, confidence_threshold=0.5, occurrence=1
    ):
        """
        从PaddleOCR输出的JSON文件中查找目标文字

        Args:
            json_file_path (str): JSON文件路径
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            occurrence (int): 指定返回第几个出现的文字 (1-based)，默认为1

        Returns:
            dict: 查找结果字典
        """
        try:
            # 读取JSON文件
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 获取识别的文字列表和对应的坐标框
            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])
            dt_polys = data.get("dt_polys", [])  # 检测框坐标

            self.logger.info(f"在JSON中查找文字: '{target_text}' (第{occurrence}个)")
            self.logger.info(f"总共识别到 {len(rec_texts)} 个文字")

            # 收集所有匹配的文字
            matches = []
            for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                self.logger.debug(f"  {i + 1:2d}. '{text}' (置信度: {score:.3f})")

                # 检查置信度和文字匹配（识别出的文字包含目标文字）
                if score >= confidence_threshold and target_text in text:
                    # 获取对应的坐标框
                    if i < len(dt_polys):
                        poly = dt_polys[i]

                        # 计算中心点坐标
                        # poly 格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        x_coords = [point[0] for point in poly]
                        y_coords = [point[1] for point in poly]
                        center_x = int(sum(x_coords) / len(x_coords))
                        center_y = int(sum(y_coords) / len(y_coords))

                        matches.append(
                            {
                                "center": (center_x, center_y),
                                "text": text,
                                "confidence": score,
                                "bbox": poly,
                                "index": len(matches) + 1,
                            }
                        )

            total_matches = len(matches)
            self.logger.info(f"找到 {total_matches} 个匹配的文字")

            if total_matches == 0:
                self.logger.warning(f"未找到匹配的文字: '{target_text}'")
                return {
                    "found": False,
                    "center": None,
                    "text": None,
                    "confidence": None,
                    "bbox": None,
                    "total_matches": 0,
                    "selected_index": 0,
                }

            # 显示所有匹配的文字
            for i, match in enumerate(matches, 1):
                self.logger.info(
                    f"  匹配 {i}: '{match['text']}' (置信度: {match['confidence']:.3f}) 位置: {match['center']}"
                )

            # 选择指定的匹配项
            if occurrence > total_matches:
                self.logger.warning(
                    f"请求第{occurrence}个匹配，但只找到{total_matches}个，使用最后一个"
                )
                selected_match = matches[-1]
                selected_index = total_matches
            else:
                selected_match = matches[occurrence - 1]
                selected_index = occurrence

            self.logger.info(
                f"选择第{selected_index}个匹配: '{selected_match['text']}'"
            )
            self.logger.info(f"坐标框: {selected_match['bbox']}")
            self.logger.info(f"中心点: {selected_match['center']}")

            return {
                "found": True,
                "center": selected_match["center"],
                "text": selected_match["text"],
                "confidence": selected_match["confidence"],
                "bbox": selected_match["bbox"],
                "total_matches": total_matches,
                "selected_index": selected_index,
            }

        except FileNotFoundError:
            self.logger.error(f"JSON文件不存在: {json_file_path}")
            return {
                "found": False,
                "center": None,
                "text": None,
                "confidence": None,
                "bbox": None,
                "total_matches": 0,
                "selected_index": 0,
            }
        except json.JSONDecodeError:
            self.logger.error(f"JSON文件格式错误: {json_file_path}")
            return {
                "found": False,
                "center": None,
                "text": None,
                "confidence": None,
                "bbox": None,
                "total_matches": 0,
                "selected_index": 0,
            }
        except Exception as e:
            self.logger.error(f"处理JSON文件时出错: {e}")
            return {
                "found": False,
                "center": None,
                "text": None,
                "confidence": None,
                "bbox": None,
                "total_matches": 0,
                "selected_index": 0,
            }

    def find_all_matching_texts(
        self, image_path, target_text, confidence_threshold=0.5
    ):
        """
        查找图像中所有匹配的文字

        Args:
            image_path (str): 图像文件路径
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)

        Returns:
            list: 包含所有匹配文字信息的列表，每个元素包含center, text, confidence, bbox
        """
        try:
            # OCR 识别
            result = self._predict_with_timing(image_path)

            if not result or len(result) == 0:
                self.logger.warning(f"OCR识别结果为空: {image_path}")
                return []

            # 保存识别结果到JSON
            for res in result:
                res.save_to_json(self.output_dir)

            # 从结果中查找所有匹配的文字
            json_file = os.path.join(
                self.output_dir,
                os.path.basename(image_path).replace(".png", "_res.json"),
            )
            return self._find_all_matching_texts_in_json(
                json_file, target_text, confidence_threshold
            )

        except Exception as e:
            self.logger.error(f"查找所有匹配文字时出错: {e}")
            return []

    def _find_all_matching_texts_in_json(
        self, json_file_path, target_text, confidence_threshold=0.5
    ):
        """
        从JSON文件中查找所有匹配的文字

        Args:
            json_file_path (str): JSON文件路径
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)

        Returns:
            list: 所有匹配的文字信息列表
        """
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])
            dt_polys = data.get("dt_polys", [])

            matches = []
            for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                # 检查置信度和文字匹配（识别出的文字包含目标文字）
                if score >= confidence_threshold and target_text in text:
                    if i < len(dt_polys):
                        poly = dt_polys[i]
                        x_coords = [point[0] for point in poly]
                        y_coords = [point[1] for point in poly]
                        center_x = int(sum(x_coords) / len(x_coords))
                        center_y = int(sum(y_coords) / len(y_coords))

                        matches.append(
                            {
                                "center": (center_x, center_y),
                                "text": text,
                                "confidence": score,
                                "bbox": poly,
                                "index": len(matches) + 1,
                            }
                        )

            return matches

        except Exception as e:
            self.logger.error(f"处理JSON文件时出错: {e}")
            return []

    def get_all_texts_from_image(self, image_path):
        """
        获取图像中所有识别到的文字信息

        Args:
            image_path (str): 图像文件路径

        Returns:
            list: 包含所有文字信息的列表，每个元素为字典包含text, confidence, center, bbox
        """
        try:
            # OCR 识别
            result = self._predict_with_timing(image_path)

            if not result or len(result) == 0:
                self.logger.warning(f"OCR识别结果为空: {image_path}")
                return []

            # 保存识别结果到JSON
            for res in result:
                res.save_to_json(self.output_dir)

            # 从JSON文件读取所有文字
            json_file = os.path.join(
                self.output_dir,
                os.path.basename(image_path).replace(".png", "_res.json"),
            )
            return self._get_all_texts_from_json(json_file)

        except Exception as e:
            self.logger.error(f"获取图像文字信息出错: {e}")
            return []

    def _get_all_texts_from_json(self, json_file_path):
        """
        从JSON文件中获取所有文字信息

        Args:
            json_file_path (str): JSON文件路径

        Returns:
            list: 所有文字信息列表
        """
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])
            dt_polys = data.get("dt_polys", [])

            texts_info = []

            for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                if i < len(dt_polys):
                    poly = dt_polys[i]
                    x_coords = [point[0] for point in poly]
                    y_coords = [point[1] for point in poly]
                    center_x = int(sum(x_coords) / len(x_coords))
                    center_y = int(sum(y_coords) / len(y_coords))

                    texts_info.append(
                        {
                            "text": text,
                            "confidence": score,
                            "center": (center_x, center_y),
                            "bbox": poly,
                        }
                    )

            return texts_info

        except Exception as e:
            self.logger.error(f"读取JSON文件出错: {e}")
            return []
