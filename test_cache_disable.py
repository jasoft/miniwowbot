#!/usr/bin/env python3
"""测试缓存禁用功能"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def test_cache_disable():
    """测试禁用缓存时是否还会访问缓存"""

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="ocr_test_")
    print(f"临时目录: {temp_dir}")

    try:
        # 初始化OCR助手
        output_dir = os.path.join(temp_dir, "output")
        cache_dir = os.path.join(output_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)

        ocr = OCRHelper(
            output_dir=output_dir,
            max_cache_size=1000,  # 设置缓存大小
            hash_type="dhash",  # 使用 dHash
            hash_threshold=10,  # hash 阈值
        )

        # 创建一个测试图像文件
        test_image_path = os.path.join(temp_dir, "test.png")

        # 创建一个简单的测试图像（黑色背景，白色文字）
        import cv2
        import numpy as np

        # 创建图像
        img = np.ones((100, 200, 3), dtype=np.uint8) * 255  # 白色背景
        cv2.putText(img, "TEST", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.imwrite(test_image_path, img)

        print("\n=== 测试1: 启用缓存 ===")
        # 第一次调用，使用缓存
        print("第一次OCR（启用缓存）...")
        result1 = ocr.find_text_in_image(
            test_image_path,
            "TEST",
            use_cache=True,
            regions=[5],  # 中间区域
        )
        print(f"结果: {result1.get('found', False)}")

        # 第二次调用，应该命中缓存
        print("\n第二次OCR（启用缓存，应该命中）...")
        result2 = ocr.find_text_in_image(
            test_image_path, "TEST", use_cache=True, regions=[5]
        )
        print(f"结果: {result2.get('found', False)}")

        print("\n=== 测试2: 禁用缓存 ===")
        # 第三次调用，禁用缓存
        print("第三次OCR（禁用缓存，不应该使用缓存）...")
        result3 = ocr.find_text_in_image(
            test_image_path,
            "TEST",
            use_cache=False,  # 禁用缓存
            regions=[5],
        )
        print(f"结果: {result3.get('found', False)}")

        # 创建另一个略有不同的图像
        test_image_path2 = os.path.join(temp_dir, "test2.png")
        img2 = np.ones((100, 200, 3), dtype=np.uint8) * 255  # 白色背景
        cv2.putText(
            img2, "TEST", (51, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2
        )  # 略微偏移
        cv2.imwrite(test_image_path2, img2)

        print("\n=== 测试3: 禁用缓存时不同图像 ===")
        # 使用不同图像，禁用缓存
        print("第四次OCR（不同图像，禁用缓存）...")
        result4 = ocr.find_text_in_image(
            test_image_path2,
            "TEST",
            use_cache=False,  # 禁用缓存
            regions=[5],
        )
        print(f"结果: {result4.get('found', False)}")

        # 检查缓存目录中的文件
        cache_files = list(Path(cache_dir).glob("*"))
        print(f"\n缓存文件数量: {len(cache_files)}")
        for f in cache_files:
            print(f"  - {f.name}")

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        print(f"\n已清理临时目录: {temp_dir}")


if __name__ == "__main__":
    test_cache_disable()
