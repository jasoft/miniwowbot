#!/usr/bin/env python3
"""测试生产环境下的日志输出（仅 INFO 级别）"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def main():
    # 初始化OCR助手（默认为 INFO 级别）
    ocr = OCRHelper(output_dir="output")

    # 强制设置为 INFO 级别（模拟生产环境）
    import logging

    ocr.logger.setLevel(logging.INFO)
    for handler in ocr.logger.handlers:
        handler.setLevel(logging.INFO)

    print("=" * 60)
    print("生产环境日志输出（仅 INFO 级别）")
    print("=" * 60)
    print("注意：")
    print("- 只会显示找到文字时的 INFO 日志")
    print("- DEBUG 信息（缓存、耗时等）不会显示")
    print("- 日志输出更加简洁清晰")
    print("=" * 60)

    # 检查是否有现有的截图文件可以使用
    screenshots_dir = "images/screenshots"
    if os.path.exists(screenshots_dir):
        screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
        if screenshots:
            test_image = os.path.join(screenshots_dir, screenshots[0])
            print(f"\n使用截图: {os.path.basename(test_image)}")

            # 测试一些常见的字符
            test_chars = ["登", "录", "设", "置", "开", "始", "确", "认"]

            for char in test_chars:
                print(f"\n查找文字: '{char}'")
                result = ocr.find_text_in_image(
                    test_image,
                    char,
                    use_cache=True,
                    regions=[5, 6, 8],  # 搜索多个区域
                )

                # 如果找到了，会显示一行简洁的 INFO 日志
                # 如果没找到，不会显示任何内容

    else:
        print("截图目录不存在")

    print("\n" + "=" * 60)
    print("日志优化总结：")
    print("1. 大部分调试信息改为 DEBUG 级别")
    print("2. 只在找到文字时输出 INFO 日志")
    print("3. 每个匹配信息一行显示，包含：")
    print("   - 文字内容")
    print("   - 置信度")
    print("   - 位置坐标")
    print("   - 是否使用缓存")
    print("   - OCR 耗时（如果非缓存）")
    print("=" * 60)


if __name__ == "__main__":
    main()
