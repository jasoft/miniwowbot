#!/usr/bin/env python3
"""测试找到文字时的日志输出"""

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

    # 设置其 logger 为 INFO 级别，这样只会看到重要信息
    ocr.logger.setLevel(logging.INFO)

    # 检查是否有现有的截图文件可以使用
    screenshots_dir = "images/screenshots"
    if os.path.exists(screenshots_dir):
        screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
        if screenshots:
            test_image = os.path.join(screenshots_dir, screenshots[0])
            print(f"\n使用截图: {test_image}")
            print("=" * 60)
            print("说明：")
            print("- DEBUG 级别的日志不会显示")
            print("- 只有找到文字时才会显示 INFO 级别的日志")
            print("- 每个找到的文字会显示在一行")
            print("=" * 60)

            # 先运行一次 OCR 来识别所有文字
            print("\n正在进行 OCR 识别...")
            json_file = ocr._perform_ocr(test_image)

            if json_file and os.path.exists(json_file):
                # 读取识别结果
                import json

                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 显示识别到的所有文字
                print("\n识别到的文字：")
                if isinstance(data, list):
                    texts = [item.get("rec_texts", []) for item in data]
                    texts = sum(texts, [])  # 展平列表
                else:
                    texts = data.get("rec_texts", [])

                for i, text in enumerate(texts[:10]):  # 只显示前10个
                    print(f"  {i + 1}. {text}")

                # 选择第一个文字来测试查找
                if texts:
                    test_word = texts[0]
                    print(f"\n测试查找第一个文字: '{test_word}'")
                    print("-" * 40)

                    # 查找这个文字
                    result = ocr.find_text_in_image(
                        test_image, test_word, use_cache=True, regions=[5]
                    )

                    print("\n再次查找相同文字（应该命中缓存）...")
                    result2 = ocr.find_text_in_image(
                        test_image, test_word, use_cache=True, regions=[5]
                    )

                    print("\n禁用缓存查找...")
                    result3 = ocr.find_text_in_image(
                        test_image, test_word, use_cache=False, regions=[5]
                    )

    else:
        print("截图目录不存在")


if __name__ == "__main__":
    main()
