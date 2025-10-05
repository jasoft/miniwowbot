# -*- encoding=utf8 -*-
__author__ = "Airtest"

from airtest.core.api import (
    connect_device,
    auto_setup,
    wait,
    sleep,
    touch,
    device,
    exists,
    Template,
)
import time
import sys
import os
import logging
import coloredlogs

# 导入自定义的OCR工具类
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ocr_helper import OCRHelper

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

# 设置 Airtest 日志级别
airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)


zone_dungeons = {
    # 风暴群岛
    "风暴群岛": [
        "真理之地",
        "预言神殿",
        "海底王宫",
        "泰坦密室",
        "黑暗庄园",
        "海底囚牢",
        "地精岛",
        "泰坦遗迹",
        "海盗监狱",
        "巨魔陵墓",
        "毒蛇神庙",
        "腐化沼泽",
        "海港城",
    ],
    # 军团领域
    "军团领域": [
        "大墓地密室",
        "流放王座",
        "毁灭之地",
        "大墓地圣殿",
        "封印地窟",
        "魔能宫殿",
        "魔能要塞",
        "魔法高台",
        "地底巢穴",
        "风暴绿洲",
        "渡鸦堡垒",
        "梦魇丛林",
        "守护者大殿",
    ],
    # 暗影大陆
    "暗影大陆": [
        "钢铁码头",
        "食人魔王国",
        "黑暗熔炉",
        "通天峰",
        "熔渣车间",
        "食人魔矿井",
        "木精圣地",
        "鲜血庭院",
        "钢铁车站",
        "神圣陵墓",
        "兽人墓地",
        "毁灭高台",
    ],
    # 迷雾大陆
    "迷雾大陆": [
        "兽人圣殿",
        "恐魔之心",
        "古魔宝库",
        "兽人都城",
        "古魔宫殿",
        "风暴之巅",
        "酿酒厂",
        "风暴王座",
        "青龙寺",
        "白虎寺",
        "日落关",
        "玄牛寺",
    ],
    # 元素之地
    "元素之地": [
        "火焰宫殿",
        "守护者神殿",
        "黑龙宫殿",
        "黑暗堡垒",
        "潮汐宫殿",
        "黑暗监狱",
        "泰坦密室",
        "大地神殿",
        "失落之城",
        "天空之城",
        "黑石熔炉",
    ],
    # 冰封大陆
    "冰封大陆": [
        "泰坦基地",
        "冠军试炼",
        "寒冰堡垒",
        "寒冰王座",
        "灵魂熔炉",
        "瘟疫之城",
        "古代大厅",
        "古代王国",
        "巨魔要塞",
        "峡湾城堡",
        "蓝龙巢穴",
    ],
    # 虚空领域
    "虚空领域": [
        "魔法之井",
        "虚空要塞",
        "海底神殿",
        "守护者之塔上层",
        "黑暗神殿",
        "守护者之塔下层",
        "圣山战场",
        "虚空舰",
        "沼泽水库",
        "山丘城堡",
        "地狱火堡垒",
        "亡者之城",
    ],
    # 东部大陆
    "东部大陆": [
        "亡灵要塞",
        "黑龙巢穴",
        "火焰之心",
        "巨石密室",
        "诅咒教堂",
        "盗贼矿井",
        "机械要塞",
        "巨魔墓地",
        "噩梦洞穴",
        "野猪人高地",
        "水晶庭院",
        "龙人塔",
        "精灵遗迹",
        "沉没的神庙",
    ],
}


# 初始化设备
connect_device("Android:///")
auto_setup(__file__)

# 初始化OCR工具类
ocr_helper = OCRHelper(output_dir="output")


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


def find_text_and_click(text, timeout=10, similarity_threshold=0.9, occurrence=1):
    """
    使用 OCRHelper 查找文本并点击
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

    while time.time() - start_time < timeout:
        # 使用 OCRHelper 查找并点击文本
        if ocr_helper.find_and_click_text(
            text, confidence_threshold=similarity_threshold, occurrence=occurrence
        ):
            if occurrence > 1:
                logger.info(f"✅ 成功点击: {text} (第{occurrence}个)")
            else:
                logger.info(f"✅ 成功点击: {text}")
            return True

    if occurrence > 1:
        logger.warning(f"❌ 未找到: {text} (第{occurrence}个)")
    else:
        logger.warning(f"❌ 未找到: {text}")
    return False


def click_back():
    """点击返回按钮（左上角）"""
    try:
        width, height = device().get_current_resolution()
        back_pos = (int(width * 0.08), int(height * 0.08))
        touch(back_pos)
        logger.info("🔙 点击返回按钮")
        return True
    except Exception as e:
        logger.error(f"❌ 返回失败: {e}")
        return False


def click_free_button():
    """点击免费按钮"""
    free_words = ["免费"]

    for word in free_words:
        if find_text_and_click(word, timeout=3):
            logger.info(f"💰 点击了免费按钮: {word}")
            wait(
                Template(
                    r"tpl1759654885996.png",
                    record_pos=(0.432, -0.732),
                    resolution=(720, 1280),
                )
            )
            return True

    logger.warning("⚠️ 未找到免费按钮")
    return False


def open_map():
    if exists(
        Template(
            r"images/tpl1759679976634.png",
            record_pos=(0.432, -0.732),
            resolution=(720, 1280),
        )
    ):
        touch((350, 50))
        logger.info("🗺️ 打开地图")


def wait_for_main():
    """等待回到主界面"""
    wait(
        Template(
            r"images/tpl1759679976634.png",
            record_pos=(0.432, -0.732),
            resolution=(720, 1280),
        )
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
    click_back()
    find_text_and_click("装备")
    find_text_and_click("整理售卖")
    find_text_and_click("出售")
    click_back()


def process_dungeon(dungeon_name, index, total):
    """处理单个副本"""
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")
    open_map()

    # 点击副本名称
    if not find_text_and_click(dungeon_name, timeout=5):
        logger.warning(f"⏭️ 跳过: {dungeon_name}")
        return False

    # 尝试点击免费按钮
    if click_free_button():
        # 进入副本战斗，退出后会回到主界面，这里需要再次打开地图
        wait_for_main()
        logger.info(f"✅ 完成: {dungeon_name}")
        sleep(1)
        # 可能需要返回
        click_back()
    else:
        logger.warning("⚠️ 无免费按钮，返回")
        click_back()

    return True


def main():
    """主函数"""
    logger.info("\n" + "=" * 60)
    logger.info("🎮 副本自动遍历脚本")
    logger.info("=" * 60 + "\n")

    total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())
    logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本\n")

    dungeon_index = 0

    # 遍历所有区域
    open_map()
    for zone_idx, (zone_name, dungeons) in enumerate(zone_dungeons.items(), 1):
        logger.info(f"\n{'#' * 60}")
        logger.info(f"# 🌍 [{zone_idx}/{len(zone_dungeons)}] 区域: {zone_name}")
        logger.info(f"# 🎯 副本数: {len(dungeons)}")
        logger.info(f"{'#' * 60}")

        # 遍历副本
        for dungeon_name in dungeons:
            dungeon_index += 1
            if dungeon_index % 3 == 0:
                sell_trashes()
            # 切换区域
            if not switch_to_zone(zone_name):
                logger.warning(f"⏭️ 跳过区域: {zone_name}")
                continue

            process_dungeon(dungeon_name, dungeon_index, total_dungeons)

        logger.info(f"\n✅ 完成区域: {zone_name}")

    logger.info("\n" + "=" * 60)
    logger.info("🎉 全部完成！")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    main()
