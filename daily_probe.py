#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""临时诊断脚本：逐项执行指定配置的每日任务并记录成败。

用于定位「每日任务有些完不成」的具体失败项。复用项目既有的
``DailyCollectManager``，不修改任何项目代码。

用法::

    python daily_probe.py [config_name] [emulator]

默认 ``warrior`` / ``192.168.1.150:5555``。
"""

import logging
import sys
import time

from auto_dungeon_container import get_container
from auto_dungeon_core import initialize_configs
from auto_dungeon_device import DeviceManager
from auto_dungeon_daily import DailyCollectManager
from database import DungeonProgressDB

logger = logging.getLogger("daily_probe")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    """逐个执行每日任务并打印成败汇总。

    Returns:
        进程退出码，未完成的任务数 > 0 时为 1。
    """
    config_name = sys.argv[1] if len(sys.argv) > 1 else "warrior"
    emulator = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.150:5555"

    initialize_configs(f"configs/{config_name}.json")
    container = get_container()

    # 设备初始化（复用项目既有 DeviceManager）
    device_manager = DeviceManager()
    correction_map = container.config_loader.get_ocr_correction_map()
    device_manager.initialize(emulator_name=emulator, correction_map=correction_map)
    container.emulator_manager = device_manager.emulator_manager
    container.ocr_helper = device_manager.get_ocr_helper()
    container.game_actions = device_manager.get_game_actions()
    container.target_emulator = device_manager.get_target_emulator()

    # 诊断期间静音 Bark 通知，避免打扰
    import auto_dungeon_daily as daily_mod

    daily_mod.send_notification = lambda *a, **k: None

    tasks = [t["name"] for t in container.config_loader.daily_tasks if t.get("selected", True)]
    db_config = container.config_loader.get_config_name()

    results: list[tuple[str, bool, float]] = []
    with DungeonProgressDB(config_name=db_config) as db:
        manager = DailyCollectManager(container.config_loader, db)
        logger.info("=" * 60)
        logger.info("🧪 每日任务逐项诊断: config=%s, 任务数=%d", db_config, len(tasks))
        logger.info("=" * 60)
        for idx, name in enumerate(tasks, 1):
            logger.info("\n--- [%d/%d] %s ---", idx, len(tasks), name)
            started = time.time()
            try:
                ok = manager.execute_task(name)
            except Exception as exc:  # 单任务异常不阻断后续诊断
                logger.error("❌ %s 抛异常: %s", name, exc)
                ok = False
            elapsed = time.time() - started
            results.append((name, bool(ok), elapsed))
            logger.info(">>> [%d/%d] %s => %s (%.1fs)", idx, len(tasks), name, ok, elapsed)

    logger.info("\n" + "=" * 60)
    logger.info("📋 诊断汇总 (config=%s)", db_config)
    logger.info("=" * 60)
    failed = 0
    for name, ok, elapsed in results:
        if not ok:
            failed += 1
        logger.info("%s %-12s %6.1fs", "✅" if ok else "❌", name, elapsed)
    logger.info("=" * 60)
    logger.info("成功 %d / 共 %d，失败 %d", len(results) - failed, len(results), failed)

    with DungeonProgressDB(config_name=db_config) as db:
        logger.info("💾 今日已记录的日常任务: %s", db.get_today_completed_dungeons(include_special=True))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
