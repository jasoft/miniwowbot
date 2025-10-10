#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
显示游戏画面的9个区域划分
用于方便选择OCR识别区域
"""

import sys
import os
import cv2
from airtest.core.api import connect_device, auto_setup, snapshot

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def draw_regions(image):
    """
    在图像上绘制9个区域的划分线和编号

    区域编号：
    1 2 3
    4 5 6
    7 8 9

    Args:
        image: 输入图像

    Returns:
        绘制了区域划分的图像
    """
    height, width = image.shape[:2]
    result = image.copy()

    # 计算每个格子的大小
    cell_height = height // 3
    cell_width = width // 3

    # 定义颜色
    line_color = (0, 255, 0)  # 绿色
    text_color = (255, 255, 0)  # 青色
    bg_color = (0, 0, 0)  # 黑色背景

    # 绘制垂直分割线
    for i in range(1, 3):
        x = i * cell_width
        cv2.line(result, (x, 0), (x, height), line_color, 2)

    # 绘制水平分割线
    for i in range(1, 3):
        y = i * cell_height
        cv2.line(result, (0, y), (width, y), line_color, 2)

    # 在每个区域中心绘制编号
    region_num = 1
    for row in range(3):
        for col in range(3):
            # 计算区域中心
            center_x = col * cell_width + cell_width // 2
            center_y = row * cell_height + cell_height // 2

            # 绘制编号文字
            text = str(region_num)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 3
            thickness = 5

            # 获取文字大小
            (text_width, text_height), baseline = cv2.getTextSize(
                text, font, font_scale, thickness
            )

            # 计算文字位置（居中）
            text_x = center_x - text_width // 2
            text_y = center_y + text_height // 2

            # 绘制文字背景（黑色矩形）
            padding = 10
            cv2.rectangle(
                result,
                (text_x - padding, text_y - text_height - padding),
                (text_x + text_width + padding, text_y + baseline + padding),
                bg_color,
                -1,
            )

            # 绘制文字
            cv2.putText(
                result,
                text,
                (text_x, text_y),
                font,
                font_scale,
                text_color,
                thickness,
            )

            # 绘制区域边界框（半透明）
            overlay = result.copy()
            x1 = col * cell_width
            y1 = row * cell_height
            x2 = x1 + cell_width if col < 2 else width
            y2 = y1 + cell_height if row < 2 else height

            cv2.rectangle(overlay, (x1, y1), (x2, y2), line_color, 2)
            cv2.addWeighted(overlay, 0.3, result, 0.7, 0, result)

            region_num += 1

    # 在顶部添加说明文字
    info_text = "Region Layout (1-9)"
    cv2.putText(
        result,
        info_text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )

    # 在底部添加操作提示
    help_text = "Press any key to close | ESC to exit"
    cv2.putText(
        result,
        help_text,
        (10, height - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    return result


def show_region_details(image):
    """
    显示每个区域的详细信息

    Args:
        image: 输入图像
    """
    height, width = image.shape[:2]
    cell_height = height // 3
    cell_width = width // 3

    print("\n" + "=" * 60)
    print("区域划分详情")
    print("=" * 60)
    print(f"图像尺寸: {width}x{height}")
    print(f"单元格尺寸: {cell_width}x{cell_height}")
    print("\n区域坐标 (x, y, width, height):")
    print("-" * 60)

    region_num = 1
    for row in range(3):
        for col in range(3):
            x = col * cell_width
            y = row * cell_height
            w = cell_width if col < 2 else (width - x)
            h = cell_height if row < 2 else (height - y)

            print(f"区域 {region_num}: ({x:4d}, {y:4d}, {w:4d}, {h:4d})")
            region_num += 1

    print("=" * 60 + "\n")


def highlight_region(image, region_num):
    """
    高亮显示指定区域

    Args:
        image: 输入图像
        region_num: 区域编号 (1-9)

    Returns:
        高亮显示指定区域的图像
    """
    if region_num < 1 or region_num > 9:
        return image

    height, width = image.shape[:2]
    result = image.copy()

    # 计算每个格子的大小
    cell_height = height // 3
    cell_width = width // 3

    # 计算区域位置
    row = (region_num - 1) // 3
    col = (region_num - 1) % 3

    x = col * cell_width
    y = row * cell_height
    w = cell_width if col < 2 else (width - x)
    h = cell_height if row < 2 else (height - y)

    # 创建半透明的高亮层
    overlay = result.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 255), -1)
    cv2.addWeighted(overlay, 0.3, result, 0.7, 0, result)

    # 绘制边框
    cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 255), 3)

    # 显示区域信息
    info_text = f"Region {region_num}: ({x}, {y}, {w}, {h})"
    cv2.putText(
        result,
        info_text,
        (10, height - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 255),
        2,
    )

    return result


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🎮 游戏画面区域划分工具")
    print("=" * 60 + "\n")

    # 连接设备
    print("📱 连接设备...")
    try:
        connect_device("Android:///")
        auto_setup(__file__)
        print("✅ 设备连接成功\n")
    except Exception as e:
        print(f"❌ 设备连接失败: {e}")
        sys.exit(1)

    # 截取当前画面
    print("📸 截取游戏画面...")
    try:
        screenshot_path = "/tmp/game_screenshot.png"
        snapshot(filename=screenshot_path)
        print(f"✅ 截图保存到: {screenshot_path}\n")
    except Exception as e:
        print(f"❌ 截图失败: {e}")
        sys.exit(1)

    # 读取截图
    image = cv2.imread(screenshot_path)
    if image is None:
        print(f"❌ 无法读取截图: {screenshot_path}")
        sys.exit(1)

    # 显示区域详情
    show_region_details(image)

    # 绘制区域划分
    print("🎨 绘制区域划分...")
    result = draw_regions(image)

    # 保存结果
    output_path = "/tmp/game_regions.png"
    cv2.imwrite(output_path, result)
    print(f"✅ 区域划分图保存到: {output_path}\n")

    # 显示图像
    print("🖼️  显示区域划分图...")
    print("\n操作提示:")
    print("  - 按数字键 1-9: 高亮显示对应区域")
    print("  - 按 R 键: 刷新截图")
    print("  - 按 S 键: 保存当前图像")
    print("  - 按 ESC 或 Q 键: 退出")
    print()

    # 创建窗口
    window_name = "Game Regions (1-9)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # 调整窗口大小以适应屏幕
    screen_height = 1000  # 假设屏幕高度
    if result.shape[0] > screen_height:
        scale = screen_height / result.shape[0]
        new_width = int(result.shape[1] * scale)
        new_height = int(result.shape[0] * scale)
        cv2.resizeWindow(window_name, new_width, new_height)

    # 显示图像并等待按键
    current_image = result.copy()
    highlighted_region = None

    while True:
        cv2.imshow(window_name, current_image)
        key = cv2.waitKey(0) & 0xFF

        # ESC 或 Q 键退出
        if key == 27 or key == ord("q") or key == ord("Q"):
            break

        # 数字键 1-9 高亮区域
        elif ord("1") <= key <= ord("9"):
            region_num = key - ord("0")
            print(f"🔍 高亮区域 {region_num}")
            current_image = draw_regions(image)
            current_image = highlight_region(current_image, region_num)
            highlighted_region = region_num

        # R 键刷新截图
        elif key == ord("r") or key == ord("R"):
            print("🔄 刷新截图...")
            try:
                snapshot(filename=screenshot_path)
                image = cv2.imread(screenshot_path)
                current_image = draw_regions(image)
                if highlighted_region:
                    current_image = highlight_region(current_image, highlighted_region)
                print("✅ 截图已刷新")
            except Exception as e:
                print(f"❌ 刷新失败: {e}")

        # S 键保存
        elif key == ord("s") or key == ord("S"):
            save_path = "/tmp/game_regions_highlighted.png"
            cv2.imwrite(save_path, current_image)
            print(f"💾 图像已保存到: {save_path}")

        # 空格键重置
        elif key == ord(" "):
            print("🔄 重置视图")
            current_image = draw_regions(image)
            highlighted_region = None

    # 关闭窗口
    cv2.destroyAllWindows()

    print("\n✅ 完成！")
    print(f"📁 截图文件: {screenshot_path}")
    print(f"📁 区域划分图: {output_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
