#!uv run
# -*- encoding=utf8 -*-
"""
显示游戏画面的9个区域划分
用于方便选择OCR识别区域
"""

import argparse
import os
import sys
import tempfile
from typing import Optional

import cv2
import numpy as np
from airtest.core.api import auto_setup, snapshot
from PIL import Image, ImageDraw, ImageFont

from device_utils import connect_device_with_timeout
from emulator_manager import EmulatorManager
from logger_config import setup_logger_from_config
from vibe_ocr import OCRHelper

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 初始化日志
logger = setup_logger_from_config(use_color=True)


def _get_connection_string(emulator_name: Optional[str] = None) -> str:
    """
    获取连接字符串

    Args:
        emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'

    Returns:
        str: Airtest 连接字符串
    """
    if emulator_name:
        emulator_manager = EmulatorManager()

        # 获取设备列表
        devices = emulator_manager.get_adb_devices()
        if emulator_name not in devices:
            logger.warning(f"⚠️ 模拟器 {emulator_name} 不在设备列表中")
            logger.info(f"   可用设备: {list(devices.keys()) if devices else '无'}")
            raise RuntimeError(f"模拟器 {emulator_name} 不可用")

        connection_string = emulator_manager.get_emulator_connection_string(emulator_name)
        logger.info(f"📱 连接到模拟器: {emulator_name}")
        logger.info(f"   连接字符串: {connection_string}")
    else:
        connection_string = "Android:///"
        logger.info("📱 使用默认连接字符串")

    return connection_string


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
            (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)

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


def put_chinese_text(img, text, position, font_size, color=(0, 255, 0)):
    """
    使用 PIL 在图像上绘制中文文字

    Args:
        img: OpenCV 图像 (BGR)
        text: 要绘制的文字
        position: 文字位置 (x, y)
        font_size: 字体大小
        color: 文字颜色 (B, G, R)

    Returns:
        绘制了文字的图像
    """
    # 转换为 PIL Image (RGB)
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 尝试加载中文字体
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",  # Windows 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
        "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
        "/System/Library/Fonts/STHeiti Light.ttc",  # macOS 华文细黑
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux Droid Sans
    ]

    font = None
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    # PIL 使用 RGB，需要转换颜色
    color_rgb = (color[2], color[1], color[0])

    # 绘制文字
    draw.text(position, text, font=font, fill=color_rgb)

    # 转换回 OpenCV 格式 (BGR)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def recognize_and_overlay_text(image, ocr_helper):
    """
    识别图像上的所有文字，并用不透明底色覆盖原文字显示识别结果

    Args:
        image: 输入图像
        ocr_helper: OCR Helper 实例

    Returns:
        覆盖了文字的图像
    """
    result = image.copy()
    height, width = result.shape[:2]

    # 使用系统临时目录保存图像用于 OCR 识别
    temp_path = os.path.join(tempfile.gettempdir(), "ocr_temp.png")
    cv2.imwrite(temp_path, image)

    print("🔍 正在识别图像上的所有文字...")
    try:
        # 使用 OCRHelper 的 get_all_texts_from_image 方法获取所有文字
        all_texts = ocr_helper.get_all_texts_from_image(temp_path)

        if not all_texts or len(all_texts) == 0:
            print("⚠️  未识别到任何文字")
            return result

        text_count = 0
        # 遍历所有识别到的文字
        for text_info in all_texts:
            try:
                text = text_info["text"]
                confidence = text_info["confidence"]
                bbox = text_info["bbox"]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

                print(f"  📝 识别到: '{text}' (置信度: {confidence:.3f})")

                # 计算文字框的边界
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]
                x_min, x_max = int(min(x_coords)), int(max(x_coords))
                y_min, y_max = int(min(y_coords)), int(max(y_coords))

                # 绘制不透明的黑色背景（完全覆盖原文字）
                cv2.rectangle(result, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

                # 计算合适的字体大小
                box_height = y_max - y_min
                font_size = max(12, min(int(box_height * 0.8), 48))  # 字体大小

                # 计算文字位置（大致居中，PIL 的文字定位与 OpenCV 不同）
                text_x = x_min + 5  # 留一点边距
                text_y = y_min + (box_height - font_size) // 2

                # 确保文字不超出边界
                text_x = max(0, min(text_x, width - 20))
                text_y = max(0, min(text_y, height - font_size))

                # 使用 PIL 绘制中文文字
                result = put_chinese_text(result, text, (text_x, text_y), font_size, (0, 255, 0))

                # 在文字框上方显示置信度（如果低于95%）
                if confidence < 0.95:
                    conf_text = f"{confidence:.2f}"
                    conf_y = max(10, y_min - 5)
                    result = put_chinese_text(
                        result,
                        conf_text,
                        (x_min, conf_y),
                        max(10, font_size // 2),
                        (0, 255, 255),
                    )

                text_count += 1

            except Exception as e:
                print(f"⚠️  处理文字时出错: {e}")
                import traceback

                traceback.print_exc()
                continue

        print(f"✅ 成功识别并覆盖 {text_count} 个文字区域")

    except Exception as e:
        print(f"❌ OCR 识别失败: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return result


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="显示游戏画面的9个区域划分，用于方便选择OCR识别区域"
    )
    parser.add_argument(
        "--emulator",
        type=str,
        default=None,
        help="指定模拟器连接，如 '127.0.0.1:5555'。不指定则使用默认模拟器",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🎮 游戏画面区域划分工具")
    print("=" * 60 + "\n")

    # 初始化 OCR Helper
    print("🤖 初始化 OCR 引擎...")
    try:
        ocr_helper = OCRHelper(output_dir="output")
        print("✅ OCR 引擎初始化成功\n")
    except Exception as e:
        logger.error(f"❌ OCR 引擎初始化失败: {e}")
        sys.exit(1)

    # 连接设备
    print("📱 连接设备...")
    try:
        connection_string = _get_connection_string(args.emulator)
        auto_setup(__file__)
        connect_device_with_timeout(connection_string, timeout=30)
        print("✅ 设备连接成功\n")
    except Exception as e:
        logger.error(f"❌ 设备连接失败: {e}")
        sys.exit(1)

    # 截取当前画面
    print("📸 截取游戏画面...")
    try:
        screenshot_path = os.path.join(tempfile.gettempdir(), "game_screenshot.png")
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
    output_path = os.path.join(tempfile.gettempdir(), "game_regions.png")
    cv2.imwrite(output_path, result)
    print(f"✅ 区域划分图保存到: {output_path}\n")

    # 显示图像
    print("🖼️  显示区域划分图...")
    print("\n操作提示:")
    print("  - 按数字键 1-9: 高亮显示对应区域")
    print("  - 按 T 键: 切换文字识别模式")
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
    ocr_mode = False  # OCR 模式标志

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
            if ocr_mode:
                # OCR 模式下，直接在原图上识别并覆盖文字（不绘制区域分割）
                current_image = recognize_and_overlay_text(image, ocr_helper)
                current_image = highlight_region(current_image, region_num)
            else:
                current_image = draw_regions(image)
                current_image = highlight_region(current_image, region_num)
            highlighted_region = region_num

        # T 键切换文字识别模式
        elif key == ord("t") or key == ord("T"):
            ocr_mode = not ocr_mode
            if ocr_mode:
                print("📝 切换到文字识别模式（直接在原图上显示）")
                # 直接在原图上识别并覆盖文字，不绘制区域分割
                current_image = recognize_and_overlay_text(image, ocr_helper)
            else:
                print("🎨 切换到区域划分模式")
                current_image = draw_regions(image)
                if highlighted_region:
                    current_image = highlight_region(current_image, highlighted_region)

        # R 键刷新截图
        elif key == ord("r") or key == ord("R"):
            print("🔄 刷新截图...")
            try:
                snapshot(filename=screenshot_path)
                image = cv2.imread(screenshot_path)
                if ocr_mode:
                    # OCR 模式：直接在原图上识别文字
                    current_image = recognize_and_overlay_text(image, ocr_helper)
                else:
                    current_image = draw_regions(image)
                if highlighted_region:
                    current_image = highlight_region(current_image, highlighted_region)
                print("✅ 截图已刷新")
            except Exception as e:
                print(f"❌ 刷新失败: {e}")

        # S 键保存
        elif key == ord("s") or key == ord("S"):
            save_path = os.path.join(tempfile.gettempdir(), "game_regions_highlighted.png")
            cv2.imwrite(save_path, current_image)
            print(f"💾 图像已保存到: {save_path}")

        # 空格键重置
        elif key == ord(" "):
            print("🔄 重置视图")
            if ocr_mode:
                # OCR 模式：直接在原图上识别文字
                current_image = recognize_and_overlay_text(image, ocr_helper)
            else:
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
