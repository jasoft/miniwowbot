#!/usr/bin/env python3
"""简单测试缓存禁用功能"""

import os
import sys
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def main():
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="ocr_test_")
    print(f"临时目录: {temp_dir}")

    try:
        # 初始化OCR助手
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        ocr = OCRHelper(output_dir=output_dir)

        # 检查是否有现有的截图文件可以使用
        screenshots_dir = "images/screenshots"
        if os.path.exists(screenshots_dir):
            screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
            if screenshots:
                test_image = os.path.join(screenshots_dir, screenshots[0])
                print(f"\n使用现有截图: {test_image}")

                # 测试启用缓存
                print("\n=== 测试启用缓存 ===")
                result1 = ocr.find_text_in_image(
                    test_image,
                    "设置",  # 常见的文字
                    use_cache=True,
                    regions=[8],  # 右下角区域
                )
                print(f"结果1 (启用缓存): {result1.get('found', False)}")

                # 测试禁用缓存
                print("\n=== 测试禁用缓存 ===")
                result2 = ocr.find_text_in_image(
                    test_image,
                    "设置",  # 相同的文字
                    use_cache=False,  # 禁用缓存
                    regions=[8],
                )
                print(f"结果2 (禁用缓存): {result2.get('found', False)}")
            else:
                print("没有找到截图文件")
        else:
            print("截图目录不存在")

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        print(f"\n已清理临时目录")


if __name__ == "__main__":
    main()
