# -*- encoding=utf8 -*-
__author__ = "Airtest"
import time
import sys
import os
import logging
import coloredlogs
import argparse
import random

from airtest.core.api import (
    wait,
    sleep,
    touch,
    exists,
    Template,
)

# 设置 Airtest 日志级别
airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)

# 导入自定义的数据库模块和配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DungeonProgressDB  # noqa: E402
from config_loader import load_config  # noqa: E402

CLICK_INTERVAL = 1
# 配置彩色日志
logger = logging.getLogger(__name__)
# 防止日志重复：移除已有的 handlers
logger.handlers.clear()
logger.propagate = False

coloredlogs.install(
    level="INFO",
    logger=logger,
    fmt="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level_styles={
        "debug": {"color": "cyan"},
        "info": {"color": "green"},
        "warning": {"color": "yellow"},
        "error": {"color": "red"},
        "critical": {"color": "red", "bold": True},
    },
    field_styles={
        "asctime": {"color": "blue"},
        "levelname": {"color": "white", "bold": True},
    },
)


# 全局变量，将在 main 函数中初始化
config_loader = None
zone_dungeons = None
ocr_helper = None

SETTINGS_TEMPLATE = Template(
    r"images/settings_button.png",
    resolution=(720, 1280),
)

GIFTS_TEMPLATE = Template(
    r"images/gifts_button.png",
    resolution=(720, 1280),
)


def find_text_with_paddleocr(text, similarity_threshold=0.6):
    """
    使用 OCRHelper 查找文本并返回位置
    :param text: 要查找的文本
    :param similarity_threshold: 相似度阈值（0-1）
    :return: 文本中心位置 (x, y) 或 None
    """
    try:
        # 使用OCRHelper截图并查找文字
        result = ocr_helper.capture_and_find_text(
            text, confidence_threshold=similarity_threshold
        )

        if result["found"]:
            logger.info(
                f"找到文本: '{result['text']}' (置信度: {result['confidence']:.2f}) 位置: {result['center']}"
            )
            return result["center"]
        else:
            logger.warning(f"未找到文本: '{text}'")
            return None

    except Exception as e:
        logger.error(f"OCR 识别错误: {e}")
        return None


def find_text_and_click(
    text, timeout=10, similarity_threshold=0.7, occurrence=1, use_cache=True
):
    """
    使用 OCRHelper 查找文本并点击
    支持 OCR 纠正：如果找不到原文本，会尝试查找 OCR 可能识别错误的文本

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定点击第几个出现的文字 (1-based)，默认为1
    :return: 是否成功
    """
    if occurrence > 1:
        logger.info(f"🔍 查找文本: {text} (第{occurrence}个)")
    else:
        logger.info(f"🔍 查找文本: {text}")
    start_time = time.time()

    # 准备要尝试的文本列表：[原文本, OCR可能识别的错误文本]
    texts_to_try = [text]

    # 检查是否有对应的 OCR 纠正映射（反向查找）
    if config_loader:
        for ocr_text, correct_text in config_loader.get_ocr_correction_map().items():
            if correct_text == text:
                texts_to_try.append(ocr_text)
                logger.debug(f"💡 将同时尝试查找 OCR 可能识别的文本: {ocr_text}")
                break

    while time.time() - start_time < timeout:
        # 尝试所有可能的文本
        for try_text in texts_to_try:
            # 使用 OCRHelper 查找并点击文本
            if ocr_helper.find_and_click_text(
                try_text,
                confidence_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
            ):
                if try_text != text:
                    logger.info(
                        f"✅ 通过 OCR 纠正找到并点击: {text} (OCR识别为: {try_text})"
                    )
                else:
                    if occurrence > 1:
                        logger.info(f"✅ 成功点击: {text} (第{occurrence}个)")
                    else:
                        logger.info(f"✅ 成功点击: {text}")
                sleep(CLICK_INTERVAL)  # 每个点击后面停顿一下等待界面刷新
                return True

    if occurrence > 1:
        logger.warning(f"❌ 未找到: {text} (第{occurrence}个)")
    else:
        logger.warning(f"❌ 未找到: {text}")
    return False


def click_back():
    """点击返回按钮（左上角）"""
    try:
        touch((360, 117))
        sleep(CLICK_INTERVAL)  # 等待界面刷新
        logger.info("🔙 点击返回按钮")
        return True
    except Exception as e:
        logger.error(f"❌ 返回失败: {e}")
        return False


def click_free_button():
    """点击免费按钮"""
    free_words = ["免费"]

    for word in free_words:
        if find_text_and_click(word, timeout=3, use_cache=False):
            logger.info(f"💰 点击了免费按钮: {word}")

            return True

    logger.warning("⚠️ 未找到免费按钮")
    return False


def is_main_world():
    """检查是否在主世界"""
    return exists(GIFTS_TEMPLATE)


def open_map():
    while not is_main_world():
        click_back()

    touch((350, 50))
    logger.info("🗺️ 打开地图")
    sleep(CLICK_INTERVAL)


def auto_combat():
    """自动战斗"""
    logger.info("自动战斗")
    while not is_main_world():
        positions = [(100 + i * 130, 560) for i in range(5)]
        random.shuffle(positions)
        for pos in positions:
            touch(pos)
            sleep(0.2)


def select_character(char_class):
    """
    选择角色

    Args:
        char_class: 角色职业名称（如：战士、法师、刺客等）
    """
    logger.info(f"⚔️ 选择角色: {char_class}")

    # 打开设置
    back_to_main()

    touch(SETTINGS_TEMPLATE)
    sleep(1)

    # 返回角色选择界面
    find_text_and_click("返回角色选择界面")
    sleep(10)

    # 查找职业文字位置
    logger.info(f"🔍 查找职业: {char_class}")
    pos = find_text_with_paddleocr(char_class, similarity_threshold=0.6)

    if pos:
        # 点击文字上方 60 像素的位置
        click_x = pos[0]
        click_y = pos[1] - 60
        logger.info(f"👆 点击角色位置: ({click_x}, {click_y})")
        touch((click_x, click_y))
        sleep(1)

        # 等待回到主界面
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        logger.error(f"❌ 未找到职业: {char_class}")
        raise Exception(f"无法找到职业: {char_class}")

    find_text_and_click("进入游戏")
    wait_for_main()


def wait_for_main():
    """等待回到主界面"""
    logger.info("等待战斗结束...")
    wait(
        GIFTS_TEMPLATE,
        timeout=180,
    )


def switch_to_zone(zone_name):
    """切换到指定区域"""
    logger.info(f"\n{'=' * 50}")
    logger.info(f"🌍 切换区域: {zone_name}")
    logger.info(f"{'=' * 50}")

    # 点击切换区域按钮
    switch_words = ["切换区域"]

    for word in switch_words:
        if find_text_and_click(word, timeout=10):
            break

    # 点击区域名称
    if find_text_and_click(zone_name, timeout=10, occurrence=2):
        logger.info(f"✅ 成功切换到: {zone_name}")
        touch((80, 212))  # 关闭切换菜单
        return True

    logger.error(f"❌ 切换失败: {zone_name}")
    return False


def sell_trashes():
    logger.info("💰 卖垃圾")
    click_back()
    find_text_and_click("装备")
    find_text_and_click("整理售卖")
    find_text_and_click("出售")
    click_back()
    click_back()
    find_text_and_click("战斗")


def back_to_main():
    logger.info("🔙 返回主界面")
    for _ in range(3):
        click_back()


def process_dungeon(dungeon_name, zone_name, index, total, db):
    """处理单个副本, 返回是否成功完成

    注意：调用此函数前应该已经检查过是否已通关
    """
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

    # 点击副本名称
    if not find_text_and_click(dungeon_name, timeout=5):
        logger.warning(f"⏭️ 跳过: {dungeon_name}")
        return False

    # 尝试点击免费按钮
    if click_free_button():
        # 进入副本战斗，退出后会回到主界面
        auto_combat()
        logger.info(f"✅ 完成: {dungeon_name}")

        # 记录通关状态
        db.mark_dungeon_completed(zone_name, dungeon_name)

        sleep(CLICK_INTERVAL)
        return True
    else:
        # 没有免费按钮，说明今天已经通关过了，记录状态
        logger.warning("⚠️ 无免费按钮，标记为已完成")
        db.mark_dungeon_completed(zone_name, dungeon_name)
        click_back()

    return False


def main():
    """主函数"""
    global config_loader, zone_dungeons, ocr_helper

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="副本自动遍历脚本")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="configs/default.json",
        help="配置文件路径 (默认: configs/default.json)",
    )
    args = parser.parse_args()

    logger.info("\n" + "=" * 60)
    logger.info("🎮 副本自动遍历脚本")
    logger.info("=" * 60 + "\n")

    # 加载配置
    try:
        config_loader = load_config(args.config)
        zone_dungeons = config_loader.get_zone_dungeons()
    except Exception as e:
        logger.error(f"❌ 加载配置失败: {e}")
        sys.exit(1)

    # 初始化设备
    from airtest.core.api import connect_device, auto_setup

    connect_device("Android:///")
    auto_setup(__file__)

    # 初始化OCR工具类
    from ocr_helper import OCRHelper

    ocr_helper = OCRHelper(output_dir="output")

    # 选择角色（如果配置了职业）
    char_class = config_loader.get_char_class()
    if char_class:
        select_character(char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")

    # 初始化数据库
    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        # 清理旧记录
        db.cleanup_old_records(days_to_keep=7)

        # 显示今天已通关的副本
        completed_count = db.get_today_completed_count()
        if completed_count > 0:
            logger.info(f"📊 今天已通关 {completed_count} 个副本")
            completed_dungeons = db.get_today_completed_dungeons()
            for zone, dungeon in completed_dungeons[:5]:  # 只显示前5个
                logger.info(f"  ✅ {zone} - {dungeon}")
            if len(completed_dungeons) > 5:
                logger.info(f"  ... 还有 {len(completed_dungeons) - 5} 个")
            logger.info("")

        total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())
        remaining_dungeons = total_dungeons - completed_count
        logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本")
        logger.info(f"📊 剩余: {remaining_dungeons} 个副本待通关\n")

        dungeon_index = 0
        processed_dungeons = 0

        # 遍历所有区域
        back_to_main()
        open_map()
        for zone_idx, (zone_name, dungeons) in enumerate(zone_dungeons.items(), 1):
            logger.info(f"\n{'#' * 60}")
            logger.info(f"# 🌍 [{zone_idx}/{len(zone_dungeons)}] 区域: {zone_name}")
            logger.info(f"# 🎯 副本数: {len(dungeons)}")
            logger.info(f"{'#' * 60}")

            # 遍历副本
            for dungeon_dict in dungeons:
                dungeon_name = dungeon_dict["name"]
                is_selected = dungeon_dict["selected"]
                dungeon_index += 1

                # 检查是否选定该副本
                if not is_selected:
                    logger.info(
                        f"⏭️ [{dungeon_index}/{total_dungeons}] 未选定，跳过: {dungeon_name}"
                    )
                    continue

                # 先检查是否已通关，如果已通关则跳过，不需要切换区域
                if db.is_dungeon_completed(zone_name, dungeon_name):
                    logger.info(
                        f"⏭️ [{dungeon_index}/{total_dungeons}] 已通关，跳过: {dungeon_name}"
                    )
                    continue

                # 切换区域
                if not switch_to_zone(zone_name):
                    logger.warning(f"⏭️ 跳过区域: {zone_name}")
                    continue

                # 完成副本后会回到主界面，需要重新打开地图
                if process_dungeon(
                    dungeon_name, zone_name, dungeon_index, total_dungeons, db
                ):
                    processed_dungeons += 1
                    # 每完成3个副本就卖垃圾
                    if processed_dungeons % 3 == 0:
                        sell_trashes()

                    open_map()

            logger.info(f"\n✅ 完成区域: {zone_name}")

        logger.info("\n" + "=" * 60)
        logger.info(f"🎉 全部完成！今天共通关 {db.get_today_completed_count()} 个副本")
        logger.info("=" * 60 + "\n")
        back_to_main()


if __name__ == "__main__":
    main()
