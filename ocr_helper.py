"""
OCR Helper Class - 基于PaddleOCR的文字识别和定位工具类
提供统一的接口供外部调用，输入图像文件和要查找的文字，返回文字所在的图片区域
支持区域分割功能，可以指定只识别屏幕的特定区域，大大提升识别速度
"""

from paddleocr import PaddleOCR
import json
import os
import time
import cv2
from airtest.core.api import snapshot, touch
from airtest.aircv.cal_confidence import cal_ccoeff_confidence
import logging
import coloredlogs
from typing import List, Tuple, Optional, Dict, Any


class OCRHelper:
    """OCR辅助工具类，封装PaddleOCR功能"""

    def __init__(
        self,
        output_dir="output",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        resize_image=True,
        max_width=960,
    ):
        """
        初始化OCR Helper

        Args:
            output_dir (str): 输出目录路径
            use_doc_orientation_classify (bool): 是否使用文档方向分类模型
            use_doc_unwarping (bool): 是否使用文本图像矫正模型
            use_textline_orientation (bool): 是否使用文本行方向分类模型
            resize_image (bool): 是否自动缩小图片以提升速度
            max_width (int): 图片最大宽度，默认960（建议在640-960之间）
        """
        self.output_dir = output_dir
        self.resize_image = resize_image
        self.max_width = max_width

        self.ocr = PaddleOCR(
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            cpu_threads=4,  # M4 效率核心，减少线程竞争
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
            level="INFO",
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

    def _merge_regions(self, regions: List[int]) -> Tuple[int, int, int, int]:
        """
        合并多个区域为一个连续的矩形区域

        Args:
            regions: 要合并的区域列表（1-9）
                    1 2 3
                    4 5 6
                    7 8 9

        Returns:
            合并后的边界 (min_row, max_row, min_col, max_col)，都是0-based索引
        """
        if not regions:
            return (0, 2, 0, 2)  # 整个图像

        # 将区域ID转换为行列索引
        rows = []
        cols = []
        for region_id in regions:
            if not 1 <= region_id <= 9:
                self.logger.warning(f"无效的区域ID: {region_id}，跳过")
                continue
            row = (region_id - 1) // 3
            col = (region_id - 1) % 3
            rows.append(row)
            cols.append(col)

        if not rows:
            return (0, 2, 0, 2)

        # 计算包含所有区域的最小矩形
        min_row = min(rows)
        max_row = max(rows)
        min_col = min(cols)
        max_col = max(cols)

        return (min_row, max_row, min_col, max_col)

    def _get_region_bounds(
        self, image_shape: Tuple[int, int], regions: Optional[List[int]] = None
    ) -> Tuple[int, int, int, int]:
        """
        将图像分成3x3网格，返回合并后的区域边界

        Args:
            image_shape: 图像形状 (height, width)
            regions: 要提取的区域列表，使用数字1-9表示（从左到右，从上到下）
                    1 2 3
                    4 5 6
                    7 8 9
                    如果为None，返回整个图像
                    多个区域会被合并成一个连续的矩形

        Returns:
            区域边界 (x, y, w, h)
        """
        height, width = image_shape

        if regions is None:
            # 返回整个图像
            return (0, 0, width, height)

        # 合并区域
        min_row, max_row, min_col, max_col = self._merge_regions(regions)

        # 计算每个格子的大小
        cell_height = height // 3
        cell_width = width // 3

        # 计算合并后的边界
        x = min_col * cell_width
        y = min_row * cell_height
        w = (max_col - min_col + 1) * cell_width
        h = (max_row - min_row + 1) * cell_height

        # 处理边界情况，确保覆盖到图像边缘
        if max_col == 2:  # 包含最右列
            w = width - x
        if max_row == 2:  # 包含最下行
            h = height - y

        return (x, y, w, h)

    def _extract_region(
        self,
        image: Any,
        regions: Optional[List[int]] = None,
        debug_save_path: Optional[str] = None,
    ) -> Tuple[Any, Tuple[int, int]]:
        """
        从图像中提取指定的区域（合并后的单个区域）

        Args:
            image: OpenCV图像对象
            regions: 要提取的区域列表（1-9），会被合并成一个连续的矩形
            debug_save_path: 调试用，保存区域截图的路径

        Returns:
            (region_image, (offset_x, offset_y))
        """
        if image is None:
            return None, (0, 0)

        height, width = image.shape[:2]
        x, y, w, h = self._get_region_bounds((height, width), regions)

        region_img = image[y : y + h, x : x + w]

        # 调试：保存区域截图
        if debug_save_path:
            import cv2

            cv2.imwrite(debug_save_path, region_img)
            self.logger.info(f"🔍 调试：区域截图已保存到 {debug_save_path}")
            self.logger.info(f"   区域范围: x={x}, y={y}, w={w}, h={h}")
            self.logger.info(f"   原图尺寸: {width}x{height}")

        return region_img, (x, y)

    def _adjust_coordinates_to_full_image(
        self, bbox: List[List[int]], offset: Tuple[int, int]
    ) -> List[List[int]]:
        """
        将区域内的坐标调整为原图中的坐标

        Args:
            bbox: 区域内的边界框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            offset: 区域在原图中的偏移量 (offset_x, offset_y)

        Returns:
            调整后的边界框坐标
        """
        offset_x, offset_y = offset
        adjusted_bbox = []
        for point in bbox:
            adjusted_bbox.append([point[0] + offset_x, point[1] + offset_y])
        return adjusted_bbox

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

    def _resize_image_for_ocr(self, image_path):
        """
        调整图片大小以加速 OCR 识别

        Args:
            image_path (str): 原始图片路径

        Returns:
            str: 调整后的图片路径（如果需要调整），否则返回原路径
        """
        if not self.resize_image:
            return image_path

        try:
            img = cv2.imread(image_path)
            if img is None:
                return image_path

            height, width = img.shape[:2]

            # 如果图片宽度大于最大宽度，进行缩放
            if width > self.max_width:
                scale = self.max_width / width
                new_width = self.max_width
                new_height = int(height * scale)

                # 缩小图片
                resized_img = cv2.resize(
                    img, (new_width, new_height), interpolation=cv2.INTER_AREA
                )

                # 保存到临时文件
                temp_path = image_path.replace(".png", "_resized.png")
                cv2.imwrite(temp_path, resized_img)

                self.logger.debug(
                    f"🔧 图片已缩小: {width}x{height} -> {new_width}x{new_height}"
                )
                return temp_path

            return image_path
        except Exception as e:
            self.logger.warning(f"图片缩放失败: {e}，使用原图")
            return image_path

    def _predict_with_timing(self, image_path):
        """
        执行 OCR 识别并记录耗时

        Args:
            image_path (str): 图像文件路径

        Returns:
            OCR 识别结果
        """
        # 预处理：缩小图片
        processed_image_path = self._resize_image_for_ocr(image_path)

        start_time = time.time()
        result = self.ocr.predict(processed_image_path)
        elapsed_time = time.time() - start_time

        filename = os.path.basename(image_path)
        self.logger.info(f"⏱️ OCR识别耗时: {elapsed_time:.3f}秒 (文件: {filename})")

        # 清理临时文件
        if processed_image_path != image_path and os.path.exists(processed_image_path):
            try:
                os.remove(processed_image_path)
            except Exception:
                pass

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
        regions: Optional[List[int]] = None,
        debug_save_path: Optional[str] = None,
    ):
        """
        在指定图像中查找目标文字的位置

        Args:
            image_path (str): 图像文件路径
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True
            regions (List[int], optional): 要搜索的区域列表（1-9），如果为None则搜索整个图像
                                          区域编号如下：
                                          1 2 3
                                          4 5 6
                                          7 8 9
            debug_save_path (str, optional): 调试用，保存区域截图的路径

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
            # 如果指定了区域，使用区域搜索
            if regions is not None:
                return self._find_text_in_regions(
                    image_path,
                    target_text,
                    confidence_threshold,
                    occurrence,
                    regions,
                    debug_save_path,
                )

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

    def _find_text_in_regions(
        self,
        image_path: str,
        target_text: str,
        confidence_threshold: float,
        occurrence: int,
        regions: List[int],
        debug_save_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        在指定区域中查找文字（内部方法）

        Args:
            image_path: 图像文件路径
            target_text: 要查找的目标文字
            confidence_threshold: 置信度阈值
            occurrence: 指定第几个出现的文字
            regions: 要搜索的区域列表（会被合并成一个连续的矩形）
            debug_save_path: 调试用，保存区域截图的路径

        Returns:
            查找结果字典
        """
        try:
            # 读取图像
            image = cv2.imread(image_path)
            if image is None:
                self.logger.error(f"无法读取图像: {image_path}")
                return self._empty_result()

            # 提取合并后的区域
            region_img, offset = self._extract_region(image, regions, debug_save_path)
            if region_img is None:
                self.logger.warning("未能提取区域")
                return self._empty_result()

            # 显示区域信息
            region_desc = self._get_region_description(regions)
            self.logger.info(f"🔍 在{region_desc}搜索文字: '{target_text}'")

            # 对区域进行OCR识别
            start_time = time.time()
            result = self.ocr.predict(region_img)
            elapsed_time = time.time() - start_time
            self.logger.info(f"⏱️ 区域 OCR 耗时: {elapsed_time:.3f}秒 (偏移: {offset})")

            if not result or len(result) == 0:
                self.logger.warning("OCR识别结果为空")
                return self._empty_result()

            # 收集所有匹配结果
            all_matches = []
            for res in result:
                # 支持两种访问方式：属性访问和字典访问
                if hasattr(res, "rec_texts"):
                    rec_texts = res.rec_texts
                    rec_scores = res.rec_scores
                    dt_polys = res.dt_polys
                elif isinstance(res, dict):
                    rec_texts = res.get("rec_texts", [])
                    rec_scores = res.get("rec_scores", [])
                    dt_polys = res.get("dt_polys", [])
                else:
                    # 尝试作为字典访问（OCRResult 对象）
                    try:
                        rec_texts = res["rec_texts"]
                        rec_scores = res["rec_scores"]
                        dt_polys = res["dt_polys"]
                    except (KeyError, TypeError):
                        rec_texts = []
                        rec_scores = []
                        dt_polys = []

                # 查找匹配的文字
                for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                    if score >= confidence_threshold and target_text in text:
                        if i < len(dt_polys):
                            poly = dt_polys[i]

                            # 调整坐标到原图
                            adjusted_poly = self._adjust_coordinates_to_full_image(
                                poly, offset
                            )

                            # 计算中心点
                            x_coords = [point[0] for point in adjusted_poly]
                            y_coords = [point[1] for point in adjusted_poly]
                            center_x = int(sum(x_coords) / len(x_coords))
                            center_y = int(sum(y_coords) / len(y_coords))

                            all_matches.append(
                                {
                                    "center": (center_x, center_y),
                                    "text": text,
                                    "confidence": score,
                                    "bbox": adjusted_poly,
                                    "index": len(all_matches) + 1,
                                }
                            )

            # 处理匹配结果
            total_matches = len(all_matches)
            self.logger.info(f"找到 {total_matches} 个匹配的文字")

            if total_matches == 0:
                return self._empty_result()

            # 显示所有匹配
            for i, match in enumerate(all_matches, 1):
                self.logger.info(
                    f"  匹配 {i}: '{match['text']}' (置信度: {match['confidence']:.3f}) 位置: {match['center']}"
                )

            # 选择指定的匹配项
            if occurrence > total_matches:
                self.logger.warning(
                    f"请求第{occurrence}个匹配，但只找到{total_matches}个，使用最后一个"
                )
                selected_match = all_matches[-1]
                selected_index = total_matches
            else:
                selected_match = all_matches[occurrence - 1]
                selected_index = occurrence

            self.logger.info(
                f"选择第{selected_index}个匹配: '{selected_match['text']}'"
            )

            return {
                "found": True,
                "center": selected_match["center"],
                "text": selected_match["text"],
                "confidence": selected_match["confidence"],
                "bbox": selected_match["bbox"],
                "total_matches": total_matches,
                "selected_index": selected_index,
            }

        except Exception as e:
            self.logger.error(f"区域搜索出错: {e}")
            return self._empty_result()

    def _get_region_description(self, regions: Optional[List[int]]) -> str:
        """
        获取区域的描述文字

        Args:
            regions: 区域列表

        Returns:
            区域描述，如 "区域[1,2,3]（上部）"
        """
        if not regions:
            return "全屏"

        # 合并区域
        min_row, max_row, min_col, max_col = self._merge_regions(regions)

        # 生成描述
        parts = []

        # 行描述
        if min_row == max_row:
            row_names = ["上部", "中部", "下部"]
            parts.append(row_names[min_row])
        elif min_row == 0 and max_row == 2:
            parts.append("全高")
        else:
            parts.append(f"第{min_row + 1}-{max_row + 1}行")

        # 列描述
        if min_col == max_col:
            col_names = ["左侧", "中间", "右侧"]
            parts.append(col_names[min_col])
        elif min_col == 0 and max_col == 2:
            parts.append("全宽")
        else:
            parts.append(f"第{min_col + 1}-{max_col + 1}列")

        region_str = ",".join(map(str, sorted(regions)))
        return f"区域[{region_str}]（{' '.join(parts)}）"

    def _empty_result(self) -> Dict[str, Any]:
        """返回空的查找结果"""
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
        regions: Optional[List[int]] = None,
    ):
        """
        截图并查找目标文字的位置

        Args:
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            screenshot_path (str): 截图保存路径
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True
            regions (List[int], optional): 要搜索的区域列表（1-9），如果为None则搜索整个图像

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
                regions,
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
        regions: Optional[List[int]] = None,
    ):
        """
        截图、查找文字并点击其中心点

        Args:
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            screenshot_path (str): 截图保存路径
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True
            regions (List[int], optional): 要搜索的区域列表（1-9），如果为None则搜索整个图像

        Returns:
            bool: 是否成功找到并点击
        """
        result = self.capture_and_find_text(
            target_text,
            confidence_threshold,
            screenshot_path,
            occurrence,
            use_cache,
            regions,
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
