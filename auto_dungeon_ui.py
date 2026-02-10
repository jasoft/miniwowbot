"""
auto_dungeon UI 交互模块
"""

import logging
from typing import Any, Dict, List, Optional

from airtest.core.api import touch

from auto_dungeon_config import CLICK_INTERVAL
from auto_dungeon_container import get_container
from auto_dungeon_utils import sleep
from coordinates import BACK_BUTTON

logger = logging.getLogger(__name__)

# ====== 文本查找函数 ======


def find_text(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """文本查找"""
    ga = get_container().game_actions
    if ga:
        return ga.find_text(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return None


def text_exists(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """检查文本是否存在"""
    ga = get_container().game_actions
    if ga:
        return ga.text_exists(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return None


def find_text_and_click(*args, **kwargs) -> bool:
    """文本查找并点击"""
    ga = get_container().game_actions
    if ga:
        logger.info(f"🔍 查找并点击文本: {args}")
        return ga.find_text_and_click(*args, **kwargs)
    raise RuntimeError("GameActions 未初始化")


def find_text_and_click_safe(*args, **kwargs) -> bool:
    """文本查找并点击（安全版本）"""
    ga = get_container().game_actions
    if ga:
        return ga.find_text_and_click_safe(*args, **kwargs)
    return kwargs.get("default_return", False)


def find_all_texts(*args, **kwargs) -> List[Dict[str, Any]]:
    """查找所有匹配的文本"""
    ga = get_container().game_actions
    if ga:
        return ga.find_all_texts(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return []


def find_all(*args, **kwargs):
    """查找所有匹配的元素"""
    ga = get_container().game_actions
    if ga:
        return ga.find_all(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return []


# ====== UI 交互函数 ======


def click_back() -> bool:
    """点击返回按钮"""
    try:
        touch(BACK_BUTTON)
        sleep(CLICK_INTERVAL)
        logger.info("🔙 点击返回按钮")
        return True
    except Exception as e:
        logger.error(f"❌ 返回失败: {e}")
        return False


def click_free_button() -> bool:
    """点击免费按钮"""
    free_words = ["免费"]
    for word in free_words:
        if find_text_and_click_safe(word, timeout=3, use_cache=False, regions=[8]):
            logger.info(f"💰 点击了免费按钮: {word}")
            return True
    logger.warning("⚠️ 未找到免费按钮")
    return False


def switch_to(section_name: str) -> Optional[Dict[str, Any]]:
    """切换到指定区域"""
    logger.info(f"🌍 切换到: {section_name}")
    return find_text_and_click(section_name, regions=[7, 8, 9])


def sell_trashes() -> None:
    """卖垃圾"""
    logger.info("💰 卖垃圾")
    click_back()
    if find_text_and_click_safe("装备", regions=[7, 8, 9]):
        if find_text_and_click_safe("整理售卖", regions=[7, 8, 9]):
            touch((462, 958))
            sleep(1)
        else:
            raise Exception("❌ 点击'整理售卖'按钮失败")
    else:
        raise Exception("❌ 点击'装备'按钮失败")
    click_back()
    click_back()
