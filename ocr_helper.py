"""
OCR Helper Class - 基于PaddleOCR的文字识别和定位工具类
Wrapper around vibe-ocr library.
"""
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from airtest.core.api import snapshot, touch
from project_paths import ensure_project_path
from logger_config import apply_logging_slice, setup_logger_from_config

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

    def capture_and_find_text(
        self,
        target_text,
        confidence_threshold=0.5,
        occurrence=1,
        use_cache=True,
        regions: Optional[List[int]] = None,
        debug_save_path: Optional[str] = None,
        screenshot_path: Optional[str] = None,
    ):
        if screenshot_path:
            # If path is provided, use it
            final_path = screenshot_path
        else:
            # Generate temp path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            final_path = os.path.join(self.temp_dir, f"capture_{timestamp}_{unique_id}.png")

        try:
            self.snapshot_func(filename=final_path)
            
            result = self.find_text_in_image(
                final_path,
                target_text,
                confidence_threshold,
                occurrence,
                use_cache=use_cache,
                regions=regions,
                debug_save_path=debug_save_path,
                return_all=False,
            )
            
            # Retry logic: if use_cache is True and not found, try again with use_cache=False
            if use_cache and (not result or not result.get("found")):
                self.logger.debug(f"缓存未找到文字 '{target_text}'，尝试禁用缓存重新识别...")
                
                self.snapshot_func(filename=final_path)
                
                if regions is None:
                    # Manual handling to ensure cache is saved when regions is None
                    ocr_data = self._get_or_create_ocr_result(
                        final_path, 
                        use_cache=False, 
                        regions=None
                    )
                    
                    if ocr_data:
                        self._save_to_cache(final_path, ocr_data, None)
                        result = self._find_text_in_json(
                            ocr_data, 
                            target_text, 
                            confidence_threshold, 
                            occurrence, 
                            return_all=False
                        )
                    else:
                        result = self._empty_result()
                else:
                    # Fallback for regions (might not cache properly depending on library implementation)
                    result = self.find_text_in_image(
                        final_path,
                        target_text,
                        confidence_threshold,
                        occurrence,
                        use_cache=False, # Disable cache for retry
                        regions=regions,
                        debug_save_path=debug_save_path,
                        return_all=False,
                    )
            
            return result
        finally:
            if not screenshot_path and self.delete_temp_screenshots and os.path.exists(final_path):
                try:
                    os.remove(final_path)
                except Exception:
                    pass

    def find_and_click_text(
        self,
        target_text,
        confidence_threshold=0.5,
        occurrence=1,
        use_cache=True,
        regions: Optional[List[int]] = None,
    ):
        result = self.capture_and_find_text(
            target_text,
            confidence_threshold=confidence_threshold,
            occurrence=occurrence,
            use_cache=use_cache,
            regions=regions,
        )
        
        if result and result.get("found"):
            center = result.get("center")
            if center:
                try:
                    touch(center)
                    self.logger.info(f"点击了文字 '{target_text}' at {center}")
                    return True
                except Exception as e:
                    self.logger.error(f"点击文字 '{target_text}' 失败: {e}")
                    return False
        
        return False

# Apply logging slice
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
