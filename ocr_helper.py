"""
OCR Helper Class - 基于PaddleOCR的文字识别和定位工具类
Wrapper around vibe-ocr library.
"""
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from airtest.core.api import snapshot
from project_paths import ensure_project_path
from logger_config import setup_logger_from_config

# Import from library
from vibe_ocr.ocr_helper import OCRHelper as BaseOCRHelper

load_dotenv()

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

# No need to override capture_and_find_text or find_and_click_text 
# as they are now provided by the base library.