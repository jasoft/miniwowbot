"""
自动化市场查询脚本
每 5 秒点击一次查询按钮，识别全屏幕文字，匹配一口价金币数量
如果金币数 < 100k，自动点击一口价按钮并确定
"""

import os
import logging
import re
from typing import Optional, Tuple

from airtest.core.api import (
    auto_setup,
    touch,
    sleep,
)

# 导入通用日志配置模块
from device_utils import connect_device_with_timeout
from logger_config import setup_logger_from_config
from vibe_ocr import OCRHelper
from emulator_manager import EmulatorManager
from error_dialog_monitor import ErrorDialogMonitor

logging.getLogger("airtest").setLevel(logging.CRITICAL)
# 设置日志
logger = setup_logger_from_config(use_color=True)

# 全局变量
ocr_helper = None
emulator_manager = None
error_dialog_monitor: Optional[ErrorDialogMonitor] = None


def get_error_dialog_monitor() -> ErrorDialogMonitor:
    global error_dialog_monitor
    if error_dialog_monitor is None:
        error_dialog_monitor = ErrorDialogMonitor(logger)
    return error_dialog_monitor


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
        connect_device_with_timeout(connection_string, timeout=30)
        logger.info("   ✅ 成功连接到设备")
    except Exception as e:
        logger.error(f"   ❌ 连接设备失败: {e}")
        raise

    if ocr_helper is None:
        ocr_helper = OCRHelper(output_dir="output")


def parse_gold_amount(text: str) -> Optional[int]:
    """
    从 "一口价 xxxxk 金币" 或 "一口价 xxxxx 金币" 格式的文本中解析金币数量
    例如:
    - "一口价 2000k 金币" -> 2000000
    - "一口价2000K金币" -> 2000000
    - "一口价88888金币" -> 88888

    Args:
        text: 要解析的文本

    Returns:
        金币数量（整数），如果解析失败返回 None
    """
    # 先尝试匹配带 k/K 的格式: "一口价 XXXk 金币" 或 "一口价XXXk金币"
    match = re.search(r"一口价\s*(\d+(?:\.\d+)?)\s*[kK]\s*金币", text)
    if match:
        amount_str = match.group(1)
        try:
            amount = float(amount_str)
            # k/K 表示千位
            amount *= 1000
            return int(amount)
        except ValueError:
            return None

    # 再尝试匹配不带 k/K 的格式: "一口价 XXXXX 金币"
    match = re.search(r"一口价\s*(\d+(?:\.\d+)?)\s*金币", text)
    if match:
        amount_str = match.group(1)
        try:
            amount = float(amount_str)
            return int(amount)
        except ValueError:
            return None

    return None


def find_all_matching_prices(price_threshold: int) -> list:
    """
    查找全屏幕中所有符合 "一口价 xxxxk 金币" 模式的文本，并返回价格低于阈值的结果

    Args:
        price_threshold: 价格阈值，只返回价格低于此值的结果

    Returns:
        包含匹配结果的列表，每个元素为字典:
        {
            "price": int,  # 金币数量
            "price_text": str,  # 原始价格文本
            "center": tuple,  # 文字位置
        }
    """
    if ocr_helper is None:
        logger.error("❌ OCR助手未初始化")
        return []

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
            return []

        logger.info(f"📝 识别到 {len(all_texts)} 个文字")
        logger.info("=" * 80)
        logger.info("all_texts")
        logger.info("=" * 80)

        # 查找所有符合 "一口价 xxxxk 金币" 模式的文本
        matching_results = []

        for text_info in all_texts:
            text = text_info["text"].strip()

            # 检查是否符合 "一口价 xxxxk 金币" 或 "一口价 xxxxx 金币" 模式
            if re.search(r"一口价\s*\d+\s*[kK]?\s*金币", text):
                logger.info(f"\n✅ 找到匹配文本: {text}")

                # 解析价格
                price = parse_gold_amount(text)

                if price is not None:
                    logger.info(f"   💰 价格: {price} 金币")

                    # 检查是否低于阈值
                    if price < price_threshold:
                        logger.info(
                            f"   🎯 价格 ({price}) < 阈值 ({price_threshold})，处理此拍卖品"
                        )

                        # 获取同一行的所有文字（y 坐标差值 ≤ 50）
                        price_y = text_info["center"][1]
                        item_texts = []

                        for other_text_info in all_texts:
                            other_y = other_text_info["center"][1]
                            if abs(other_y - price_y) <= 50:
                                item_texts.append(
                                    {
                                        "text": other_text_info["text"].strip(),
                                        "center": other_text_info["center"],
                                        "confidence": other_text_info.get(
                                            "confidence", 0
                                        ),
                                    }
                                )

                        # 按 x 坐标排序
                        item_texts.sort(key=lambda x: x["center"][0])

                        # 构造拍卖品描述
                        item_description = " | ".join([t["text"] for t in item_texts])

                        logger.info("   📦 拍卖品信息:")
                        logger.info(f"      Y 坐标: {price_y}")
                        logger.info(f"      同行文字数: {len(item_texts)}")
                        for idx, item_text in enumerate(item_texts):
                            logger.info(
                                f"        [{idx}] {item_text['text']:30s} | 位置: {item_text['center']}"
                            )
                        logger.info(f"      完整描述: {item_description}")

                        matching_results.append(
                            {
                                "price": price,
                                "price_text": text,
                                "center": text_info["center"],
                                "item_texts": item_texts,
                                "item_description": item_description,
                            }
                        )
                    else:
                        logger.info(
                            f"   ⏭️ 价格 ({price}) >= 阈值 ({price_threshold})，跳过"
                        )
                else:
                    logger.warning(f"   ⚠️ 无法解析价格: {text}")

        # 清理临时截图
        try:
            os.remove(screenshot_path)
        except Exception as exc:
            # 删不掉会留下垃圾文件，说清原因便于人工清理
            logger.warning(
                f"   ⚠️ 清理临时截图失败: {type(exc).__name__}: {exc} ({screenshot_path})"
            )

        logger.info("\n" + "=" * 80)
        logger.info(f"📊 找到 {len(matching_results)} 个符合条件的商品")
        for idx, result in enumerate(matching_results, 1):
            logger.info(f"\n  [{idx}] 拍卖品信息:")
            logger.info(f"      价格: {result['price']} 金币")
            logger.info(f"      描述: {result['item_description']}")
        logger.info("=" * 80)

        return matching_results

    except Exception as e:
        logger.error(f"❌ OCR 查找失败: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return []


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
    button_x = text_pos[0] + 268
    button_y = text_pos[1] + 10
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
    price_threshold: int = 100000,
    interval: int = 5,
    max_iterations: Optional[int] = None,
):
    """
    自动化市场查询主循环

    Args:
        price_threshold: 价格阈值，只拍下价格低于此值的商品（默认 100000）
        interval: 查询间隔（秒），默认 5 秒
        max_iterations: 最大迭代次数，None 表示无限循环
    """
    # 固定的按钮坐标
    QUERY_BUTTON_POS = (560, 300)
    CONFIRM_BUTTON_POS = (485, 710)

    logger.info("=" * 60)
    logger.info("🤖 开始自动化市场查询")
    logger.info(f"   价格阈值: {price_threshold} 金币")
    logger.info(f"   查询间隔: {interval} 秒")
    logger.info(f"   查询按钮: {QUERY_BUTTON_POS}")
    logger.info(f"   确定按钮: {CONFIRM_BUTTON_POS}")
    logger.info("=" * 60)

    iteration = 0
    monitor = get_error_dialog_monitor()

    try:
        while True:
            iteration += 1

            # 检查是否达到最大迭代次数
            if max_iterations and iteration > max_iterations:
                logger.info(f"✅ 已达到最大迭代次数 ({max_iterations})，停止执行")
                break

            monitor.handle_once()
            logger.info(f"\n[{iteration}] 执行查询...")

            # 1. 点击查询按钮
            click_query_button(QUERY_BUTTON_POS)

            # 2. 等待一段时间让界面刷新
            sleep(2)

            # 3. 查找所有符合条件的商品
            matching_items = find_all_matching_prices(price_threshold)

            if matching_items:
                logger.info(f"\n🎯 找到 {len(matching_items)} 个符合条件的商品")

                # 4. 对每个符合条件的商品执行购买流程
                for idx, item in enumerate(matching_items, 1):
                    item_price = item["price"]
                    price_pos = item["center"]
                    item_description = item["item_description"]

                    logger.info(f"\n   [{idx}/{len(matching_items)}] 处理商品:")
                    logger.info(f"      价格: {item_price} 金币")
                    logger.info(f"      描述: {item_description}")

                    # 点击一口价按钮（基于价格位置计算）
                    click_one_key_price_button(price_pos)
                    sleep(1)

                    # 点击确定按钮
                    click_confirm_button(CONFIRM_BUTTON_POS)

                    logger.info(f"   ✅ 商品 {idx} 购买完成")
                    sleep(1)  # 等待一下再处理下一个
            else:
                logger.warning(f"⚠️ 未找到符合条件的商品（价格 < {price_threshold}）")

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

    global error_dialog_monitor

    parser = argparse.ArgumentParser(description="自动化市场查询脚本")
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="查询间隔（秒），默认 5 秒",
    )
    parser.add_argument(
        "--price-threshold",
        type=int,
        default=100000,
        help="价格阈值，只拍下价格低于此值的商品（默认: 100000）",
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
    parser.add_argument(
        "--name",
        type=str,
        help="要查询的装备名称",
    )

    args = parser.parse_args()

    monitor = get_error_dialog_monitor()
    monitor.start()
    try:
        # 初始化设备和OCR
        initialize_device_and_ocr(args.emulator)

        # 执行自动化查询
        auto_market_query(
            price_threshold=args.price_threshold,
            interval=args.interval,
            max_iterations=args.max_iterations,
        )
    finally:
        monitor.stop()
        if error_dialog_monitor is monitor:
            error_dialog_monitor = None


if __name__ == "__main__":
    main()
