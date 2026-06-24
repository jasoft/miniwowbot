"""
OCR Helper Class - 基于PaddleOCR的文字识别和定位工具类
Wrapper around vibe-ocr library.
"""
import time
import sqlite3
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from airtest.core.api import snapshot
from project_paths import ensure_project_path
from logger_config import setup_logger_from_config

# Import from library
from vibe_ocr.ocr_helper import OCRHelper as BaseOCRHelper

load_dotenv()

# 缓存过期时间：24小时（秒）
CACHE_TTL_SECONDS = 24 * 60 * 60


class OCRHelper(BaseOCRHelper):
    def __init__(
        self,
        output_dir="output",
        resize_image=True,
        max_width=960,
        delete_temp_screenshots=True,
        max_cache_size=200,
        hash_type="dhash",
        hash_threshold=10,
        correction_map: Optional[Dict[str, str]] = None,
        snapshot_func: Optional[Any] = None,
    ):
        resolved_output_dir = ensure_project_path(output_dir)

        super().__init__(
            output_dir=str(resolved_output_dir),
            resize_image=resize_image,
            max_width=max_width,
            delete_temp_screenshots=delete_temp_screenshots,
            max_cache_size=max_cache_size,
            hash_type=hash_type,
            hash_threshold=hash_threshold,
            correction_map=correction_map,
            snapshot_func=snapshot_func or snapshot,
        )

        # Override logger to match project config
        self.logger = setup_logger_from_config(use_color=True)

    def _clean_expired_cache(self) -> int:
        """
        清理已过期的缓存条目（超过24小时）。

        Returns:
            已删除的条目数量
        """
        try:
            expire_time = time.time() - CACHE_TTL_SECONDS
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM ocr_cache WHERE created_time < ?",
                    (expire_time,),
                )
                expired_count = cursor.fetchone()[0]
                if expired_count > 0:
                    cursor.execute(
                        "DELETE FROM ocr_cache WHERE created_time < ?",
                        (expire_time,),
                    )
                    conn.commit()
                    self.logger.info(f"清理了 {expired_count} 个过期缓存条目（超过24小时）")
                return expired_count
        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {e}")
            return 0

    def _find_similar_cached_image(self, current_image_path, regions: Optional[list] = None):
        """
        查找缓存中是否有相似的图片，在查找前先清理过期条目。

        Args:
            current_image_path: 当前图片路径
            regions: 区域列表

        Returns:
            缓存的 OCR 结果，如果没有找到则返回 None
        """
        # 先清理过期缓存，防止读取到错误的旧截图结果
        self._clean_expired_cache()
        return super()._find_similar_cached_image(current_image_path, regions)