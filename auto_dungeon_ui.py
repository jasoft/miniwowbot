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


# 「卖垃圾」的尝试次数与重试间隔。
# 真机实测「整理售卖」偶发点不到（2026-07-13 / 08-30 / 09-18 / 10-02，约三周一次；
# 2026-10-02 mage_alt 那次在 2 分钟后的下一轮卖垃圾就正常了）。旧实现直接抛异常，
# 整个会话被判「脚本异常退出」→ 编排器停/重启模拟器重跑一轮（约 2 分钟）+
# 推一条「程序发生错误」告警 —— 代价远大于「本轮不卖垃圾」。
SELL_TRASHES_MAX_ATTEMPTS = 3
SELL_TRASHES_RETRY_INTERVAL_SECONDS = 1.0


def _log_sell_trashes_failure(reason: str) -> None:
    """记录卖垃圾失败的诊断信息（错误截图 + 当前前台应用）。

    失败时脚本侧原本没有任何画面信息，事后只能靠模拟器日志反推「当时停在哪个
    画面」，所以放弃前先落一张截图并记下前台包名（永不抛异常）。

    Args:
        reason: 失败原因描述。

    Returns:
        None.
    """
    try:
        # 局部导入：auto_dungeon_navigation 在模块级反向依赖本模块，避免循环导入。
        from auto_dungeon_navigation import describe_foreground, save_error_screenshot

        screenshot = save_error_screenshot("sell_trashes")
        logger.error(
            "❌ 卖垃圾失败：%s；截图=%s，前台=%s",
            reason,
            screenshot or "(截图失败)",
            describe_foreground(),
        )
    except Exception as e:  # noqa: BLE001 - 纯诊断，不能反过来打断主流程
        logger.error("❌ 卖垃圾失败：%s（诊断信息收集失败: %s）", reason, e)


def sell_trashes(max_attempts: int = SELL_TRASHES_MAX_ATTEMPTS) -> bool:
    """卖垃圾：点「装备」→「整理售卖」→ 确认，然后返回主界面。

    任一步骤点不到时**有界重试**（每次重新走一遍完整序列），仍失败就记 ERROR、
    落诊断截图并返回 `False`，**不再抛异常**。理由是卖垃圾只是每 3 个副本一次的
    例行清理，本轮没做既不丢进度也不会重复通关（下一个周期会再来），
    而抛异常会让整个会话直接退出、编排器重跑一轮（约 2 分钟）。

    Args:
        max_attempts: 最多尝试次数。

    Returns:
        bool: 是否成功点完「整理售卖」并确认卖出。
    """
    logger.info("💰 卖垃圾")
    reason = "未知"
    for attempt in range(1, max_attempts + 1):
        click_back()
        if not find_text_and_click_safe("装备", regions=[7, 8, 9]):
            reason = "未找到「装备」入口"
        elif find_text_and_click_safe("整理售卖", regions=[7, 8, 9]):
            touch((462, 958))
            sleep(1)
            click_back()
            click_back()
            return True
        else:
            reason = "未找到「整理售卖」按钮"

        logger.warning("⚠️ 卖垃圾第 %d/%d 次失败：%s", attempt, max_attempts, reason)
        if attempt < max_attempts:
            sleep(SELL_TRASHES_RETRY_INTERVAL_SECONDS, "等待界面刷新后重试卖垃圾")

    _log_sell_trashes_failure(reason)
    return False
