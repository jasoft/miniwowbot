"""
auto_dungeon 战斗模块
"""

import logging
import time

from airtest.core.api import touch, wait
from tqdm import tqdm

from auto_dungeon_config import AUTOCOMBAT_TEMPLATE
from auto_dungeon_navigation import describe_foreground, is_main_world, save_error_screenshot
from auto_dungeon_ui import tap_battle_entry_if_not_nav
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

#: 底部导航栏「战斗」页签的坐标（基准 720x1280）。
#:
#: 它是**角色面板的开关**：点一次展开、再点一次收起。超时自愈时用它把遮住战斗画面的
#: 面板收起来 —— 这是本项目既有的关面板手段（``weekly_soul_land.NAV_BATTLE`` 同一坐标，
#: 注释为「也用来关面板」）。**不要换成 ``keyevent 4``**：项目硬约定禁止用系统返回键
#: 关面板（会退出游戏/弹退出确认）。
BATTLE_NAV_TOGGLE_POSITION = (362, 1245)

#: 超时触发「收起遮挡面板」之后，额外再给战斗的观察轮数（每轮约 1 秒）。
#:
#: 取值依据：真机战斗上限约 130 秒，正常战斗此时早该结束；收起面板后画面恢复，
#: 剩下的一般只是结算动画 + 回主界面。90 秒足够，同时保证「面板收起也没用」
#: 时不会把一轮卡死拖成十几分钟。
COMBAT_PANEL_RECOVERY_ROUNDS = 90


def _toggle_battle_panel() -> bool:
    """点一次底部导航「战斗」页签，尝试收起遮挡战斗画面的角色面板。

    这是**尽力而为**的自愈动作，不保证成功：若面板本来就是关的，这一下反而会把它
    打开（该页签是 toggle）。因此调用方只应在"已经超时、本来就要失败"的分支里用它，
    并且必须给它一个有限的重试预算，绝不能靠它做正常流程。

    Returns:
        bool: True 表示点击动作已发出（不代表面板一定收起）。
    """
    try:
        touch(BATTLE_NAV_TOGGLE_POSITION)
        return True
    except Exception as exc:
        logger.warning(f"⚠️ 点击底部导航「战斗」失败: {exc}")
        return False


def auto_combat(completed_dungeons: int = 0, total_dungeons: int = 0) -> None:
    """自动战斗。

    Args:
        completed_dungeons: 已完成副本数（仅用于进度条展示与诊断日志）。
        total_dungeons: 副本总数（仅用于进度条展示与诊断日志）。

    Raises:
        KeyboardInterrupt: 检测到停止信号。
        TimeoutError: 等待 ``COMBAT_TIMEOUT_SECONDS`` 秒（含一次有界自愈）仍未回到主界面。

    Note:
        超时后**不再立刻** ``raise``，而是先做一次有界自愈：点一次底部导航「战斗」
        把可能遮挡画面的角色面板收起，再多观察 ``COMBAT_PANEL_RECOVERY_ROUNDS`` 轮。
        2026-10-26 ~ 11-06 的 5 次真机超时，错误截图里画面都被角色面板整块遮住、
        战斗其实一直在打（BOSS 血量在掉）；旧实现直接抛异常 → 停/重启模拟器重跑整轮，
        白耗约 4 分钟并误发一条「超时重启」。收起面板就能接着打完，代价小得多。
    """
    logger.info("⚔️ 开始自动战斗")
    tap_battle_entry_if_not_nav()

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

        # 超时自愈的状态：``recovery_pending`` 一旦置位就不再重复触发自愈（只给一次机会），
        # ``recovery_rounds_left`` 是自愈后允许继续观察的轮数，烧完即判失败。
        recovery_pending = False
        recovery_rounds_left = 0
        pbar_closed = False
        foreground = "unknown"
        screenshot_path = ""

        while not is_main_world():
            if check_stop_signal():
                pbar.close()
                raise KeyboardInterrupt("检测到停止信号，退出自动战斗")

            elapsed_seconds = time.monotonic() - combat_start

            if recovery_pending:
                recovery_rounds_left -= 1

            # 超时判定分两段：第一段到点后先做一次面板块自愈（recovery_pending 置位），
            # 第二段把自愈给的观察轮数烧完才算真失败。
            timed_out = elapsed_seconds >= COMBAT_TIMEOUT_SECONDS and not recovery_pending
            recovery_exhausted = recovery_pending and recovery_rounds_left <= 0

            if timed_out:
                pbar.close()
                pbar_closed = True
                # 超时分支必须留下「画面证据」：2026-10-26 06:13:59 / 06:24:57 两次真机超时，
                # 脚本侧连一张截图都没有（auto_dungeon_core 的 airtest_log(snapshot=True)
                # 也不落盘），只能靠 Player.log 反推「游戏进程一直活着」，无法回答
                # 「当时屏幕上到底是什么」。姊妹路径 wait_for_main（2026-10-07）与
                # is_on_character_selection（2026-10-08）早已补齐，本函数是漏项。
                screenshot_path = save_error_screenshot("auto_combat_timeout")
                foreground = describe_foreground()
                # 先自愈再判失败：2026-10-26/27/28、11-06 共 5 次真机超时的错误截图里，
                # 战斗画面都被「角色面板 + 底部『战斗』页签高亮」整块遮住，而 BOSS 血量
                # 一直在掉 —— 战斗其实在打，只是 is_main_world() 被面板挡住永远命中不了。
                # 收起面板就能接着打完，比停/重启模拟器重跑整轮（约 4 分钟）便宜得多。
                logger.warning(
                    f"⚠️ 自动战斗已等 {elapsed_seconds:.1f} 秒仍未回到主界面"
                    f"（阈值 {COMBAT_TIMEOUT_SECONDS} 秒），疑似画面被角色面板遮挡；"
                    f"点一次底部导航「战斗」尝试收起，再观察 {COMBAT_PANEL_RECOVERY_ROUNDS} 轮；"
                    f"内置自动战斗={builtin_auto_combat_activated}，"
                    f"前台: {foreground}，截图: {screenshot_path or '未生成'}"
                )
                recovery_pending = True
                recovery_rounds_left = COMBAT_PANEL_RECOVERY_ROUNDS if _toggle_battle_panel() else 0
                if not recovery_rounds_left:
                    logger.error("❌ 收起遮挡面板的动作没能发出，直接判定超时")
                continue

            if recovery_exhausted:
                logger.error(
                    f"⏱️ 自动战斗超时（{COMBAT_TIMEOUT_SECONDS}秒，实等 {elapsed_seconds:.1f} 秒），"
                    "已尝试收起遮挡面板仍未恢复，抛出异常；"
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
                elif not pbar_closed:
                    update_amount = current_time - last_update
                    pbar.update(update_amount)
                last_update = current_time

            if builtin_auto_combat_activated:
                sleep(1, "等待内置自动战斗")
                continue

            positions = SKILL_POSITIONS.copy()
            touch(positions[4])
            sleep(1, "等待下一次攻击")

        if recovery_pending:
            logger.warning(
                f"✅ 自动战斗超时后收起遮挡面板，画面恢复，战斗照常结束（白等 {COMBAT_TIMEOUT_SECONDS} 秒）"
            )

        if pbar_closed:
            pass
        elif total_dungeons > 0:
            pbar.update(1)
        else:
            remaining = total_value - (time.time() - start_time)
            if remaining > 0:
                pbar.update(remaining)
        if not pbar_closed:
            pbar.close()

    logger.info("✅ 战斗完成")
