"""
auto_dungeon 导航模块
"""

import logging
import os
import time
from datetime import datetime

from airtest.core.api import (
    keyevent,
    shell,
    touch,
    wait,
    exists,
    snapshot,
)
from airtest.core.error import TargetNotFoundError

from auto_dungeon_utils import sleep
from auto_dungeon_ui import find_text_and_click_safe
from auto_dungeon_config import (
    ENTER_GAME_BUTTON_TEMPLATE,
    GIFTS_TEMPLATE,
    MAP_DUNGEON_TEMPLATE,
    LAST_OCCURRENCE,
)
from coordinates import (
    BACK_BUTTON,
    CLOSE_ZONE_MENU,
    MAP_BUTTON,
)

logger = logging.getLogger(__name__)


def save_error_screenshot(operation_name: str) -> str:
    """保存错误截图到log目录，返回文件路径"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_dir = os.path.join(os.getcwd(), "log")
        os.makedirs(log_dir, exist_ok=True)
        filename = os.path.join(log_dir, f"error_{operation_name}_{timestamp}.png")
        snapshot(filename=filename)
        logger.debug(f"📸 错误截图已保存: {filename}")
        return filename
    except Exception as e:
        logger.debug(f"📸 保存错误截图失败: {e}")
        return ""

def open_map() -> None:
    """打开地图"""
    back_to_main()
    touch(MAP_BUTTON)
    logger.info("🗺️ 打开地图")
    sleep(2, "等待地图加载完毕")


def is_on_map() -> bool:
    """检查是否在地图界面"""
    return exists(MAP_DUNGEON_TEMPLATE)


def is_main_world() -> bool:
    """检查是否在主世界"""
    try:
        result = wait(GIFTS_TEMPLATE, timeout=0.3, interval=0.1)
        return bool(result)
    except Exception:
        return False


def is_on_character_selection(timeout: int = 30) -> bool:
    """检查是否在角色选择界面"""
    try:
        logger.info("🔍 等待进入角色选择界面...")
        wait(ENTER_GAME_BUTTON_TEMPLATE, timeout=timeout, interval=0.1)
        return True
    except TargetNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"检测角色选择界面时发生异常: {e}")
    return False


def back_to_main(max_duration: float = 15, backoff_interval: float = 0.2) -> None:
    """返回主界面"""
    logger.info("🔙 返回主界面")
    start_time = time.time()
    attempt = 0

    while True:
        if is_main_world():
            logger.info("✅ 已回到主界面")
            return

        elapsed = time.time() - start_time
        if elapsed >= max_duration:
            message = f"back_to_main 超时，已等待 {elapsed:.1f} 秒仍未检测到主界面"
            logger.error(message)
            raise TimeoutError(message)

        attempt += 1

        for _ in range(3):
            try:
                touch(BACK_BUTTON)
            except Exception as e:
                logger.warning(f"⚠️ 发送返回点击失败: {e}")
                break
            sleep(0.1)

        if attempt % 3 == 0:
            try:
                keyevent("BACK")
            except Exception as e:
                logger.warning(f"⚠️ 系统返回键发送失败: {e}")

        if attempt % 5 == 0:
            try:
                shell("input keyevent 4")
            except Exception as e:
                logger.debug(f"ADB 返回指令失败: {e}")

        sleep(backoff_interval)


def switch_to_zone(zone_name: str, max_attempts: int = 3) -> bool:
    """切换到指定区域，最多重试max_attempts次"""
    for attempt in range(max_attempts):
        logger.info(f"\n{'=' * 50}")
        logger.info(f"🌍 切换区域: {zone_name} (第 {attempt + 1}/{max_attempts} 次尝试)")
        logger.info(f"{ '=' * 50}")

        find_text_and_click_safe("切换区域", timeout=10)

        if find_text_and_click_safe(zone_name, timeout=10, occurrence=2):
            logger.info(f"✅ 成功切换到: {zone_name}")
            touch(CLOSE_ZONE_MENU)
            return True

        logger.error(f"❌ 切换失败: {zone_name} (第 {attempt + 1}/{max_attempts} 次)")

        if attempt < max_attempts - 1:
            logger.info("🔄 关闭弹窗后重试...")
            find_text_and_click_safe("切换区域", timeout=10)
            sleep(1)

    logger.error(f"❌ 切换区域失败，已重试 {max_attempts} 次: {zone_name}")
    save_error_screenshot("switch_to_zone")
    return False


def focus_and_click_dungeon(dungeon_name: str, zone_name: str, max_attempts: int = 2) -> bool:
    """尝试聚焦到指定副本并点击"""
    for attempt in range(max_attempts):
        use_cache = attempt == 0
        result = find_text_and_click_safe(
            dungeon_name,
            timeout=6,
            occurrence=LAST_OCCURRENCE,
            use_cache=use_cache,
        )
        if result:
            return True
        logger.warning(f"⚠️ 未能找到副本: {dungeon_name} (第 {attempt + 1}/{max_attempts} 次尝试)")
        if attempt < max_attempts - 1:
            logger.info("🔄 重新打开地图并刷新区域后再试")
            open_map()
            if not switch_to_zone(zone_name):
                logger.warning(f"⚠️ 刷新区域失败: {zone_name}")
                continue
            sleep(1)
    save_error_screenshot("focus_and_click_dungeon")
    return False
