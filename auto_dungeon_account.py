"""
auto_dungeon 账号管理模块
"""

import logging
import time

from airtest.core.api import (
    start_app,
    stop_app,
    touch,
    swipe,
    wait,
)
from airtest.core.error import TargetNotFoundError

from auto_dungeon_container import get_container
from auto_dungeon_ui import find_text, find_text_and_click_safe, find_text_and_click
from auto_dungeon_navigation import is_on_character_selection, save_error_screenshot
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
    result = find_text(char_class, similarity_threshold=0.8, use_cache=False)

    if result and result.get("found"):
        pos = result["center"]
        click_x = pos[0]
        click_y = pos[1] - 60
        logger.info(f"👆 点击角色位置: ({click_x}, {click_y})")
        touch((click_x, click_y))
        sleep(1)
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        logger.error(f"❌ 未找到职业: {char_class}")
        save_error_screenshot("select_character")
        raise RuntimeError(f"无法找到职业: {char_class}")

    find_text_and_click("进入游戏", regions=[5])
    wait_for_main()


def wait_for_main(timeout: int = 300) -> None:
    """等待回到主界面"""
    logger.info("⏳ 等待战斗结束...")
    start_time = time.time()
    try:
        result = wait(GIFTS_TEMPLATE, timeout=timeout, interval=0.5)
        if result:
            elapsed = time.time() - start_time
            logger.info(f"✅ 战斗结束，用时 {elapsed:.1f} 秒")
    except Exception as e:
        logger.error(f"⏱️ 等待 GIFTS_TEMPLATE 超时或出错: {e}")
        raise TimeoutError("等待主界面超时")
