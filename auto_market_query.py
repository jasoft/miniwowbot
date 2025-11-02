"""
自动化市场查询脚本
每 5 秒点击一次查询按钮，识别全屏幕文字，匹配一口价金币数量
如果金币数 < 100k，自动点击一口价按钮并确定
"""

import time
import sys
import os
import logging
import re
from typing import Optional, Tuple

from airtest.core.api import (
    auto_setup,
    connect_device,
    touch,
    sleep,
    start_app,
)

# 导入通用日志配置模块
from logger_config import setup_logger_from_config
from ocr_helper import OCRHelper
from emulator_manager import EmulatorManager

logging.getLogger("airtest").setLevel(logging.ERROR)
# 设置日志
logger = setup_logger_from_config(use_color=True)

# 全局变量
ocr_helper = None
emulator_manager = None


def initialize_device_and_ocr(emulator_name: Optional[str] = None):
    """
    初始化设备连接和OCR助手

    Args:
        emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'
    """
    global ocr_helper, emulator_manager

    # 确定连接字符串
    if emulator_name:
        if emulator_manager is None:
            emulator_manager = EmulatorManager()

        # 获取设备列表
        devices = emulator_manager.get_adb_devices()
        if emulator_name not in devices:
            logger.warning(f"⚠️ 模拟器 {emulator_name} 不在设备列表中")
            logger.info(f"   可用设备: {list(devices.keys()) if devices else '无'}")
            raise RuntimeError(f"模拟器 {emulator_name} 不可用")

        connection_string = emulator_manager.get_emulator_connection_string(
            emulator_name
        )
        logger.info(f"📱 连接到模拟器: {emulator_name}")
    else:
        connection_string = "Android:///"
        logger.info("📱 使用默认连接字符串")

    # 连接设备
    try:
        auto_setup(__file__)
        logger.info("自动配置设备中...")
        connect_device(connection_string)
        logger.info("   ✅ 成功连接到设备")
    except Exception as e:
        logger.error(f"   ❌ 连接设备失败: {e}")
        raise

    if ocr_helper is None:
        ocr_helper = OCRHelper(output_dir="output")


def parse_gold_amount(text: str) -> Optional[int]:
    """
    从文本中解析金币数量
    支持以下格式:
    - "2000k" -> 2000000
    - "89888" -> 89888
    - "2.5k" -> 2500

    Args:
        text: 要解析的文本

    Returns:
        金币数量（整数），如果解析失败返回 None
    """
    # 移除空格
    text = text.strip()

    # 匹配 "XXXk" 或 "XXX" 的模式
    match = re.search(r"(\d+(?:\.\d+)?)\s*k?", text)
    if match:
        amount_str = match.group(1)
        try:
            amount = float(amount_str)
            # 检查是否有 'k' 后缀
            if "k" in text[match.start() : match.end()]:
                amount *= 1000
            return int(amount)
        except ValueError:
            return None
    return None


def find_gold_price_text() -> Optional[dict]:
    """
    查找全屏幕中的一口价按钮及其旁边的价格信息

    Returns:
        包含价格信息的字典，格式:
        {
            "found": bool,
            "price": int,  # 金币数量
            "price_text": str,  # 原始价格文本
            "button_pos": tuple,  # 一口价按钮位置
            "price_pos": tuple,  # 价格文本位置
        }
        如果未找到返回 None
    """
    if ocr_helper is None:
        logger.error("❌ OCR助手未初始化")
        return None

    try:
        # 截图并获取全屏幕的所有文字
        import tempfile
        import uuid
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        screenshot_path = os.path.join(
            tempfile.gettempdir(), f"market_screenshot_{timestamp}_{unique_id}.png"
        )

        # 截图
        from airtest.core.api import snapshot

        snapshot(filename=screenshot_path)

        # 获取全屏幕的所有文字
        all_texts = ocr_helper.get_all_texts_from_image(screenshot_path)

        if not all_texts:
            logger.warning("⚠️ 未识别到任何文字")
            return None

        # 查找"一口价"按钮
        button_index = None
        button_pos = None

        for i, text_info in enumerate(all_texts):
            if "一口价" in text_info["text"]:
                button_index = i
                button_pos = text_info["center"]
                logger.info(
                    f"✅ 找到一口价按钮: {text_info['text']} 位置: {button_pos}"
                )
                break

        if button_index is None:
            logger.warning("⚠️ 未找到一口价按钮")
            return None

        # 查找一口价按钮右侧的价格信息
        # 价格通常在按钮的右侧，我们查找距离最近的数字文本
        button_x, button_y = button_pos

        best_price_info = None
        best_distance = float("inf")

        for i, text_info in enumerate(all_texts):
            if i == button_index:
                continue

            text = text_info["text"].strip()

            # 检查是否是价格文本（包含数字和可能的 'k'）
            if re.search(r"\d+", text):
                price_x, price_y = text_info["center"]

                # 计算距离（优先考虑右侧的文本，且 Y 坐标接近）
                # 如果在右侧（x > button_x）且 Y 坐标接近（|y - button_y| < 50）
                if price_x > button_x and abs(price_y - button_y) < 50:
                    distance = price_x - button_x
                    if distance < best_distance:
                        best_distance = distance
                        best_price_info = text_info

        if best_price_info is None:
            logger.warning("⚠️ 未找到价格信息")
            return None

        price_text = best_price_info["text"].strip()
        price_pos = best_price_info["center"]

        # 解析价格
        price = parse_gold_amount(price_text)

        if price is None:
            logger.warning(f"⚠️ 无法解析价格: {price_text}")
            return None

        logger.info(f"💰 识别到价格: {price_text} ({price} 金币) 位置: {price_pos}")

        # 清理临时截图
        try:
            os.remove(screenshot_path)
        except Exception:
            pass

        return {
            "found": True,
            "price": price,
            "price_text": price_text,
            "button_pos": button_pos,
            "price_pos": price_pos,
        }

    except Exception as e:
        logger.error(f"❌ OCR 查找失败: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


def click_query_button(query_button_pos: Tuple[int, int]):
    """
    点击查询按钮

    Args:
        query_button_pos: 查询按钮的坐标 (x, y)
    """
    try:
        touch(query_button_pos)
        logger.info(f"🔍 点击查询按钮: {query_button_pos}")
        sleep(1)  # 等待界面刷新
    except Exception as e:
        logger.error(f"❌ 点击查询按钮失败: {e}")


def click_one_key_price_button(text_pos: Tuple[int, int]):
    """
    点击一口价按钮
    根据文字位置计算按钮位置: x+400, y-30

    Args:
        text_pos: 文字位置的坐标 (x, y)
    """
    button_x = text_pos[0] + 400
    button_y = text_pos[1] - 30

    try:
        touch((button_x, button_y))
        logger.info(f"💰 点击一口价按钮: ({button_x}, {button_y})")
        sleep(1)
    except Exception as e:
        logger.error(f"❌ 点击一口价按钮失败: {e}")


def click_confirm_button(confirm_button_pos: Tuple[int, int]):
    """
    点击确定按钮

    Args:
        confirm_button_pos: 确定按钮的坐标 (x, y)
    """
    try:
        touch(confirm_button_pos)
        logger.info(f"✅ 点击确定按钮: {confirm_button_pos}")
        sleep(1)
    except Exception as e:
        logger.error(f"❌ 点击确定按钮失败: {e}")


def auto_market_query(
    query_button_pos: Tuple[int, int],
    confirm_button_pos: Tuple[int, int],
    interval: int = 5,
    max_iterations: Optional[int] = None,
):
    """
    自动化市场查询主循环

    Args:
        query_button_pos: 查询按钮的坐标 (x, y)
        confirm_button_pos: 确定按钮的坐标 (x, y)
        interval: 查询间隔（秒），默认 5 秒
        max_iterations: 最大迭代次数，None 表示无限循环
    """
    logger.info("=" * 60)
    logger.info("🤖 开始自动化市场查询")
    logger.info(f"   查询间隔: {interval} 秒")
    logger.info(f"   查询按钮: {query_button_pos}")
    logger.info(f"   确定按钮: {confirm_button_pos}")
    logger.info("=" * 60)

    iteration = 0

    try:
        while True:
            iteration += 1

            # 检查是否达到最大迭代次数
            if max_iterations and iteration > max_iterations:
                logger.info(f"✅ 已达到最大迭代次数 ({max_iterations})，停止执行")
                break

            logger.info(f"\n[{iteration}] 执行查询...")

            # 1. 点击查询按钮
            click_query_button(query_button_pos)

            # 2. 等待一段时间让界面刷新
            sleep(2)

            # 3. 查找一口价按钮及其旁边的价格
            price_result = find_gold_price_text()

            if price_result and price_result.get("found"):
                price = price_result.get("price")
                price_text = price_result.get("price_text", "")
                price_pos = price_result.get("price_pos", (0, 0))

                logger.info(f"📝 识别价格: {price_text}")
                logger.info(f"💰 金币数量: {price}")

                # 4. 检查是否 < 100k
                if price < 100000:
                    logger.info(f"🎯 金币数量 ({price}) < 100k，执行购买流程")

                    # 点击一口价按钮（基于价格位置计算）
                    click_one_key_price_button(price_pos)
                    sleep(1)

                    # 点击确定按钮
                    click_confirm_button(confirm_button_pos)

                    logger.info("✅ 购买流程完成")
                else:
                    logger.info(f"⏭️ 金币数量 ({price}) >= 100k，跳过购买")
            else:
                logger.warning("⚠️ 未找到一口价按钮或价格信息")

            # 6. 等待指定间隔后继续
            logger.info(f"⏳ 等待 {interval} 秒后继续...")
            sleep(interval)

    except KeyboardInterrupt:
        logger.info("\n⛔ 用户中断，程序退出")
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}")
        import traceback

        logger.error(traceback.format_exc())


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="自动化市场查询脚本")
    parser.add_argument(
        "--query-x",
        type=int,
        default=360,
        help="查询按钮 X 坐标 (默认: 360)",
    )
    parser.add_argument(
        "--query-y",
        type=int,
        default=640,
        help="查询按钮 Y 坐标 (默认: 640)",
    )
    parser.add_argument(
        "--confirm-x",
        type=int,
        default=360,
        help="确定按钮 X 坐标 (默认: 360)",
    )
    parser.add_argument(
        "--confirm-y",
        type=int,
        default=1000,
        help="确定按钮 Y 坐标 (默认: 1000)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="查询间隔（秒），默认 5 秒",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="最大迭代次数，默认无限循环",
    )
    parser.add_argument(
        "--emulator",
        type=str,
        help="指定模拟器网络地址（如：127.0.0.1:5555）",
    )

    args = parser.parse_args()

    # 初始化设备和OCR
    initialize_device_and_ocr(args.emulator)

    # 启动游戏
    logger.info("启动游戏...")
    start_app("com.ms.ysjyzr")
    sleep(3)

    # 执行自动化查询
    query_button_pos = (args.query_x, args.query_y)
    confirm_button_pos = (args.confirm_x, args.confirm_y)

    auto_market_query(
        query_button_pos=query_button_pos,
        confirm_button_pos=confirm_button_pos,
        interval=args.interval,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()
