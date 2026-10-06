"""升级行为树的动作处理器。"""

from __future__ import annotations

import logging
import time
from urllib.parse import quote

import requests
from airtest.core.api import sleep, touch
from config import BARK_URL
from dungeon_navigation import navigate_to_task, task_target
from state import WorldState

from task_workflow import click_text, read_task_screen, request_tasks

logger = logging.getLogger(__name__)


def send_notification(title: str, content: str) -> None:
    """发送 Bark 通知。

    Args:
        title: 通知标题。
        content: 通知内容。
    """
    if not BARK_URL:
        logger.warning("BARK_SERVER 未配置，未发送通知")
        return
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    try:
        response = requests.get(
            f"{BARK_URL}/{quote(title, safe='')}/{quote(content, safe='')}", timeout=5
        )
        if response.status_code != 200 or response.json().get("code") != 200:
            logger.error("Bark 未确认发送成功，HTTP 状态：%s", response.status_code)
    except (requests.RequestException, ValueError):
        logger.error("Bark 通知发送失败，网络请求异常或响应不是有效 JSON")


def should_preempt(state: WorldState) -> bool:
    """检查当前动作是否应被抢占。

    Args:
        state: 共享的世界状态。

    Returns:
        True 如果检测到高优先级任务完成。
    """
    return bool(state.signals.get("task_complete_pos"))


def clear_signal(state: WorldState, key: str) -> None:
    """清除信号值。

    Args:
        state: 共享的世界状态。
        key: 要清除的信号键。
    """
    state.signals[key] = None


def action_task_completion(state: WorldState) -> None:
    """处理任务完成流程。

    Args:
        state: 共享的世界状态。
    """
    pos = state.signals.get("task_complete_pos")
    if not pos:
        return

    touch(pos)
    logger.info("点击任务完成图标: %s", pos)

    sleep(1)
    if click_text(read_task_screen(state), "完成"):
        state.last_task_time = time.time()
        logger.info("任务已完成")
        if click_text(read_task_screen(state), "接受任务"):
            logger.info("已接受后续任务")
    back_to_main(state)
    clear_signal(state, "task_complete_pos")


def action_request_task(state: WorldState) -> None:
    """处理任务请求流程。

    Args:
        state: 共享的世界状态。
    """
    request_tasks(state)
    back_to_main(state)


def action_combat(state: WorldState) -> None:
    """执行战斗动作。

    Args:
        state: 共享的世界状态。
    """
    if not state.signals.get("in_combat"):
        return
    for i in range(5):
        touch((105 + i * 130, 560))


def action_dungeon_transition(state: WorldState) -> None:
    """前进到下一个副本或区域。

    Args:
        state: 共享的世界状态。
    """
    logger.info("推进副本/区域")
    navigate_active_tasks(state)
    clear_signal(state, "xp_full")


def action_timeout_recovery(state: WorldState) -> None:
    """从任务超时中恢复。

    Args:
        state: 共享的世界状态。
    """
    logger.warning("任务超时，强制导航恢复")

    navigate_active_tasks(state)
    state.last_task_time = time.time()
    logger.debug("超时恢复后更新last_task_time: %.2f", state.last_task_time)


def action_equip_item(state: WorldState) -> None:
    """当有可用物品时装备。

    Args:
        state: 共享的世界状态。
    """
    equip_el = state.signals.get("equip_el")
    if not equip_el:
        return
    equip_el.click()
    clear_signal(state, "equip_el")


def goto_next_place(state: WorldState) -> bool:
    """导航到下一个地点。

    Args:
        state: 共享的世界状态。

    Returns:
        确认进入目标地点时返回 True，未完成导航时返回 False。
    """
    if should_preempt(state):
        return False
    try:
        reason = navigate_to_task(state)
    except Exception:
        logger.exception("导航异常")
        reason = "导航发生异常，请检查运行日志"
    state.failed_in_dungeon = bool(reason)
    if not reason:
        state.last_task_time = time.time()
        return True
    logger.warning("导航暂未完成：%s", reason)
    now = time.time()
    if "免费次数已耗尽" not in reason and now >= state.navigation_notice_after:
        send_notification("副本助手 - 导航异常", reason)
        state.navigation_notice_after = now + 1800
    back_to_main(state)
    return False


def navigate_active_tasks(state: WorldState) -> None:
    """优先打开主线，等级任务没有地点时改做未完成的支线。

    Args:
        state: 共享的世界状态。
    """
    back_to_main(state)
    texts = read_task_screen(state)
    candidates = [
        item
        for item in texts
        if item.get("center")
        and item["center"][0] <= 110
        and 80 <= item["center"][1] <= 400
        and any(word in item.get("text", "") for word in ("通关", "消灭", "等级达到", "前往"))
    ]
    candidates.sort(
        key=lambda item: (
            item["center"][1] > 140,
            "通关" not in item.get("text", ""),
            item["center"][1],
        )
    )
    for item in candidates:
        if should_preempt(state):
            return
        touch(tuple(item["center"]))
        sleep(1)
        if task_target(read_task_screen(state)):
            if goto_next_place(state):
                return
        else:
            back_to_main(state)
    logger.info("当前任务没有可导航的地点，继续等待升级或领取任务")


def sell_trash(state: WorldState) -> None:
    """在副本界面出售垃圾物品。

    Args:
        state: 共享的世界状态。
    """
    touch((226, 1213))
    sleep(1)
    touch((446, 1108))
    sleep(1)
    touch((469, 954))
    back_to_main(state)


def back_to_main(state: WorldState, taps: int = 5) -> None:
    """通过点击返回回到主界面。

    Args:
        state: 共享的世界状态。
        taps: 返回点击次数。
    """
    for _ in range(taps):
        # 顶部有 Android 指针调试栏；点击弹窗外的右下空白才能可靠关闭地图。
        touch((710, 1150))
        sleep(0.3)
