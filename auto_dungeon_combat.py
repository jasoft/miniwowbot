"""
auto_dungeon 战斗模块
"""

import logging
import time

from airtest.core.api import touch, wait
from tqdm import tqdm

from auto_dungeon_config import AUTOCOMBAT_TEMPLATE
from auto_dungeon_navigation import describe_foreground, is_main_world, save_error_screenshot
from auto_dungeon_ui import find_text_and_click_safe
from auto_dungeon_utils import check_stop_signal, sleep
from coordinates import SKILL_POSITIONS

logger = logging.getLogger(__name__)

#: 一次战斗最长等待秒数。
#:
#: 取值依据（2026-10-26 体检按 ``开始自动战斗`` → ``战斗完成`` 重新量化）：
#: 法师 / 战士在「亡灵之地」11 个副本的战斗耗时中位数约 70~112 秒、上限约 130 秒，
#: 180 秒留了约 40% 余量。**它与看门狗阈值无关** —— 战斗循环每秒都会打一条
#: 「等待内置自动战斗」日志，看门狗不会把这段当成僵死。
#:
#: 已知边界：``古魔宝库`` 的历史耗时尾部可达 185 秒（364 次成功里有 38 次 >150 秒，
#: 另有 22 次在这条阈线上超时）。该副本现已从所有 config 置 ``selected: false``，
#: 若将来重新启用，需要为它单独放宽阈值，否则会周期性白跑一轮重启。
COMBAT_TIMEOUT_SECONDS = 180


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

        while not is_main_world():
            if check_stop_signal():
                pbar.close()
                raise KeyboardInterrupt("检测到停止信号，退出自动战斗")

            elapsed_seconds = time.monotonic() - combat_start
            if elapsed_seconds >= COMBAT_TIMEOUT_SECONDS:
                pbar.close()
                # 超时分支必须留下「画面证据」：2026-10-26 06:13:59 / 06:24:57 两次真机超时，
                # 脚本侧连一张截图都没有（auto_dungeon_core 的 airtest_log(snapshot=True)
                # 也不落盘），只能靠 Player.log 反推「游戏进程一直活着」，无法回答
                # 「当时屏幕上到底是什么」。姊妹路径 wait_for_main（2026-10-07）与
                # is_on_character_selection（2026-10-08）早已补齐，本函数是漏项。
                screenshot_path = save_error_screenshot("auto_combat_timeout")
                foreground = describe_foreground()
                logger.error(
                    f"⏱️ 自动战斗超时（{COMBAT_TIMEOUT_SECONDS}秒，实等 {elapsed_seconds:.1f} 秒），"
                    "抛出异常；"
                    f"内置自动战斗={builtin_auto_combat_activated}，"
                    f"进度 [{completed_dungeons}/{total_dungeons}]，"
                    f"超时瞬间前台: {foreground}，"
                    f"错误截图: {screenshot_path or '未生成'}"
                )
                raise TimeoutError(f"自动战斗超时（{COMBAT_TIMEOUT_SECONDS}秒）")

            current_time = time.time()

            if current_time - last_update >= 0.5:
                if total_dungeons > 0:
                    pass
                else:
                    update_amount = current_time - last_update
                    pbar.update(update_amount)
                last_update = current_time

            if builtin_auto_combat_activated:
                sleep(1, "等待内置自动战斗")
                continue

            positions = SKILL_POSITIONS.copy()
            touch(positions[4])
            sleep(1, "等待下一次攻击")

        if total_dungeons > 0:
            pbar.update(1)
        else:
            remaining = total_value - (time.time() - start_time)
            if remaining > 0:
                pbar.update(remaining)
        pbar.close()

    logger.info("✅ 战斗完成")
