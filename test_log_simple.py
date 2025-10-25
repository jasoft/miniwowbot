#!/usr/bin/env python3
"""简单测试日志输出"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def main():
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

            # 测试查找可能存在的文字
            test_words = [
                "设置",
                "开始",
                "确认",
                "取消",
                "返回",
                "进入",
                "战斗",
                "背包",
            ]

            for word in test_words:
                print(f"\n查找文字: '{word}'")
                result = ocr.find_text_in_image(
                    test_image,
                    word,
                    use_cache=True,
                    regions=[5, 6, 8, 9],  # 搜索多个区域
                )

                # 结果会在 logger 中输出
                if result.get("found"):
                    print(f"✓ 找到了！")
                else:
                    print(f"  未找到")

    else:
        print("截图目录不存在")


if __name__ == "__main__":
    main()
