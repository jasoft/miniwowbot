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


#: 底部导航栏「战斗」页签的文案。
BATTLE_NAV_TEXT = "战斗"

#: 底部导航栏的起始 y 坐标（基准 720x1280）。
#:
#: 「战斗」这个词在真机上有两个落点：底部导航栏的页签（真机实测稳定在
#: ``(361, 1243)`` / ``(362, 1245)``）和（可能存在）战斗界面里的按钮。页签本身是
#: **角色面板的开关（toggle）** —— 点一次展开、再点一次收起，``weekly_soul_land``
#: 里的 ``NAV_BATTLE`` 注释也明确写了「也用来关面板」。因此"点一下战斗"这种写法
#: 的后果取决于**奇偶性**：点两次等于没点，点一次就会把角色面板展开并盖住战斗画面。
BATTLE_NAV_BAND_Y = 1180


def tap_battle_entry_if_not_nav(timeout: float = 1) -> bool:
    """点击「战斗」按钮，但**绝不**点击底部导航栏的「战斗」页签。

    背景见 :data:`BATTLE_NAV_BAND_Y`：那个页签是角色面板的开关，点开之后面板会
    遮住战斗画面，``is_main_world()``（靠主世界「礼包」模板判定）就再也命中不了，
    战斗循环会一路空转到 180 秒超时，进而触发「超时重启」重跑整轮（约 4 分钟）。
    2026-10-26 / 10-27 / 10-28 / 11-06 共 5 次真机战斗超时的错误截图里，画面上
    都是「角色面板 + 底部『战斗』页签高亮」这一组特征。

    这里不再"盲点"，而是先取到命中的坐标再判断：命中的 y 落在底部导航栏内就
    **只记日志、不点击**。这样避免了用奇偶性去赌面板的开合状态 —— 既然无法确认
    点之前面板是开是关，就不去碰这个开关。

    Args:
        timeout: 文本查找超时秒数。

    Returns:
        bool: True 表示真的点了「战斗」（命中的不是导航页签）；False 表示没点
        （没找到，或只匹配到导航页签）。
    """
    ga = get_container().game_actions
    if not ga:
        logger.error("❌ GameActions 未初始化")
        return False

    try:
        element = ga.find(
            BATTLE_NAV_TEXT,
            regions=[8],
            raise_exception=False,
            timeout=timeout,
        )
    except Exception as exc:  # OCR/截图异常不应炸掉战斗流程
        logger.warning(f"⚠️ 查找「{BATTLE_NAV_TEXT}」失败: {exc}")
        return False

    if not element:
        logger.info(f"ℹ️ 未找到「{BATTLE_NAV_TEXT}」按钮，跳过点击")
        return False

    _, center_y = element.center
    if center_y >= BATTLE_NAV_BAND_Y:
        logger.info(
            f"ℹ️ 「{BATTLE_NAV_TEXT}」只匹配到底部导航页签 at {element.center}"
            f"（y≥{BATTLE_NAV_BAND_Y}，它是角色面板开关），跳过点击以免遮挡战斗画面"
        )
        return False

    try:
        element.click()
    except Exception as exc:
        logger.warning(f"⚠️ 点击「{BATTLE_NAV_TEXT}」失败: {exc}")
        return False

    logger.info(f"👆 点击了「{BATTLE_NAV_TEXT}」按钮 at {element.center}")
    return True


# 「卖垃圾」的尝试次数与重试间隔。
# 真机实测「整理售卖」偶发点不到（2026-07-13 / 08-30 / 09-18 / 10-02，约三周一次；
# 2026-10-02 法师小号实例（已下线）那次在 2 分钟后的下一轮卖垃圾就正常了）。旧实现直接抛异常，
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
