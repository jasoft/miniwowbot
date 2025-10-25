#!/usr/bin/env python3
"""最终测试日志输出优化"""

import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def main():
    # 设置全局日志级别为 INFO
    logging.basicConfig(level=logging.INFO)

    # 初始化OCR助手
    ocr = OCRHelper(output_dir="output")

    # 检查是否有现有的截图文件可以使用
    screenshots_dir = "images/screenshots"
    if os.path.exists(screenshots_dir):
        screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
        if screenshots:
            test_image = os.path.join(screenshots_dir, screenshots[0])
            print(f"\n使用截图: {test_image}")
            print("=" * 60)
            print("日志优化效果：")
            print("- DEBUG 级别的信息不会显示")
            print("- 只有找到文字时才会显示一行简洁的 INFO 信息")
            print("- 包含：文字、置信度、位置、缓存状态、耗时")
            print("=" * 60)

            # 查找单个字符，这样更容易找到
            print("\n测试1: 查找单个字符（使用缓存）")
            result = ocr.find_text_in_image(
                test_image,
                "登",  # 单个字符
                use_cache=True,
                regions=[5],  # 中间区域
            )

            print("\n测试2: 再次查找相同字符（应该命中缓存）")
            result = ocr.find_text_in_image(
                test_image,
                "登",  # 相同的字符
                use_cache=True,
                regions=[5],
            )

            print("\n测试3: 禁用缓存查找")
            result = ocr.find_text_in_image(
                test_image,
                "登",  # 相同的字符
                use_cache=False,  # 禁用缓存
                regions=[5],
            )

            print("\n测试4: 查找其他字符")
            result = ocr.find_text_in_image(
                test_image,
                "录",  # 另一个字符
                use_cache=True,
                regions=[5],
            )

            print("\n测试5: 查找数字")
            result = ocr.find_text_in_image(
                test_image,
                "1",  # 数字
                use_cache=True,
                regions=[5],
            )

    else:
        print("截图目录不存在")


if __name__ == "__main__":
    main()
