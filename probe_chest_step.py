#!/usr/bin/env python3
# -*- encoding:utf8 -*-
"""临时诊断脚本：逐步截图 + OCR，把「进宝库」链路的每一帧留证。

用法::

    python probe_chest_step.py [config_name] [emulator]
"""

import logging
import sys
import time

from airtest.core.api import touch

from auto_dungeon_container import get_container
from auto_dungeon_core import initialize_configs
from auto_dungeon_device import DeviceManager
from auto_dungeon_navigation import back_to_main
from auto_dungeon_ui import find_text_and_click_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("probe_step")

OUT_DIR = "log/_chest_probe"
MAIN_CITY_TAB = (655, 1211)


def dump(ocr_helper, tag):
    """截图并打印 OCR 文字中与导航/宝库相关的部分。

    Args:
        ocr_helper: OCR helper。
        tag: 本步的标签，用于文件名。
    """
    ocr_helper.snapshot_func(filename=f"{OUT_DIR}/step_{tag}.png")
    keys = ("主城", "宝库", "专业", "战斗", "随从", "装备", "亡灵", "宝箱", "钥匙", "今日")
    for it in ocr_helper.capture_and_get_all_texts(use_cache=False):
        text = it.get("text", "")
        if any(k in text for k in keys):
            logger.info("  [%s] %s conf=%.3f %r", tag, it.get("center"), it.get("confidence", 0), text)


def main() -> int:
    """逐步执行「回主界面 → 点主城 → 点宝库」，每步留证。

    Returns:
        进程退出码。
    """
    config_name = sys.argv[1] if len(sys.argv) > 1 else "warrior"
    emulator = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.150:5555"

    initialize_configs(f"configs/{config_name}.json")
    container = get_container()
    device_manager = DeviceManager()
    correction_map = container.config_loader.get_ocr_correction_map()
    device_manager.initialize(emulator_name=emulator, correction_map=correction_map)
    ocr_helper = device_manager.get_ocr_helper()

    back_to_main()
    time.sleep(1)
    logger.info("=== step0: back_to_main 后 ===")
    dump(ocr_helper, "0_after_back")

    touch(MAIN_CITY_TAB)
    time.sleep(2)
    logger.info("=== step1: 点主城 tab 后 ===")
    dump(ocr_helper, "1_after_city")

    r = find_text_and_click_safe("宝库", regions=[9], use_cache=False, timeout=3)
    logger.info("点宝库 -> %r (bool=%s)", r, bool(r))
    time.sleep(2.5)
    logger.info("=== step2: 点宝库后 ===")
    dump(ocr_helper, "2_after_vault")
    return 0


if __name__ == "__main__":
    sys.exit(main())
