#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
OCR 区域可视化脚本
读取图片，识别每个区域的文字，并生成标注图片
"""

import sys
import os
import cv2
import numpy as np

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def draw_text_boxes(image, ocr_results, region_id, color):
    """
    在图像上绘制文字边界框

    Args:
        image: OpenCV 图像
        ocr_results: OCR 识别结果列表
        region_id: 区域编号
        color: 边界框颜色 (B, G, R)
    """
    for res in ocr_results:
        try:
            # 支持字典访问（OCRResult 对象）
            rec_texts = res["rec_texts"]
            rec_scores = res["rec_scores"]
            dt_polys = res["dt_polys"]
        except (KeyError, TypeError):
            # 尝试属性访问
            rec_texts = res.rec_texts if hasattr(res, "rec_texts") else []
            rec_scores = res.rec_scores if hasattr(res, "rec_scores") else []
            dt_polys = res.dt_polys if hasattr(res, "dt_polys") else []

        # 绘制每个识别到的文字
        for i, (text, score, bbox) in enumerate(zip(rec_texts, rec_scores, dt_polys)):
            if score < 0.5:  # 跳过低置信度的结果
                continue

            # 转换为整数坐标
            points = np.array(bbox, dtype=np.int32)

            # 绘制边界框
            cv2.polylines(image, [points], True, color, 2)

            # 计算中心点
            center_x = int((bbox[0][0] + bbox[2][0]) / 2)
            center_y = int((bbox[0][1] + bbox[2][1]) / 2)

            # 绘制中心点
            cv2.circle(image, (center_x, center_y), 3, color, -1)

            # 准备标注文本
            label = f"{text} ({center_x},{center_y})"

            # 计算文本位置（在边界框上方）
            text_x = int(bbox[0][0])
            text_y = int(bbox[0][1]) - 5

            # 绘制文本背景
            (text_w, text_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                image,
                (text_x, text_y - text_h - 2),
                (text_x + text_w, text_y + 2),
                color,
                -1,
            )

            # 绘制文本
            cv2.putText(
                image,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )


def visualize_all_regions(image_path, output_path):
    """
    可视化所有区域的 OCR 识别结果

    Args:
        image_path: 输入图像路径
        output_path: 输出图像路径
    """
    # 创建 OCR Helper
    ocr = OCRHelper(output_dir="output")

    # 读取图像
    if not os.path.exists(image_path):
        print(f"❌ 图像文件不存在: {image_path}")
        return

    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 无法读取图像: {image_path}")
        return

    height, width = image.shape[:2]
    print(f"✅ 图像尺寸: {width}x{height}")

    # 创建输出图像（复制原图）
    output_image = image.copy()

    # 定义每个区域的颜色（BGR 格式）
    region_colors = {
        1: (255, 0, 0),  # 蓝色
        2: (0, 255, 0),  # 绿色
        3: (0, 0, 255),  # 红色
        4: (255, 255, 0),  # 青色
        5: (255, 0, 255),  # 品红
        6: (0, 255, 255),  # 黄色
        7: (128, 0, 128),  # 紫色
        8: (255, 128, 0),  # 橙色
        9: (0, 128, 255),  # 天蓝色
    }

    # 绘制区域分割线
    grid_color = (200, 200, 200)  # 灰色

    # 垂直分割线
    cv2.line(output_image, (width // 3, 0), (width // 3, height), grid_color, 1)
    cv2.line(output_image, (width * 2 // 3, 0), (width * 2 // 3, height), grid_color, 1)

    # 水平分割线
    cv2.line(output_image, (0, height // 3), (width, height // 3), grid_color, 1)
    cv2.line(
        output_image, (0, height * 2 // 3), (width, height * 2 // 3), grid_color, 1
    )

    # 标注区域编号
    region_positions = [
        (width // 6, height // 6),  # 区域 1
        (width // 2, height // 6),  # 区域 2
        (width * 5 // 6, height // 6),  # 区域 3
        (width // 6, height // 2),  # 区域 4
        (width // 2, height // 2),  # 区域 5
        (width * 5 // 6, height // 2),  # 区域 6
        (width // 6, height * 5 // 6),  # 区域 7
        (width // 2, height * 5 // 6),  # 区域 8
        (width * 5 // 6, height * 5 // 6),  # 区域 9
    ]

    for region_id in range(1, 10):
        pos = region_positions[region_id - 1]
        color = region_colors[region_id]

        # 绘制区域编号
        cv2.putText(
            output_image,
            f"R{region_id}",
            (pos[0] - 15, pos[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    # 对每个区域进行 OCR 识别
    print("\n🔍 开始识别各个区域的文字...\n")

    total_texts = 0
    for region_id in range(1, 10):
        print(f"📍 区域 {region_id}:")

        # 提取区域
        region_img, offset = ocr._extract_region(
            image,
            regions=[region_id],
            debug_save_path=f"/tmp/region_{region_id}_debug.png",
        )

        if region_img is None:
            print("   ❌ 区域提取失败")
            continue

        # 进行 OCR 识别
        result = ocr.ocr.predict(region_img)

        if not result or len(result) == 0:
            print("   ⚠️ 未识别到文字")
            continue

        # 统计识别到的文字数量
        text_count = 0
        for res in result:
            try:
                rec_texts = res["rec_texts"]
                text_count += len(rec_texts)
            except (KeyError, TypeError):
                rec_texts = res.rec_texts if hasattr(res, "rec_texts") else []
                text_count += len(rec_texts)

        print(f"   ✅ 识别到 {text_count} 个文字")
        total_texts += text_count

        # 调整坐标并绘制到输出图像
        for res in result:
            try:
                rec_texts = res["rec_texts"]
                rec_scores = res["rec_scores"]
                dt_polys = res["dt_polys"]
            except (KeyError, TypeError):
                rec_texts = res.rec_texts if hasattr(res, "rec_texts") else []
                rec_scores = res.rec_scores if hasattr(res, "rec_scores") else []
                dt_polys = res.dt_polys if hasattr(res, "dt_polys") else []

            # 调整坐标到原图
            adjusted_polys = []
            for poly in dt_polys:
                adjusted_poly = [
                    [int(p[0] + offset[0]), int(p[1] + offset[1])] for p in poly
                ]
                adjusted_polys.append(adjusted_poly)

            # 绘制文字边界框
            color = region_colors[region_id]
            for i, (text, score, bbox) in enumerate(
                zip(rec_texts, rec_scores, adjusted_polys)
            ):
                if score < 0.5:
                    continue

                # 转换为整数坐标
                points = np.array(bbox, dtype=np.int32)

                # 绘制边界框
                cv2.polylines(output_image, [points], True, color, 2)

                # 计算中心点
                center_x = int((bbox[0][0] + bbox[2][0]) / 2)
                center_y = int((bbox[0][1] + bbox[2][1]) / 2)

                # 绘制中心点
                cv2.circle(output_image, (center_x, center_y), 4, color, -1)

                # 准备标注文本
                label = f"{text}({center_x},{center_y})"

                # 计算文本位置（在边界框上方）
                text_x = int(bbox[0][0])
                text_y = int(bbox[0][1]) - 8

                # 确保文本不超出图像边界
                if text_y < 15:
                    text_y = int(bbox[2][1]) + 20

                # 绘制文本背景
                (text_w, text_h), _ = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                cv2.rectangle(
                    output_image,
                    (text_x, text_y - text_h - 2),
                    (text_x + text_w, text_y + 2),
                    color,
                    -1,
                )

                # 绘制文本
                cv2.putText(
                    output_image,
                    label,
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                )

                print(
                    f"      - '{text}' at ({center_x}, {center_y}) [置信度: {score:.2f}]"
                )

    # 保存输出图像
    cv2.imwrite(output_path, output_image)
    print(f"\n✅ 总共识别到 {total_texts} 个文字")
    print(f"✅ 标注图像已保存到: {output_path}")

    # 同时保存一个缩放版本（方便查看）
    scale = 0.5
    small_image = cv2.resize(output_image, None, fx=scale, fy=scale)
    small_output_path = output_path.replace(".png", "_small.png")
    cv2.imwrite(small_output_path, small_image)
    print(f"✅ 缩放图像已保存到: {small_output_path}")


def main():
    """主函数"""
    image_path = "/tmp/screenshot.png"
    output_path = "/tmp/screenshot_annotated.png"

    print("=" * 60)
    print("OCR 区域可视化工具")
    print("=" * 60)

    visualize_all_regions(image_path, output_path)

    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
