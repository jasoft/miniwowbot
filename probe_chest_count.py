#!/usr/bin/env python3
# -*- encoding:utf8 -*-
"""临时诊断脚本：OCR 读宝库面板，打印全部文字 + 坐标。

用于确认「亡灵宝箱 存量/每日上限」这行数字的OCR 判据。
不修改任何项目代码。

用法::

    python probe_chest_count.py [config_name] [emulator]
"""

import logging
import sys

from auto_dungeon_container import get_container
from auto_dungeon_core import initialize_configs
from auto_dungeon_device import DeviceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    """初始化设备并打印宝库面板上的全部 OCR 文字。

    Returns:
        进程退出码，0 表示成功读到文字。
    """
    config_name = sys.argv[1] if len(sys.argv) > 1 else "warrior"
    emulator = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.150:5555"

    initialize_configs(f"configs/{config_name}.json")
    container = get_container()

    device_manager = DeviceManager()
    correction_map = container.config_loader.get_ocr_correction_map()
    device_manager.initialize(emulator_name=emulator, correction_map=correction_map)
    ocr_helper = device_manager.get_ocr_helper()

    items = ocr_helper.capture_and_get_all_texts(use_cache=False)
    print(f"=== 共{len(items)} 条 OCR 结果 ===")
    for it in items:
        text = it.get("text", "")
        conf = it.get("confidence", 0)
        center = it.get("center", ())
        box = it.get("box", it.get("bbox", ""))
        print(f"{center!s:>16}  conf={conf:.3f}  {text!r}  box={box}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
