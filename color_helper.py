import cv2
import numpy as np
import logging
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger("color_helper")

class ColorHelper:
    @staticmethod
    def find_green_text(image_path: str, ocr_results: List[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
        """
        在给定的 OCR 结果中查找具有高比例绿色像素的文本区域
        
        Args:
            image_path: 图片路径
            ocr_results: OCR 结果列表，每个项包含 'bbox' (或者 'poly'), 'text' 等
        
        Returns:
            (x, y) 绿色文字中心坐标，未找到返回 None
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None

            # 转换为 HSV
            hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # 定义绿色范围
            # HSV 中绿色 H 范围通常在 35-85 左右
            lower_green = np.array([35, 43, 46])
            upper_green = np.array([85, 255, 255])

            best_match = None
            max_green_ratio = 0.0

            for item in ocr_results:
                # 获取 bbox
                # vibe_ocr.OCRHelper 的结果中 bbox 格式通常是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                bbox = item.get("bbox") or item.get("poly")
                if not bbox:
                    continue

                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                x_min, x_max = int(min(xs)), int(max(xs))
                y_min, y_max = int(min(ys)), int(max(ys))

                # 边界检查
                x_min = max(0, x_min)
                y_min = max(0, y_min)
                x_max = min(img.shape[1], x_max)
                y_max = min(img.shape[0], y_max)

                if x_max <= x_min or y_max <= y_min:
                    continue

                roi = hsv_img[y_min:y_max, x_min:x_max]
                if roi.size == 0:
                    continue

                # 计算绿色像素占比
                mask = cv2.inRange(roi, lower_green, upper_green)
                green_pixels = cv2.countNonZero(mask)
                total_pixels = roi.shape[0] * roi.shape[1]
                
                if total_pixels == 0:
                    continue

                ratio = green_pixels / total_pixels

                # 阈值：至少 10% 是绿色
                if ratio > 0.1:
                    if ratio > max_green_ratio:
                        max_green_ratio = ratio
                        center_x = int((x_min + x_max) / 2)
                        center_y = int((y_min + y_max) / 2)
                        best_match = (center_x, center_y)

            if best_match:
                logger.info(f"找到绿色文字区域，绿色占比: {max_green_ratio:.2f}")
            
            return best_match

        except Exception as e:
            logger.error(f"查找绿色文字失败: {e}")
            return None
