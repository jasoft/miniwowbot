#!/usr/bin/env python3
"""测试日志输出 - 显示所有级别"""

import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def main():
    # 设置全局日志级别为 DEBUG
    logging.basicConfig(level=logging.DEBUG)

    # 初始化OCR助手
    ocr = OCRHelper(output_dir="output")

    # 设置其 logger 为 DEBUG 级别
    ocr.logger.setLevel(logging.DEBUG)

    print(f"Logger 级别: {ocr.logger.level}")
    print(f"Logger handlers: {ocr.logger.handlers}")
    print(f"Logger effective level: {ocr.logger.getEffectiveLevel()}")

    # 测试日志输出
    ocr.logger.debug("这是一条 DEBUG 消息")
    ocr.logger.info("这是一条 INFO 消息")
    ocr.logger.warning("这是一条 WARNING 消息")

    # 检查是否有现有的截图文件可以使用
    screenshots_dir = "images/screenshots"
    if os.path.exists(screenshots_dir):
        screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
        if screenshots:
            test_image = os.path.join(screenshots_dir, screenshots[0])
            print(f"\n使用截图: {test_image}")
            print("=" * 60)

            # 测试查找单个字符
            print("\n查找文字: '设'")
            result = ocr.find_text_in_image(
                test_image,
                "设",
                use_cache=True,
                regions=[5],  # 只搜索中间区域
            )

            print(f"\n查找结果: {result.get('found', False)}")

    else:
        print("截图目录不存在")


if __name__ == "__main__":
    main()
