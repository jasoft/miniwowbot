#!/usr/bin/env python3
"""测试日志输出优化"""

import os
import sys
import tempfile
import shutil
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def test_log_output():
    """测试优化后的日志输出"""

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="ocr_log_test_")
    print(f"临时目录: {temp_dir}")

    try:
        # 初始化OCR助手
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        # 设置日志级别为 INFO，这样可以看到我们想要的信息
        logging.basicConfig(level=logging.INFO)

        ocr = OCRHelper(output_dir=output_dir)

        # 检查是否有现有的截图文件可以使用
        screenshots_dir = "images/screenshots"
        if os.path.exists(screenshots_dir):
            screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
            if screenshots:
                test_image = os.path.join(screenshots_dir, screenshots[0])
                print(f"\n使用现有截图: {test_image}")

                print("\n=== 测试1: 启用缓存 ===")
                # 第一次调用，使用缓存
                print("第一次OCR（启用缓存）...")
                result1 = ocr.find_text_in_image(
                    test_image,
                    "设置",  # 常见的文字
                    use_cache=True,
                    regions=[8],  # 右下角区域
                )

                print("\n第二次OCR（启用缓存，应该命中缓存）...")
                result2 = ocr.find_text_in_image(
                    test_image,
                    "设置",  # 相同的文字
                    use_cache=True,
                    regions=[8],
                )

                print("\n=== 测试2: 禁用缓存 ===")
                # 第三次调用，禁用缓存
                print("第三次OCR（禁用缓存）...")
                result3 = ocr.find_text_in_image(
                    test_image,
                    "设置",  # 相同的文字
                    use_cache=False,  # 禁用缓存
                    regions=[8],
                )

                print("\n=== 测试3: 查找其他文字 ===")
                print("查找其他文字（启用缓存）...")
                result4 = ocr.find_text_in_image(
                    test_image,
                    "开始",  # 另一个常见的文字
                    use_cache=True,
                    regions=[5],  # 中间区域
                )

                print("\n=== 日志输出总结 ===")
                print("1. 只有找到文字时才会输出 INFO 级别的日志")
                print("2. 未找到文字时输出 DEBUG 级别的日志")
                print("3. 缓存相关信息改为 DEBUG 级别")
                print("4. 每个找到的文字只输出一行，包含：")
                print("   - 文字内容")
                print("   - 置信度")
                print("   - 位置")
                print("   - 是否使用缓存")
                print("   - 耗时（如果有的话）")

            else:
                print("没有找到截图文件")
        else:
            print("截图目录不存在")

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        print(f"\n已清理临时目录")


if __name__ == "__main__":
    test_log_output()
