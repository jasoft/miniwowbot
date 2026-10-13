#!/usr/bin/env python3
# -*- encoding:utf8 -*-
"""临时诊断脚本：逐项验证「主城→ 宝库」入口的点击与OCR 读取行为。

用法::

    python probe_chest_entry.py [config_name] [emulator]
"""

import logging
import sys
import time

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
logger = logging.getLogger("probe_entry")


def main() -> int:
    """逐步验证入口点击结果并打印返回值的真实形态。

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

    back_to_main()

    r1 = find_text_and_click_safe("主城", regions=[9])
    logger.info("find('主城', regions=[9]) -> %r  bool=%s", r1, bool(r1))
    time.sleep(1.5)

    r2 = find_text_and_click_safe("宝库", regions=[9])
    logger.info("find('宝库', regions=[9]) -> %r  bool=%s", r2, bool(r2))
    time.sleep(2)

    ocr = device_manager.get_ocr_helper()
    for it in ocr.capture_and_get_all_texts(use_cache=False):
        text = it.get("text", "")
        if "/" in text or "宝箱" in text or "今日" in text or "钥匙" in text:
            logger.info("  %s conf=%.3f %r", it.get("center"), it.get("confidence", 0), text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
