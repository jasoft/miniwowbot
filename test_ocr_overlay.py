#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 OCR 文字识别和覆盖功能
使用本地图片测试，不需要连接设备
"""

import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper  # noqa: E402


def put_chinese_text(img, text, position, font_size, color=(0, 255, 0)):
    """使用 PIL 在图像上绘制中文文字"""
    # 转换为 PIL Image (RGB)
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 尝试加载中文字体
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/STHeiti Light.ttc", font_size
            )
        except Exception:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                    font_size,
                )
            except Exception:
                font = ImageFont.load_default()

    # PIL 使用 RGB，需要转换颜色
    color_rgb = (color[2], color[1], color[0])
    draw.text(position, text, font=font, fill=color_rgb)

    # 转换回 OpenCV 格式 (BGR)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def recognize_and_overlay_text(image, ocr_helper):
    """识别并覆盖显示所有文字"""
    result = image.copy()
    height, width = result.shape[:2]

    temp_path = "/tmp/ocr_temp.png"
    cv2.imwrite(temp_path, image)

    print("🔍 正在识别图像上的所有文字...")
    try:
        all_texts = ocr_helper.get_all_texts_from_image(temp_path)

        if not all_texts:
            print("⚠️  未识别到任何文字")
            return result

        print(f"✅ 识别到 {len(all_texts)} 个文字")

        for text_info in all_texts:
            text = text_info["text"]
            confidence = text_info["confidence"]
            bbox = text_info["bbox"]

            print(f"  📝 '{text}' (置信度: {confidence:.3f})")

            # 计算边界
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            x_min, x_max = int(min(x_coords)), int(max(x_coords))
            y_min, y_max = int(min(y_coords)), int(max(y_coords))

            # 黑色背景覆盖原文字
            cv2.rectangle(result, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

            # 计算字体大小
            box_height = y_max - y_min
            font_size = max(12, min(int(box_height * 0.8), 48))

            # 计算位置
            text_x = x_min + 5
            text_y = y_min + (box_height - font_size) // 2
            text_x = max(0, min(text_x, width - 20))
            text_y = max(0, min(text_y, height - font_size))

            # 使用PIL绘制中文
            result = put_chinese_text(
                result, text, (text_x, text_y), font_size, (0, 255, 0)
            )

            # 低置信度显示分数
            if confidence < 0.95:
                conf_y = max(10, y_min - 5)
                result = put_chinese_text(
                    result,
                    f"{confidence:.2f}",
                    (x_min, conf_y),
                    max(10, font_size // 2),
                    (0, 255, 255),
                )

    except Exception as e:
        print(f"❌ OCR 识别失败: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return result


def main():
    print("\n" + "=" * 60)
    print("🔤 OCR 文字识别覆盖测试")
    print("=" * 60 + "\n")

    test_paths = [
        "images/screenshots/Screenshot_20251008-155637.png",
        "images/screenshots/Screenshot_20251008-160246.png",
        "images/screenshots/Screenshot_20251008-161048.png",
    ]

    test_image = None
    for path in test_paths:
        if os.path.exists(path):
            test_image = path
            break

    if not test_image:
        print("❌ 未找到测试图片")
        sys.exit(1)

    print(f"📁 使用测试图片: {test_image}\n")

    print("🤖 初始化 OCR 引擎...")
    ocr_helper = OCRHelper(output_dir="output")
    print("✅ OCR 引擎初始化成功\n")

    image = cv2.imread(test_image)
    print(f"📖 图片尺寸: {image.shape[1]}x{image.shape[0]}\n")

    result = recognize_and_overlay_text(image, ocr_helper)

    output_path = "/tmp/ocr_overlay_result.png"
    cv2.imwrite(output_path, result)
    print(f"\n💾 结果已保存到: {output_path}")

    print("\n🖼️  显示结果 (按任意键关闭)...\n")
    cv2.namedWindow("OCR Overlay Result", cv2.WINDOW_NORMAL)
    if result.shape[0] > 1000:
        scale = 1000 / result.shape[0]
        cv2.resizeWindow("OCR Overlay Result", int(result.shape[1] * scale), 1000)
    cv2.imshow("OCR Overlay Result", result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("✅ 完成！\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
