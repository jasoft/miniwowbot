# -*- encoding=utf8 -*-
__author__ = "Airtest"
import time
import sys
import os
import logging
import coloredlogs
import argparse
import random

from airtest.core.api import wait, sleep, touch, exists, Template, stop_app, start_app

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
SETTINGS_POINT = (669, 107)

GIFTS_TEMPLATE = Template(
    r"images/gifts_button.png",
    resolution=(720, 1280),
)


def find_text(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
    raise_exception=True,
):
    """
    使用 OCRHelper 查找文本
    支持 OCR 纠正：如果找不到原文本，会尝试查找 OCR 可能识别错误的文本

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :param raise_exception: 超时后是否抛出异常，默认True
    :return: OCR识别结果字典，包含 center, text, confidence 等信息
    :raises TimeoutError: 如果超时且 raise_exception=True
    """
    # 检查 ocr_helper 是否已初始化
    if ocr_helper is None:
        error_msg = "❌ OCR助手未初始化，无法查找文本"
        logger.error(error_msg)
        if raise_exception:
            raise RuntimeError(error_msg)
        return None

    region_desc = ""
    if regions:
        region_desc = f" [区域{regions}]"

    if occurrence > 1:
        logger.info(f"🔍 查找文本: {text} (第{occurrence}个){region_desc}")
    else:
        logger.info(f"🔍 查找文本: {text}{region_desc}")
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
            # 使用 OCRHelper 查找文本
            result = ocr_helper.capture_and_find_text(
                try_text,
                confidence_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
                regions=regions,
            )

            if result and result.get("found"):
                if try_text != text:
                    logger.info(
                        f"✅ 通过 OCR 纠正找到文本: {text} (OCR识别为: {try_text}){region_desc}"
                    )
                else:
                    if occurrence > 1:
                        logger.info(
                            f"✅ 找到文本: {text} (第{occurrence}个){region_desc}"
                        )
                    else:
                        logger.info(f"✅ 找到文本: {text}{region_desc}")
                return result

        # 短暂休眠避免CPU占用过高
        sleep(0.1)

    # 超时处理
    error_msg = f"❌ 超时未找到文本: {text}"
    if occurrence > 1:
        error_msg = f"❌ 超时未找到文本: {text} (第{occurrence}个)"

    logger.warning(error_msg)

    if raise_exception:
        raise TimeoutError(error_msg)

    return None


def find_text_and_click(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
):
    """
    使用 OCRHelper 查找文本并点击
    支持 OCR 纠正：如果找不到原文本，会尝试查找 OCR 可能识别错误的文本

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定点击第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :return: 是否成功
    """
    try:
        # 调用 find_text 查找文本（不抛出异常）
        result = find_text(
            text=text,
            timeout=timeout,
            similarity_threshold=similarity_threshold,
            occurrence=occurrence,
            use_cache=use_cache,
            regions=regions,
            raise_exception=False,
        )

        if result and result.get("found"):
            # 点击找到的位置
            center = result["center"]
            touch(center)
            sleep(CLICK_INTERVAL)  # 每个点击后面停顿一下等待界面刷新

            region_desc = f" [区域{regions}]" if regions else ""
            logger.info(f"✅ 成功点击: {text}{region_desc} at {center}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ 查找并点击文本时出错: {e}")
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
    back_to_main()

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

    # 检查是否存在错误对话框
    error_templates = [
        Template(r"images/error_duplogin.png", resolution=(720, 1280)),
        Template(r"images/error_network.png", resolution=(720, 1280)),
    ]

    ok_button_template = Template(r"images/ok_button.png", resolution=(720, 1280))

    for error_template in error_templates:
        if exists(error_template):
            logger.warning("⚠️ 检测到错误对话框")
            if exists(ok_button_template):
                touch(ok_button_template)
                logger.info("✅ 点击OK按钮关闭错误对话框")
                sleep(1)
            break

    if not exists(
        Template(r"images/enter_game_button.png", resolution=(720, 1280))
    ):  # 如果不在选择角色界面，返回选择界面
        back_to_main()
        touch(SETTINGS_POINT)
        sleep(1)

        # 返回角色选择界面
        find_text_and_click("返回角色选择界面")
        wait(Template(r"images/enter_game_button.png", resolution=(720, 1280)), 10)
    else:
        logger.info("已在角色选择界面")

    # 查找职业文字位置
    logger.info(f"🔍 查找职业: {char_class}")
    result = find_text(char_class, similarity_threshold=0.6)

    if result and result.get("found"):
        # 点击找到的位置
        pos = result["center"]
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
    find_text_and_click("装备", regions=[7, 8, 9])
    find_text_and_click("整理售卖", regions=[7, 8, 9])
    find_text_and_click("出售")
    click_back()
    click_back()
    find_text_and_click("战斗", regions=[7, 8, 9])


def switch_account(account_name):
    logger.info(f"切换账号: {account_name}")
    stop_app("com.ms.ysjyzr")
    sleep(2)
    start_app("com.ms.ysjyzr")
    find_text("进入游戏", timeout=20, regions=[5])
    touch((14, 43))
    sleep(2)
    find_text_and_click("切换账号", regions=[2, 3])
    find_text("最近登录", timeout=20)
    touch((572, 599))  # 下拉箭头
    find_text_and_click(account_name)
    touch((356, 732))  # 登录按钮


def back_to_main():
    logger.info("🔙 返回主界面")
    while not is_main_world():
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
    parser.add_argument(
        "--load-account",
        type=str,
        help="加载指定账号后退出（账号名称，如：18502542158）",
    )
    args = parser.parse_args()

    # 如果只是加载账号，则不需要显示副本信息
    if not args.load_account:
        logger.info("\n" + "=" * 60)
        logger.info("🎮 副本自动遍历脚本")
        logger.info("=" * 60 + "\n")

    # 处理加载账号模式
    if args.load_account:
        logger.info("\n" + "=" * 60)
        logger.info("🔄 账号加载模式")
        logger.info("=" * 60 + "\n")
        logger.info(f"📱 目标账号: {args.load_account}")

        # 初始化设备和OCR
        from airtest.core.api import connect_device, auto_setup
        from ocr_helper import OCRHelper

        connect_device("Android:///")
        auto_setup(__file__)
        ocr_helper = OCRHelper(output_dir="output")

        # 切换账号
        try:
            switch_account(args.load_account)
            logger.info(f"✅ 成功加载账号: {args.load_account}")
            logger.info("=" * 60 + "\n")
            return
        except Exception as e:
            logger.error(f"❌ 加载账号失败: {e}")
            sys.exit(1)

    # 加载配置
    try:
        config_loader = load_config(args.config)
        zone_dungeons = config_loader.get_zone_dungeons()
    except Exception as e:
        logger.error(f"❌ 加载配置失败: {e}")
        sys.exit(1)

    # 初始化数据库（先检查进度）
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

        # 计算选定的副本总数
        total_selected_dungeons = sum(
            sum(1 for d in dungeons if d.get("selected", True))
            for dungeons in zone_dungeons.values()
        )
        total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())

        logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本")
        logger.info(f"📊 选定: {total_selected_dungeons} 个副本")
        logger.info(f"📊 已完成: {completed_count} 个副本")

        # 检查是否所有选定的副本都已完成
        if completed_count >= total_selected_dungeons:
            logger.info("\n" + "=" * 60)
            logger.info("🎉 今天所有选定的副本都已完成！")
            logger.info("=" * 60)
            logger.info("💤 无需执行任何操作，脚本退出")
            return

        remaining_dungeons = total_selected_dungeons - completed_count
        logger.info(f"📊 剩余: {remaining_dungeons} 个副本待通关\n")

    # 初始化设备和OCR（只有在需要执行时才初始化）
    from airtest.core.api import connect_device, auto_setup
    from ocr_helper import OCRHelper

    connect_device("Android:///")
    auto_setup(__file__)
    ocr_helper = OCRHelper(output_dir="output")

    # 选择角色（如果配置了职业）
    char_class = config_loader.get_char_class()
    if char_class:
        select_character(char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")

    # 重新打开数据库连接执行副本遍历
    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        dungeon_index = 0
        processed_dungeons = 0

        # 遍历所有区域
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
                open_map()
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
