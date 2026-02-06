"""
auto_dungeon 战斗模块
"""

import logging
import time

from airtest.core.api import touch, wait
from tqdm import tqdm

from auto_dungeon_config import AUTOCOMBAT_TEMPLATE
from auto_dungeon_navigation import is_main_world
from auto_dungeon_ui import find_text_and_click_safe
from auto_dungeon_utils import check_stop_signal, sleep
from coordinates import SKILL_POSITIONS

logger = logging.getLogger(__name__)


def auto_combat(completed_dungeons: int = 0, total_dungeons: int = 0) -> None:
    """自动战斗"""
    logger.info("⚔️ 开始自动战斗")
    find_text_and_click_safe("战斗", regions=[8])

    try:
        builtin_auto_combat_activated = bool(wait(AUTOCOMBAT_TEMPLATE, timeout=2, interval=0.1))
    except Exception:
        builtin_auto_combat_activated = False

    logger.info(f"内置自动战斗: {builtin_auto_combat_activated}")

    if total_dungeons > 0:
        desc = f"⚔️ 战斗进度 [{completed_dungeons}/{total_dungeons}]"
        bar_format = "{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        total_value = total_dungeons
    else:
        desc = "⚔️ 战斗进度"
        bar_format = "{desc} |{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]"
        total_value = 60

    with tqdm(
        total=total_value,
        desc=desc,
        unit="" if total_dungeons > 0 else "s",
        ncols=80,
        bar_format=bar_format,
        initial=completed_dungeons if total_dungeons > 0 else 0,
    ) as pbar:
        start_time = time.time()
        last_update = start_time
        combat_start = time.monotonic()
        combat_timeout_seconds = 180

        while not is_main_world():
            if check_stop_signal():
                pbar.close()
                raise KeyboardInterrupt("检测到停止信号，退出自动战斗")

            if time.monotonic() - combat_start >= combat_timeout_seconds:
                pbar.close()
                logger.error("⏱️ 自动战斗超时（180秒），抛出异常")
                raise TimeoutError("自动战斗超时（180秒）")

            current_time = time.time()

            if current_time - last_update >= 0.5:
                if total_dungeons > 0:
                    pass
                else:
                    update_amount = current_time - last_update
                    pbar.update(update_amount)
                last_update = current_time

            if builtin_auto_combat_activated:
                sleep(1)
                continue

            positions = SKILL_POSITIONS.copy()
            touch(positions[4])
            sleep(1)

        if total_dungeons > 0:
            pbar.update(1)
        else:
            remaining = total_value - (time.time() - start_time)
            if remaining > 0:
                pbar.update(remaining)
        pbar.close()

    logger.info("✅ 战斗完成")
