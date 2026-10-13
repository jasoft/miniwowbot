#!/usr/bin/env python3
# -*- encoding:utf8 -*-
"""临时诊断脚本：直接验证 region 9 能否 OCR 到「宝库」。

用法::

    python probe_region9.py [config_name] [emulator]
"""

import logging
import sys
import time

from auto_dungeon_container import get_container
from auto_dungeon_core import initialize_configs
from auto_dungeon_device import DeviceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("probe_region9")


def main() -> int:
    """在region 9 内OCR 并打印全部文字。

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

    logger.info("=== region 9 (use_cache=False) ===")
    for it in ocr_helper.capture_and_get_all_texts(use_cache=False, regions=[9]):
        logger.info("  %s conf=%.3f %r", it.get("center"), it.get("confidence", 0), it.get("text"))

    logger.info("=== find('宝库', regions=[9], use_cache=False) ===")
    ga = device_manager.get_game_actions()
    el = ga.find("宝库", regions=[9], use_cache=False, timeout=3)
    logger.info("  -> %r bool=%s center=%s", el, bool(el), getattr(el, "center", None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
