"""
OCR Helper Class - 基于PaddleOCR的文字识别和定位工具类
提供统一的接口供外部调用，输入图像文件和要查找的文字，返回文字所在的图片区域
支持区域分割功能，可以指定只识别屏幕的特定区域，大大提升识别速度
"""

import requests
import json
import os
import time
import base64
import cv2
import uuid
import shutil
import sqlite3
import imagehash
from PIL import Image
from datetime import datetime
from airtest.core.api import snapshot, touch
from airtest.aircv.cal_confidence import cal_ccoeff_confidence
from typing import List, Tuple, Optional, Dict, Any, Set
from project_paths import ensure_project_path
from logger_config import setup_logger_from_config, apply_logging_slice


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
        delete_temp_screenshots=True,
        max_cache_size=200,
        hash_type="dhash",  # 可选: "phash", "dhash", "ahash", "whash"
        hash_threshold=10,  # hash 汉明距离阈值
        cpu_threads: Optional[int] = None,
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
            delete_temp_screenshots (bool): 是否删除临时截图文件，默认为True
            max_cache_size (int): 最大缓存条目数，默认200
            hash_type (str): 哈希算法类型，默认"dhash"（差分哈希，最快）
            hash_threshold (int): 哈希汉明距离阈值，默认10
        """
        resolved_output_dir = ensure_project_path(output_dir)
        self.output_dir = str(resolved_output_dir)
        self.resize_image = resize_image
        self.max_width = max_width
        self.delete_temp_screenshots = delete_temp_screenshots
        self.max_cache_size = max_cache_size
        self.hash_type = hash_type
        self.hash_threshold = hash_threshold

        self.ocr_url = os.getenv("OCR_SERVER_URL", "http://localhost:8080/ocr")

        # 创建输出目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # 创建缓存目录和临时目录
        self.cache_dir = os.path.join(self.output_dir, "cache")
        self.temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

        # 配置彩色日志（从系统配置文件加载通用日志配置）
        # 需要先初始化，因为缓存加载时会用到
        self.logger = setup_logger_from_config(use_color=True)

        # 初始化缓存
        # 格式: [(image_path, json_file_path), ...]
        self.ocr_cache = []

        # 缓存相似度阈值（95%以上认为是同一张图）
        self.cache_similarity_threshold = 0.95

        # 初始化 SQLite 缓存数据库
        self.cache_db_path = os.path.join(self.cache_dir, "cache.db")
        self._init_cache_db()

        # 加载已有的缓存（需要在 logger 初始化之后）
        self._load_existing_cache()

    def _init_cache_db(self):
        """
        初始化缓存数据库，创建必要的表
        """
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.cursor()
                # 创建缓存表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_path TEXT UNIQUE NOT NULL,
                        json_path TEXT NOT NULL,
                        phash TEXT,
                        dhash TEXT,
                        ahash TEXT,
                        whash TEXT,
                        regions TEXT,  -- JSON 存储区域信息
                        hit_count INTEGER DEFAULT 0,
                        last_access_time REAL,
                        created_time REAL,
                        image_size INTEGER,  -- 图片文件大小
                        image_hash TEXT  -- MD5 hash for exact duplicate detection
                    )
                """)
                # 创建索引以加速查询
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_phash ON cache_entries(phash)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dhash ON cache_entries(dhash)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_last_access ON cache_entries(last_access_time)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_image_hash ON cache_entries(image_hash)"
                )
                conn.commit()
            self.logger.debug(f"✅ 缓存数据库初始化成功: {self.cache_db_path}")
        except Exception as e:
            self.logger.error(f"❌ 初始化缓存数据库失败: {e}")
            raise

    def _compute_image_hash(
        self, image_path: str, hash_type: Optional[str] = None
    ) -> Optional[str]:
        """
        计算图像的感知哈希值

        Args:
            image_path: 图像路径
            hash_type: 哈希类型 ("phash", "dhash", "ahash", "whash")

        Returns:
            哈希值的十六进制字符串，失败返回None
        """
        if hash_type is None:
            hash_type = self.hash_type

        try:
            with Image.open(image_path) as img:
                if hash_type == "phash":
                    hash_obj = imagehash.phash(img)
                elif hash_type == "dhash":
                    hash_obj = imagehash.dhash(img)
                elif hash_type == "ahash":
                    hash_obj = imagehash.average_hash(img)
                elif hash_type == "whash":
                    hash_obj = imagehash.whash(img)
                else:
                    self.logger.warning(f"未知的哈希类型: {hash_type}，使用默认 dhash")
                    hash_obj = imagehash.dhash(img)
                return str(hash_obj)
        except Exception as e:
            self.logger.debug(f"计算图像哈希失败 ({image_path}): {e}")
            return None

    def _compute_all_hashes(self, image_path: str) -> Dict[str, str]:
        """
        计算图像的所有哈希值

        Args:
            image_path: 图像路径

        Returns:
            包含所有哈希值的字典
        """
        hashes = {}
        try:
            with Image.open(image_path) as img:
                hashes["phash"] = str(imagehash.phash(img))
                hashes["dhash"] = str(imagehash.dhash(img))
                hashes["ahash"] = str(imagehash.average_hash(img))
                hashes["whash"] = str(imagehash.whash(img))
        except Exception as e:
            self.logger.debug(f"计算图像哈希失败 ({image_path}): {e}")
        return hashes

    def _calculate_hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        计算两个哈希值之间的汉明距离

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值

        Returns:
            汉明距离（不同位的数量）
        """
        try:
            # 将十六进制转换为二进制字符串
            h1 = int(hash1, 16)
            h2 = int(hash2, 16)
            # 异或后计算1的个数
            return bin(h1 ^ h2).count("1")
        except Exception:
            return 999  # 返回一个大值表示无法比较

    def _get_cache_key(
        self, image_path: str, regions: Optional[List[int]] = None
    ) -> str:
        """
        生成缓存键，包含图像路径和区域信息

        Args:
            image_path: 图像路径
            regions: 区域列表

        Returns:
            唯一的缓存键
        """
        if regions:
            regions_str = "_".join(map(str, sorted(regions)))
            return f"{image_path}_{regions_str}"
        return image_path

    def _find_similar_in_cache(
        self, image_path: str, regions: Optional[List[int]] = None
    ) -> Optional[str]:
        """
        在缓存中查找相似的图像

        Args:
            image_path: 要查找的图像路径
            regions: 区域列表（如果有的话）

        Returns:
            找到的JSON文件路径，没找到返回None
        """
        try:
            # 计算当前图像的哈希值
            current_hashes = self._compute_all_hashes(image_path)
            if not current_hashes.get(self.hash_type):
                return None

            # 连接数据库
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.cursor()

                # 首先检查是否有完全相同的图像（通过文件哈希）
                import hashlib

                with open(image_path, "rb") as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()

                cursor.execute(
                    "SELECT json_path FROM cache_entries WHERE image_hash = ?",
                    (file_hash,),
                )
                result = cursor.fetchone()
                if result:
                    self.logger.debug(f"💾 缓存命中（完全相同）: {result[0]}")
                    # 更新访问信息
                    cursor.execute(
                        "UPDATE cache_entries SET hit_count = hit_count + 1, last_access_time = ? WHERE image_hash = ?",
                        (time.time(), file_hash),
                    )
                    conn.commit()
                    return result[0]

                # 查找相似的图像（基于感知哈希）
                # 使用主要哈希类型进行查找
                primary_hash = current_hashes[self.hash_type]

                # 构建查询 - 查找汉明距离小于阈值的条目
                # 注意：SQLite没有内置的汉明距离函数，所以我们获取所有记录并在Python中计算
                cursor.execute(f"""
                    SELECT image_path, json_path, {self.hash_type}, hit_count, last_access_time
                    FROM cache_entries
                    WHERE {self.hash_type} IS NOT NULL
                    ORDER BY last_access_time DESC
                    LIMIT 100
                """)

                candidates = cursor.fetchall()
                best_match = None
                best_distance = 999

                for (
                    img_path,
                    json_path,
                    cached_hash,
                    hit_count,
                    last_access,
                ) in candidates:
                    if not cached_hash:
                        continue

                    distance = self._calculate_hamming_distance(
                        primary_hash, cached_hash
                    )
                    if distance < best_distance and distance <= self.hash_threshold:
                        best_distance = distance
                        best_match = (json_path, distance, hit_count)

                if best_match:
                    json_path, distance, hit_count = best_match
                    self.logger.debug(
                        f"💾 缓存命中（哈希相似，距离={distance}）: {json_path}"
                    )

                    # 更新访问信息
                    cursor.execute(
                        "UPDATE cache_entries SET hit_count = hit_count + 1, last_access_time = ? WHERE json_path = ?",
                        (time.time(), json_path),
                    )
                    conn.commit()

                    return json_path

            return None
        except Exception as e:
            self.logger.error(f"查找缓存失败: {e}")
            return None

    def _evict_cache(self):
        """
        淘汰最久未访问的缓存条目，保持缓存大小在限制内
        """
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.cursor()

                # 获取当前缓存条目数
                cursor.execute("SELECT COUNT(*) FROM cache_entries")
                count = cursor.fetchone()[0]

                if count > self.max_cache_size:
                    # 计算需要删除的条目数
                    to_delete = (
                        count - self.max_cache_size + 10
                    )  # 多删除一些，避免频繁操作

                    # 获取最久未访问的条目
                    cursor.execute(
                        """
                        SELECT image_path, json_path
                        FROM cache_entries
                        ORDER BY last_access_time ASC
                        LIMIT ?
                    """,
                        (to_delete,),
                    )

                    to_evict = cursor.fetchall()

                    # 删除文件和数据库记录
                    for img_path, json_path in to_evict:
                        try:
                            if os.path.exists(img_path):
                                os.remove(img_path)
                            if os.path.exists(json_path):
                                os.remove(json_path)
                        except Exception:
                            pass

                    # 从数据库删除记录
                    cursor.execute(
                        """
                        DELETE FROM cache_entries
                        WHERE id IN (
                            SELECT id FROM cache_entries
                            ORDER BY last_access_time ASC
                            LIMIT ?
                        )
                    """,
                        (to_delete,),
                    )

                    conn.commit()
                    self.logger.debug(f"🗑️ 淘汰了 {to_delete} 个缓存条目")
        except Exception as e:
            self.logger.error(f"淘汰缓存失败: {e}")

    def _save_to_cache_db(
        self, image_path: str, json_path: str, regions: Optional[List[int]] = None
    ):
        """
        保存缓存条目到数据库

        Args:
            image_path: 图像路径
            json_path: JSON文件路径
            regions: 区域列表
        """
        try:
            # 计算所有哈希值
            hashes = self._compute_all_hashes(image_path)

            # 计算文件哈希
            import hashlib

            with open(image_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            # 获取文件大小
            image_size = os.path.getsize(image_path)

            # 准备区域信息
            regions_json = json.dumps(sorted(regions)) if regions else None

            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.cursor()

                # 插入或更新记录
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (image_path, json_path, phash, dhash, ahash, whash, regions,
                     hit_count, last_access_time, created_time, image_size, image_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                    (
                        image_path,
                        json_path,
                        hashes.get("phash"),
                        hashes.get("dhash"),
                        hashes.get("ahash"),
                        hashes.get("whash"),
                        regions_json,
                        time.time(),
                        time.time(),
                        image_size,
                        file_hash,
                    ),
                )

                conn.commit()

            # 检查是否需要淘汰
            self._evict_cache()

        except Exception as e:
            self.logger.error(f"保存缓存到数据库失败: {e}")

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
            self.logger.debug(f"🔍 调试：区域截图已保存到 {debug_save_path}")
            self.logger.debug(f"   区域范围: x={x}, y={y}, w={w}, h={h}")
            self.logger.debug(f"   原图尺寸: {width}x{height}")

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
                self.logger.debug(f"💾 加载了 {len(self.ocr_cache)} 个缓存文件")
        except Exception as e:
            self.logger.error(f"加载缓存失败: {e}")

    def _find_similar_cached_image(
        self, current_image_path, regions: Optional[List[int]] = None
    ):
        """
        查找缓存中是否有相似的图片（使用新的哈希索引系统）

        Args:
            current_image_path (str): 当前图片路径
            regions (List[int], optional): 区域列表

        Returns:
            str: 缓存的 JSON 文件路径，如果没有找到则返回 None
        """
        # 首先尝试使用新的哈希索引系统
        cached_json = self._find_similar_in_cache(current_image_path, regions)
        if cached_json:
            return cached_json

        # 如果新系统没找到，回退到旧系统（兼容性）
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
                    self.logger.debug(
                        f"💾 找到相似缓存图片（旧系统）(相似度: {similarity * 100:.1f}%)"
                    )
                    return cached_json_path

            return None
        except Exception as e:
            self.logger.error(f"查找相似缓存图片失败: {e}")
            return None

    def _save_to_cache(
        self, image_path, json_file, regions: Optional[List[int]] = None
    ):
        """
        保存图片和 OCR 结果到缓存（使用新的 SQLite 系统）

        Args:
            image_path (str): 图片路径
            json_file (str): JSON 文件路径
            regions (List[int], optional): 区域列表
        """
        try:
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
                # 保存缓存记录到旧系统（兼容性）
                self.ocr_cache.append((cache_image_path, cache_json_path))
                self.logger.debug(
                    f"💾 缓存已保存 (图片数: {len(self.ocr_cache)}, JSON: {cache_json_name})"
                )

                # 保存到新的 SQLite 系统
                self._save_to_cache_db(cache_image_path, cache_json_path, regions)
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
        执行 OCR 识别并记录耗时 (Remote PaddleX 3.0)

        Args:
            image_path (str): 图像文件路径

        Returns:
            OCR 识别结果 (dict: {rec_texts: [], rec_scores: [], dt_polys: []})
        """
        # 预处理：缩小图片
        processed_image_path = self._resize_image_for_ocr(image_path)

        start_time = time.time()
        result = None

        try:
            # 1. 转换为 Base64
            with open(processed_image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # 2. 构建符合 PaddleX 3.0 规范的 Payload
            payload = {
                "file": image_data,
                "fileType": 1
            }
            
            # 3. 发送请求 (默认端口 8080)
            response = requests.post(self.ocr_url, json=payload, timeout=30)
            response.raise_for_status()
            json_resp = response.json()

            if json_resp.get("errorCode") == 0:
                # PaddleX 3.0 的结果嵌套在 result.ocrResults[0].prunedResult 中
                ocr_results = json_resp.get("result", {}).get("ocrResults", [])
                if ocr_results:
                    pruned = ocr_results[0].get("prunedResult", {})
                    
                    # 转换格式为 OCRHelper 所需的格式
                    result = {
                        "rec_texts": pruned.get("rec_texts", []),
                        "rec_scores": pruned.get("rec_scores", []),
                        "dt_polys": pruned.get("dt_polys", [])
                    }
                else:
                    self.logger.warning(f"OCR Server returned empty ocrResults")
            else:
                self.logger.error(f"OCR Server Error: {json_resp.get('errorMsg')}")

        except Exception as e:
            self.logger.error(f"OCR Request Failed: {e}")

        elapsed_time = time.time() - start_time

        filename = os.path.basename(image_path)
        self.logger.debug(f"⏱️ OCR识别耗时: {elapsed_time:.3f}秒 (文件: {filename})")

        # 清理临时文件
        if processed_image_path != image_path and os.path.exists(processed_image_path):
            try:
                os.remove(processed_image_path)
            except Exception:
                pass

        return result

    def _get_or_create_ocr_result(
        self, image_path, use_cache=True, regions: Optional[List[int]] = None
    ):
        """
        获取或创建 OCR 识别结果（带缓存）

        Args:
            image_path (str): 图像文件路径
            use_cache (bool): 是否使用缓存，默认为 True
            regions (List[int], optional): 区域列表

        Returns:
            str: JSON 文件路径
        """
        # 如果启用缓存，检查缓存中是否有相似图片
        if use_cache:
            cached_json = self._find_similar_cached_image(image_path, regions)
            if cached_json:
                return cached_json

        # 缓存未命中或禁用缓存，执行 OCR 识别
        result = self._predict_with_timing(image_path)

        if result:
            # 使用完整的文件路径保存到 cache 目录
            json_filename = os.path.basename(image_path).replace(
                ".png", "_res.json"
            )
            json_path = os.path.join(self.cache_dir, json_filename)

            # 保存 JSON
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)

            # 获取 JSON 文件路径
            json_file = json_path

            # 如果启用缓存，同时保存到缓存
            if use_cache and os.path.exists(json_file):
                self._save_to_cache(image_path, json_file, regions)

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
                    use_cache,
                )

            # 获取或创建 OCR 结果（带缓存）
            json_file = self._get_or_create_ocr_result(
                image_path, use_cache=use_cache, regions=regions
            )

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
        use_cache: bool = True,
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
            use_cache: 是否使用缓存，默认为 True

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
            self.logger.debug(f"🔍 在{region_desc}搜索文字: '{target_text}'")

            # 为区域图像生成缓存键
            region_key = self._get_cache_key(image_path, regions)
            region_cache_path = os.path.join(
                self.cache_dir, f"region_{hash(region_key) % 1000000}.png"
            )

            # 初始化结果
            result = None
            cache_used = False
            elapsed_time = 0

            # 只有在使用缓存时才尝试从缓存读取
            if use_cache:
                # 保存区域图像以供缓存
                cv2.imwrite(region_cache_path, region_img)

                # 尝试从缓存获取OCR结果
                cached_json = self._find_similar_in_cache(region_cache_path, regions)
                if cached_json and os.path.exists(cached_json):
                    self.logger.debug(f"💾 区域缓存命中: {region_desc}")
                    # 从缓存的JSON读取结果
                    with open(cached_json, "r", encoding="utf-8") as f:
                        ocr_data = json.load(f)
                    # 转换格式以兼容现有代码
                    result = [ocr_data] if isinstance(ocr_data, dict) else ocr_data
                    cache_used = True

            # 如果没有命中缓存或不使用缓存，进行OCR识别
            if result is None:
                # 对区域进行OCR识别
                start_time = time.time()
                result = self.ocr.predict(region_img)
                elapsed_time = time.time() - start_time
                self.logger.debug(
                    f"⏱️ 区域 OCR 耗时: {elapsed_time:.3f}秒 (偏移: {offset})"
                )

                # 保存OCR结果到缓存（仅在使用缓存时）
                if use_cache and result and len(result) > 0:
                    # 保存OCR结果
                    region_json_path = region_cache_path.replace(".png", "_res.json")
                    # 直接保存结果到指定路径
                    for res in result:
                        # PaddleOCR 的 save_to_json 方法需要完整路径
                        res.save_to_json(
                            os.path.join(
                                self.cache_dir, os.path.basename(region_json_path)
                            )
                        )

                    # 更新缓存数据库
                    self._save_to_cache_db(region_cache_path, region_json_path, regions)

            if not result or len(result) == 0:
                self.logger.warning("OCR识别结果为空")
                return self._empty_result()

            # 收集所有匹配结果
            all_matches = []
            for res in result:
                # 使用函数级别的缓存和耗时信息
                res_cache_used = cache_used
                res_elapsed_time = elapsed_time
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
                                    "cache_used": res_cache_used,
                                    "elapsed_time": res_elapsed_time,
                                }
                            )

            # 处理匹配结果
            total_matches = len(all_matches)

            if total_matches == 0:
                self.logger.debug(f"未找到匹配的文字: '{target_text}'")
                return self._empty_result()

            # 选择指定的匹配项
            if occurrence > total_matches:
                selected_match = all_matches[-1]
                selected_index = total_matches
            else:
                selected_match = all_matches[occurrence - 1]
                selected_index = occurrence

            # 输出关键信息：只输出选中的匹配
            # 判断是否使用了缓存
            cache_used = False
            if "cache_used" in selected_match:
                cache_used = selected_match["cache_used"]

            # 计算耗时（如果有的话）
            elapsed_time_str = ""
            if "elapsed_time" in selected_match:
                elapsed_time_str = f" 耗时:{selected_match['elapsed_time']:.3f}s"

            # 输出选中的匹配信息
            self.logger.info(
                f"找到文字: '{selected_match['text']}' "
                f"置信度:{selected_match['confidence']:.3f} "
                f"位置:{selected_match['center']} "
                f"缓存:{'是' if cache_used else '否'}"
                f"{elapsed_time_str}"
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
        screenshot_path=None,
        occurrence=1,
        use_cache=True,
        regions: Optional[List[int]] = None,
    ):
        """
        截图并查找目标文字的位置

        Args:
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            screenshot_path (str, optional): 截图保存路径，如果为None则使用随机临时文件名
            occurrence (int): 指定点击第几个出现的文字 (1-based)，默认为1
            use_cache (bool): 是否使用缓存，默认为 True
            regions (List[int], optional): 要搜索的区域列表（1-9），如果为None则搜索整个图像

        Returns:
            dict: 包含查找结果的字典，格式同find_text_in_image
        """
        temp_screenshot_paths: Set[str] = set()

        def _create_temp_screenshot_path() -> str:
            """生成并记录临时截图路径"""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            temp_path = os.path.join(
                self.temp_dir, f"screenshot_{timestamp}_{unique_id}.png"
            )
            temp_screenshot_paths.add(temp_path)
            return temp_path

        user_provided_path = screenshot_path is not None

        try:
            if not user_provided_path:
                screenshot_path = _create_temp_screenshot_path()

            # 首次截图
            snapshot(filename=screenshot_path)
            self.logger.debug(f"截图保存到: {screenshot_path}")

            # 在截图中查找文字
            result = self.find_text_in_image(
                screenshot_path,
                target_text,
                confidence_threshold,
                occurrence,
                use_cache,
                regions,
            )

            # 如果使用缓存但未找到，进行实时截图重试
            if use_cache and (not result or not result.get("found")):
                self.logger.info("缓存 OCR 未找到目标文字，尝试实时截图重试")
                fallback_path = (
                    screenshot_path
                    if user_provided_path
                    else _create_temp_screenshot_path()
                )

                snapshot(filename=fallback_path)
                self.logger.debug(f"实时截图保存到: {fallback_path}")

                fallback_result = self.find_text_in_image(
                    fallback_path,
                    target_text,
                    confidence_threshold,
                    occurrence,
                    use_cache=False,
                    regions=regions,
                )

                if fallback_result:
                    result = fallback_result

                # 如果实时识别成功，刷新缓存
                if fallback_result and fallback_result.get("found") and regions is None:
                    base_name, _ = os.path.splitext(os.path.basename(fallback_path))
                    json_file = os.path.join(self.cache_dir, f"{base_name}_res.json")
                    if os.path.exists(json_file):
                        try:
                            self._save_to_cache(fallback_path, json_file, regions)
                            self.logger.debug("实时截图结果已刷新缓存")
                        except Exception as cache_err:
                            self.logger.warning(f"刷新缓存失败: {cache_err}")

            return result

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
        finally:
            if self.delete_temp_screenshots:
                for temp_file in list(temp_screenshot_paths):
                    if not temp_file:
                        continue
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                            self.logger.debug(f"已删除临时截图: {temp_file}")
                    except Exception as cleanup_error:
                        self.logger.warning(f"删除临时截图失败: {cleanup_error}")

    def find_and_click_text(
        self,
        target_text,
        confidence_threshold=0.5,
        screenshot_path=None,
        occurrence=1,
        use_cache=True,
        regions: Optional[List[int]] = None,
    ):
        """
        截图、查找文字并点击其中心点

        Args:
            target_text (str): 要查找的目标文字
            confidence_threshold (float): 置信度阈值 (0-1)
            screenshot_path (str, optional): 截图保存路径，如果为None则使用随机临时文件名
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
            self.logger.debug(f"点击位置: {center}")
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

            self.logger.debug(f"在JSON中查找文字: '{target_text}' (第{occurrence}个)")
            self.logger.debug(f"总共识别到 {len(rec_texts)} 个文字")

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
            # 不在这里输出匹配数量，改为在选择后输出

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
            # 不再输出所有匹配，只输出选中的

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

            # 输出选中的匹配信息
            self.logger.info(
                f"找到文字: '{selected_match['text']}' "
                f"置信度:{selected_match['confidence']:.3f} "
                f"位置:{selected_match['center']} "
                f"缓存:是"
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


# 批量为关键方法应用日志切面
try:
    apply_logging_slice(
        [
            (OCRHelper, "capture_and_find_text"),
            (OCRHelper, "find_text_in_image"),
            (OCRHelper, "find_and_click_text"),
            (OCRHelper, "_get_or_create_ocr_result"),
            (OCRHelper, "_find_text_in_regions"),
            (OCRHelper, "_predict_with_timing"),
        ],
        level="DEBUG",
    )
except Exception:
    pass
