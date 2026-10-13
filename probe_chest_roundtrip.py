#!/usr/bin/env python3
# -*- encoding:utf8 -*-
"""临时诊断脚本：验证「宝库 → 读存量 → 挂机 → 复读存量」全链路。

不依赖 OCR 找「主城」（该tab 激活态文字不渲染），直接用固定坐标点它。

用法::

    python probe_chest_roundtrip.py [config_name] [emulator] [afk_seconds]
"""

import logging
import re
import sys
import time

from airtest.core.api import touch

from auto_dungeon_container import get_container
from auto_dungeon_core import initialize_configs
from auto_dungeon_device import DeviceManager
from auto_dungeon_navigation import back_to_main, is_game_foreground
from auto_dungeon_ui import find_text_and_click_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("probe_roundtrip")

CHEST_NAME = "亡灵宝箱"
COUNT_PATTERN = re.compile(r"^(\d+)\s*/\s*(\d+)$")
COUNT_MAX_DY = 40
# 底部导航「主城」tab 的固定坐标（该 tab 激活时文字不渲染，只能点固定坐标）。
# 真机实测底部是 **两行** 5 个 tab：「随从/装备/战斗/主城」在 y≈1211，
# 「专业」单独在第二行 y≈1241、x≈492 —— 用 x≈523 会误点到「专业」页。
MAIN_CITY_TAB = (655, 1211)


def enter_vault(ocr_helper, chest_name):
    """进入宝库并读取指定宝箱存量。

    Args:
        ocr_helper: OCR helper。
        chest_name: 宝箱名称。

    Returns:
        tuple: ``(存量, 每日上限)``；读不到时 ``(None, None)``。
    """
    back_to_main()
    touch(MAIN_CITY_TAB)
    time.sleep(1.5)
    if not find_text_and_click_safe("宝库", regions=[9]):
        logger.warning("未找到「宝库」入口")
        return None, None
    time.sleep(2)

    items = ocr_helper.capture_and_get_all_texts(use_cache=False)
    name_hit = next((it for it in items if it.get("text") == chest_name), None)
    if not name_hit:
        logger.warning("未读到宝箱名 %s", chest_name)
        return None, None
    ny = name_hit["center"][1]
    for it in items:
        m = COUNT_PATTERN.match(it.get("text", "").strip())
        if m and abs(it["center"][1] - ny) <= COUNT_MAX_DY:
            logger.info(
                "读到存量 %r conf=%.3f at %s",
                it.get("text"),
                it.get("confidence", 0),
                it.get("center"),
            )
            return int(m.group(1)), int(m.group(2))
    logger.warning("未读到存量行（宝箱名 y=%s）", ny)
    return None, None


def main() -> int:
    """读取挂机前后的宝箱存量做对比。

    Returns:
        进程退出码。
    """
    config_name = sys.argv[1] if len(sys.argv) > 1 else "warrior"
    emulator = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.150:5555"
    seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 900

    initialize_configs(f"configs/{config_name}.json")
    container = get_container()
    device_manager = DeviceManager()
    correction_map = container.config_loader.get_ocr_correction_map()
    device_manager.initialize(emulator_name=emulator, correction_map=correction_map)
    ocr_helper = device_manager.get_ocr_helper()
    # 必须把 game_actions 注入容器：find_text_and_click_safe 走的是
    # container.game_actions，未注入时会被 except 静默吞掉并返回 False。
    container.game_actions = device_manager.get_game_actions()

    before, cap_before = enter_vault(ocr_helper, CHEST_NAME)
    logger.info("挂机前存量 = %s (上限 %s)", before, cap_before)

    back_to_main()
    logger.info("回到野外，挂机 %d 秒", seconds)
    start = time.time()
    last_beat = start
    while time.time() - start < seconds:
        time.sleep(5)
        if is_game_foreground() is False:
            logger.error("游戏不在前台，中止")
            return 1
        now = time.time()
        if now - last_beat >= 60:
            last_beat = now
            logger.info("挂机中 %.0f/%.0f 秒", now - start, seconds)

    after, cap_after = enter_vault(ocr_helper, CHEST_NAME)
    logger.info("挂机后存量 = %s (上限 %s)", after, cap_after)
    if before is not None and after is not None:
        logger.info("=== 增量 = %+d / %d 秒 ===", after - before, seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
