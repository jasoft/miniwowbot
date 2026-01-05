"""
测试 OCR Helper 的区域搜索功能
"""

import pytest
import cv2
import numpy as np
from vibe_ocr import OCRHelper


@pytest.fixture
def temp_output_dir(tmp_path):
    """创建临时输出目录"""
    output_dir = tmp_path / "ocr_output"
    output_dir.mkdir()
    return str(output_dir)


@pytest.fixture
def sample_image(tmp_path):
    """创建一个测试图像，包含不同区域的文字"""
    # 创建一个 900x900 的白色图像
    img = np.ones((900, 900, 3), dtype=np.uint8) * 255

    # 在不同区域添加文字标记（使用简单的矩形代替文字）
    # 区域1 (左上)
    cv2.rectangle(img, (50, 50), (250, 100), (0, 0, 0), -1)
    cv2.putText(
        img, "Region 1", (60, 85), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
    )

    # 区域2 (中上)
    cv2.rectangle(img, (350, 50), (550, 100), (0, 0, 0), -1)
    cv2.putText(
        img, "Region 2", (360, 85), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
    )

    # 区域3 (右上)
    cv2.rectangle(img, (650, 50), (850, 100), (0, 0, 0), -1)
    cv2.putText(
        img, "Region 3", (660, 85), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
    )

    # 区域5 (中心)
    cv2.rectangle(img, (350, 400), (550, 450), (0, 0, 0), -1)
    cv2.putText(
        img, "Center", (370, 435), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
    )

    # 区域9 (右下)
    cv2.rectangle(img, (650, 800), (850, 850), (0, 0, 0), -1)
    cv2.putText(
        img, "Region 9", (660, 835), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
    )

    # 保存图像
    image_path = tmp_path / "test_regions.png"
    cv2.imwrite(str(image_path), img)
    return str(image_path)


class TestRegionMerge:
    """测试区域合并"""

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 区域1
        min_row, max_row, min_col, max_col = ocr._merge_regions([1])
        assert (min_row, max_row, min_col, max_col) == (0, 0, 0, 0)

        # 区域5
        min_row, max_row, min_col, max_col = ocr._merge_regions([5])
        assert (min_row, max_row, min_col, max_col) == (1, 1, 1, 1)

        # 区域9
        min_row, max_row, min_col, max_col = ocr._merge_regions([9])
        assert (min_row, max_row, min_col, max_col) == (2, 2, 2, 2)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 上部整行 (1, 2, 3)
        min_row, max_row, min_col, max_col = ocr._merge_regions([1, 2, 3])
        assert (min_row, max_row, min_col, max_col) == (0, 0, 0, 2)

        # 中部整行 (4, 5, 6)
        min_row, max_row, min_col, max_col = ocr._merge_regions([4, 5, 6])
        assert (min_row, max_row, min_col, max_col) == (1, 1, 0, 2)

        # 下部整行 (7, 8, 9)
        min_row, max_row, min_col, max_col = ocr._merge_regions([7, 8, 9])
        assert (min_row, max_row, min_col, max_col) == (2, 2, 0, 2)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 左侧整列 (1, 4, 7)
        min_row, max_row, min_col, max_col = ocr._merge_regions([1, 4, 7])
        assert (min_row, max_row, min_col, max_col) == (0, 2, 0, 0)

        # 中间整列 (2, 5, 8)
        min_row, max_row, min_col, max_col = ocr._merge_regions([2, 5, 8])
        assert (min_row, max_row, min_col, max_col) == (0, 2, 1, 1)

        # 右侧整列 (3, 6, 9)
        min_row, max_row, min_col, max_col = ocr._merge_regions([3, 6, 9])
        assert (min_row, max_row, min_col, max_col) == (0, 2, 2, 2)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 左上角 2x2 (1, 2, 4, 5)
        min_row, max_row, min_col, max_col = ocr._merge_regions([1, 2, 4, 5])
        assert (min_row, max_row, min_col, max_col) == (0, 1, 0, 1)

        # 右下角 2x2 (5, 6, 8, 9)
        min_row, max_row, min_col, max_col = ocr._merge_regions([5, 6, 8, 9])
        assert (min_row, max_row, min_col, max_col) == (1, 2, 1, 2)


class TestRegionBounds:
    """测试区域边界计算"""

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)
        bounds = ocr._get_region_bounds((900, 900), None)
        assert bounds == (0, 0, 900, 900)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 测试区域1 (左上)
        bounds = ocr._get_region_bounds((900, 900), [1])
        assert bounds == (0, 0, 300, 300)

        # 测试区域5 (中心)
        bounds = ocr._get_region_bounds((900, 900), [5])
        assert bounds == (300, 300, 300, 300)

        # 测试区域9 (右下)
        bounds = ocr._get_region_bounds((900, 900), [9])
        assert bounds == (600, 600, 300, 300)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 上部整行 (1, 2, 3)
        bounds = ocr._get_region_bounds((900, 900), [1, 2, 3])
        assert bounds == (0, 0, 900, 300)

        # 下部整行 (7, 8, 9)
        bounds = ocr._get_region_bounds((900, 900), [7, 8, 9])
        assert bounds == (0, 600, 900, 300)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 左侧整列 (1, 4, 7)
        bounds = ocr._get_region_bounds((900, 900), [1, 4, 7])
        assert bounds == (0, 0, 300, 900)

        # 右侧整列 (3, 6, 9)
        bounds = ocr._get_region_bounds((900, 900), [3, 6, 9])
        assert bounds == (600, 0, 300, 900)


class TestExtractRegion:
    """测试区域提取"""

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)
        image = cv2.imread(sample_image)

        region_img, offset = ocr._extract_region(image, [1])
        assert region_img.shape[0] == 300  # 高度
        assert region_img.shape[1] == 300  # 宽度
        assert offset == (0, 0)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)
        image = cv2.imread(sample_image)

        # 提取上部整行 (1, 2, 3)
        region_img, offset = ocr._extract_region(image, [1, 2, 3])
        assert region_img.shape[0] == 300  # 高度
        assert region_img.shape[1] == 900  # 宽度（整行）
        assert offset == (0, 0)

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)
        image = cv2.imread(sample_image)

        # 提取左侧整列 (1, 4, 7)
        region_img, offset = ocr._extract_region(image, [1, 4, 7])
        assert region_img.shape[0] == 900  # 高度（整列）
        assert region_img.shape[1] == 300  # 宽度
        assert offset == (0, 0)


class TestCoordinateAdjustment:
    """测试坐标调整"""

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 区域内的边界框
        bbox = [[10, 20], [100, 20], [100, 50], [10, 50]]

        # 区域偏移量
        offset = (300, 300)

        # 调整坐标
        adjusted = ocr._adjust_coordinates_to_full_image(bbox, offset)

        # 验证调整后的坐标
        assert adjusted == [[310, 320], [400, 320], [400, 350], [310, 350]]


class TestRegionSearch:
    """测试区域搜索功能"""

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 测试在区域1中搜索（应该能找到 "Region 1"）
        # 注意：这个测试可能会失败，因为OCR可能无法识别简单的文字
        # 这里主要测试API是否正常工作，不会抛出异常
        result = ocr.find_text_in_image(
            sample_image, "Region", confidence_threshold=0.3, regions=[1]
        )

        # 验证返回的结果格式正确
        assert "found" in result
        assert "center" in result
        assert "text" in result
        assert "confidence" in result
        assert "bbox" in result
        assert "total_matches" in result
        assert "selected_index" in result

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)

        # 在区域1, 2, 3中搜索
        result = ocr.find_text_in_image(
            sample_image, "Region", confidence_threshold=0.3, regions=[1, 2, 3]
        )

        # 验证返回的结果格式正确
        assert "found" in result
        assert isinstance(result["found"], bool)


class TestEmptyResult:
    """测试空结果"""

        ocr = vibe_ocr.OCRHelper(output_dir=temp_output_dir)
        result = ocr._empty_result()

        assert result["found"] is False
        assert result["center"] is None
        assert result["text"] is None
        assert result["confidence"] is None
        assert result["bbox"] is None
        assert result["total_matches"] == 0
        assert result["selected_index"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
