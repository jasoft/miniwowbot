"""
auto_dungeon 账号管理模块
"""

import logging
import time
from typing import Optional

from airtest.core.api import (
    start_app,
    stop_app,
    touch,
    swipe,
    wait,
)
from auto_dungeon_container import get_container
from auto_dungeon_ui import find_text, find_text_and_click_safe, find_text_and_click
from auto_dungeon_navigation import (
    describe_foreground,
    is_on_character_selection,
    save_error_screenshot,
    screenshot_is_blank,
)
from auto_dungeon_utils import sleep
from coordinates import (
    ACCOUNT_AVATAR,
    ACCOUNT_DROPDOWN_ARROW,
    ACCOUNT_LIST_SWIPE_START,
    ACCOUNT_LIST_SWIPE_END,
    LOGIN_BUTTON,
)
from auto_dungeon_config import GIFTS_TEMPLATE

logger = logging.getLogger(__name__)

# 查找角色职业的最大尝试次数（应对截图/OCR 抖动）。
# 仅统计「画面正常但找不到该文字」的失败 —— 画面全黑另有独立预算，见下。
CHARACTER_FIND_RETRIES = 3

# 画面全黑（游戏正在切换场景/加载）时允许的**额外**等待次数。
#
# 2026-10-08 06:06 真机实测：mage_alt 冷启动时，游戏在「判定已进入角色选择界面」
# 与「OCR 查找职业」之间发生了场景切换（模拟器广告退出 + 转屏），这 3~5 秒内截图
# 整幅几乎全黑，OCR 读不到任何文字，被误报成「未找到职业: 法师」→ 整个配置被炸掉
# 重跑一轮（约 1 分钟）。黑屏不是"没有这个文字"，而是"画面还没渲染出来"，
# 正确做法是**等画面恢复再重试**，因此给它独立预算、不占用 CHARACTER_FIND_RETRIES。
#
# 上限与 CHARACTER_RETRY_INTERVAL_SECONDS 一起把本函数内最长等待控制在数十秒量级
# —— 必须显著小于编排器的日志停滞阈值
# （cron_run_all_dungeons.LOG_IDLE_TIMEOUT_SECONDS = 180），否则会被看门狗误判僵死
# 并连模拟器一起重启；而且每次重试都会打日志，不存在静默阻塞。
CHARACTER_BLANK_SCREEN_MAX_RETRIES = 15

# 查找职业失败后、下一次尝试前的等待秒数。
CHARACTER_RETRY_INTERVAL_SECONDS = 2.0

def switch_account(account_name: str) -> None:
    """切换账号"""
    logger.info(f"切换账号: {account_name}")
    stop_app("com.ms.ysjyzr")
    sleep(2)
    start_app("com.ms.ysjyzr")
    try:
        find_text("进入游戏", timeout=120, regions=[5])
        touch(ACCOUNT_AVATAR)
        sleep(2)
        find_text_and_click_safe("切换账号", regions=[2, 3])
    except Exception:
        logger.warning("⚠️ 未找到切换账号按钮，可能处于登录界面")
    find_text("最近登录", timeout=20, regions=[5])
    touch(ACCOUNT_DROPDOWN_ARROW)

    success = False
    for _ in range(10):
        if find_text_and_click_safe(
            account_name, occurrence=2, use_cache=False, regions=[4, 5, 6, 7, 8, 9]
        ):
            success = True
            break
        swipe(ACCOUNT_LIST_SWIPE_START, ACCOUNT_LIST_SWIPE_END)

    if not success:
        save_error_screenshot("switch_account")
        raise Exception(f"Failed to find and click account '{account_name}' after 10 tries")
    touch(LOGIN_BUTTON)


def select_character(char_class: str) -> None:
    """选择角色"""
    logger.info(f"⚔️ 选择角色: {char_class}")

    em = get_container().error_dialog_monitor
    if em:
        em.handle_once()

    in_selection = is_on_character_selection(timeout=120)
    if not in_selection:
        logger.error("❌ 未在角色选择界面，无法选择角色")
        save_error_screenshot("select_character")
        raise RuntimeError("未在角色选择界面，无法选择角色")

    sleep(3, "等待角色选择界面加载完毕")
    logger.info(f"🔍 查找职业: {char_class}")

    # 查找职业时截图/OCR 偶发抖动（minicap 失败、adb 瞬时不可用）会让 find_text
    # 抛异常或返回空结果；过去一次失败就抛 RuntimeError 并重启整个流程，
    # 现在先就地重试几次，并把真实异常打出来，避免被"未找到职业"掩盖。
    #
    # 2026-10-08 补充第三种情况：游戏正在切换场景/加载时，截图**整幅全黑**。
    # 此时"OCR 读不到任何文字"与"画面上确实没有该文字"表现一致，但语义完全不同 ——
    # 前者只需等画面恢复。若按后者处理，就会白扔一轮（停/重启游戏 + 重跑配置）。
    # 因此画面全黑走独立预算，不计入普通失败次数。
    result = None
    last_error: Optional[str] = None
    normal_failures = 0
    blank_waits = 0
    while True:
        try:
            result = find_text(char_class, similarity_threshold=0.8, use_cache=False)
        except Exception as exc:
            result = None
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                f"⚠️ 查找职业出现异常（第 {normal_failures + 1}/{CHARACTER_FIND_RETRIES} 次）: "
                f"{last_error}"
            )
        if result and result.get("found"):
            break

        if screenshot_is_blank():
            blank_waits += 1
            if blank_waits > CHARACTER_BLANK_SCREEN_MAX_RETRIES:
                logger.error(f"❌ 画面持续全黑 {blank_waits - 1} 次仍未恢复，放弃查找职业")
                break
            logger.warning(
                f"⚠️ 截图全黑（游戏正在切换场景/加载中），等画面恢复后重试"
                f"（第 {blank_waits}/{CHARACTER_BLANK_SCREEN_MAX_RETRIES} 次）"
            )
        else:
            normal_failures += 1
            if normal_failures >= CHARACTER_FIND_RETRIES:
                break
            logger.info(f"未找到职业 {char_class}，准备第 {normal_failures + 1} 次重试")

        sleep(CHARACTER_RETRY_INTERVAL_SECONDS, f"等待画面就绪后重新查找职业 {char_class}")

    if result and result.get("found"):
        pos = result["center"]
        click_x = pos[0]
        click_y = pos[1] - 60
        logger.info(f"👆 点击角色位置: ({click_x}, {click_y})")
        touch((click_x, click_y))
        sleep(1)
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        detail = f"（最后一次异常: {last_error}）" if last_error else ""
        if blank_waits:
            detail += f"（期间检测到 {blank_waits} 次全黑画面）"
        logger.error(f"❌ 未找到职业: {char_class}{detail}")
        save_error_screenshot("select_character")
        raise RuntimeError(f"无法找到职业: {char_class}{detail}")

    find_text_and_click("进入游戏", regions=[5])
    wait_for_main()


# 等待主界面时的心跳间隔（秒）。必须显著小于编排器的日志停滞阈值
# （cron_run_all_dungeons.LOG_IDLE_TIMEOUT_SECONDS = 180），否则看门狗会把
# 「正在正常等待战斗结束」的会话判成僵死并杀掉重启。
WAIT_FOR_MAIN_HEARTBEAT_SECONDS = 30
# 默认超时。刻意收敛到小于看门狗阈值，让"真卡住"时由本函数自己超时抛出，
# 而不是被外部看门狗连模拟器一起杀掉 —— 后者代价是重开一轮模拟器（约 4 分钟）。
WAIT_FOR_MAIN_DEFAULT_TIMEOUT = 150
# 等待主界面超时时落盘的错误截图名。
# 2026-10-07 实测：mage_alt 在「进入游戏 → 等主界面」这段卡满 150 秒，而脚本侧
# **零画面信息**，只能靠 BlueStacks 的 Player.log 反推"游戏一直在跑但画面没推进"。
# 补上截图 + 前台应用后，下次一眼就能看到卡在哪个画面。
WAIT_FOR_MAIN_TIMEOUT_SCREENSHOT_NAME = "main_screen_timeout"


def wait_for_main(timeout: int = WAIT_FOR_MAIN_DEFAULT_TIMEOUT) -> None:
    """等待回到主界面（带心跳日志，避免看门狗误判僵死）。

    过去这里直接调用 airtest 的 ``wait()`` 阻塞最长 ``timeout`` 秒且**中途不打任何
    日志**。而编排器 ``cron_run_all_dungeons`` 用会话日志的 ``(mtime, size)`` 当作
    「会话是否还活着」的唯一信号，超过 ``LOG_IDLE_TIMEOUT_SECONDS``(180 秒) 无更新
    就判定僵死，杀掉会话并重启模拟器。当 ``timeout``(默认 300) > 180 时，
    只要这一次等待真的卡满 180 秒，就必然被误杀 —— 2026-09-30 06:06:57 实测命中。

    现在改为分段轮询：每 ``WAIT_FOR_MAIN_HEARTBEAT_SECONDS`` 秒打一条心跳日志，
    命中模板立即返回，累计超过 ``timeout`` 才抛 ``TimeoutError``。

    超时抛出前会落一张错误截图，并把**超时瞬间的前台应用**写进日志 —— 2026-10-07
    那次超时因为没有任何画面信息，只能靠模拟器日志反推，无法直接看出卡在哪个画面。

    Args:
        timeout: 最长等待秒数，默认 150 秒（小于编排器 180 秒的日志停滞阈值）。

    Raises:
        TimeoutError: 等待超过 ``timeout`` 秒仍未回到主界面。
    """
    logger.info(f"⏳ 等待战斗结束...(最长 {timeout} 秒)")
    start_time = time.time()
    deadline = start_time + timeout
    last_heartbeat = start_time
    while True:
        try:
            if wait(GIFTS_TEMPLATE, timeout=0.5, interval=0.5):
                elapsed = time.time() - start_time
                logger.info(f"✅ 战斗结束，用时 {elapsed:.1f} 秒")
                return
        except Exception as e:  # noqa: BLE001 - 单次轮询异常不应中断整个等待
            logger.debug(f"等待主界面轮询异常（继续重试）: {e}")

        now = time.time()
        if now >= deadline:
            elapsed = now - start_time
            logger.error(
                f"⏱️ 等待主界面超时（已等待 {elapsed:.1f} 秒）；"
                f"超时瞬间前台: {describe_foreground()}"
            )
            save_error_screenshot(WAIT_FOR_MAIN_TIMEOUT_SCREENSHOT_NAME)
            raise TimeoutError("等待主界面超时")
        if now - last_heartbeat >= WAIT_FOR_MAIN_HEARTBEAT_SECONDS:
            last_heartbeat = now
            elapsed_text = f"已等待 {now - start_time:.0f} 秒，上限 {timeout} 秒"
            logger.info(f"⏳ 等待主界面中...（{elapsed_text}）")
