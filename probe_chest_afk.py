#!/usr/bin/env python3
# -*- encoding:utf8 -*-
"""临时诊断脚本：验证「野外挂机 → 宝箱存量增长」的前提。

流程：读宝库存量 → 回野外挂机 N秒（带心跳）→ 再读存量做对比。

注意：底部「主城」tab处于**激活态**时其文字不渲染，OCR 读不到，
因此这里对「主城」一步做容错（点不到就直接试「宝库」）。

用法::

    python probe_chest_afk.py [config_name] [emulator] [seconds]
"""

import logging
import re
import sys
import time

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
logger = logging.getLogger("probe_chest_afk")

CHEST_NAME = "亡灵宝箱"
COUNT_PATTERN = re.compile(r"^(\d+)\s*/\s*(\d+)$")
# 「宝箱名」与「存量行」的纵坐标差上限（真机实测 34px）
COUNT_MAX_DY = 40


def read_chest_stock(ocr_helper, chest_name):
    """进宝库读取指定宝箱的存量数字。

    Args:
        ocr_helper: OCR helper。
        chest_name: 宝箱名称。

    Returns:
        tuple: ``(存量, 每日上限)``；读不到时 ``(None, None)``。
    """
    back_to_main()
    find_text_and_click_safe("主城", regions=[9])
    if not find_text_and_click_safe("宝库", regions=[9]):
        logger.warning("未找到「宝库」入口")
        return None, None
    time.sleep(1.5)

    items = ocr_helper.capture_and_get_all_texts(use_cache=False)
    name_hit = next((it for it in items if it.get("text") == chest_name), None)
    if not name_hit:
        logger.warning("未读到宝箱名 %s", chest_name)
        return None, None
    ny = name_hit["center"][1]
    for it in items:
        m = COUNT_PATTERN.match(it.get("text", "").strip())
        if m and abs(it["center"][1] - ny) <= COUNT_MAX_DY:
            logger.info("读到存量 %r conf=%.3f", it.get("text"), it.get("confidence", 0))
            return int(m.group(1)), int(m.group(2))
    logger.warning("未读到存量行（宝箱名在 y=%s）", ny)
    return None, None


def main() -> int:
    """读取挂机前后的宝箱存量做对比。

    Returns:
        进程退出码。
    """
    config_name = sys.argv[1] if len(sys.argv) > 1 else "warrior"
    emulator = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.150:5555"
    seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    initialize_configs(f"configs/{config_name}.json")
    container = get_container()
    device_manager = DeviceManager()
    correction_map = container.config_loader.get_ocr_correction_map()
    device_manager.initialize(emulator_name=emulator, correction_map=correction_map)
    ocr_helper = device_manager.get_ocr_helper()

    before, cap_before = read_chest_stock(ocr_helper, CHEST_NAME)
    logger.info("挂机前存量 = %s (上限 %s)", before, cap_before)

    back_to_main()
    logger.info("回到野外，开始挂机 %d 秒", seconds)
    start = time.time()
    last_beat = start
    while time.time() - start < seconds:
        time.sleep(5)
        if is_game_foreground() is False:
            logger.error("游戏不在前台，中止")
            return 1
        now = time.time()
        if now - last_beat >= 30:
            last_beat = now
            logger.info("挂机中... %.0f/%.0f 秒", now - start, seconds)

    after, cap_after = read_chest_stock(ocr_helper, CHEST_NAME)
    logger.info("挂机后存量 = %s (上限 %s)", after, cap_after)
    if before is not None and after is not None:
        logger.info("=== 增量 = %+d / %d 秒 ===", after - before, seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
