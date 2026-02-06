"""升级行为树的动作处理器。"""

from __future__ import annotations

import logging
import os
import time

import requests
from airtest.core.api import exists, sleep, snapshot, swipe, touch
from config import BARK_URL
from state import WorldState

from color_helper import ColorHelper

logger = logging.getLogger(__name__)


def send_notification(title: str, content: str) -> None:
    """发送 Bark 通知。

    Args:
        title: 通知标题。
        content: 通知内容。
    """
    try:
        requests.get(f"{BARK_URL}/{title}/{content}", timeout=5)
    except Exception as exc:
        logger.error("Bark 通知发送失败: %s", exc)


def should_preempt(state: WorldState) -> bool:
    """检查当前动作是否应被抢占。

    Args:
        state: 共享的世界状态。

    Returns:
        True 如果检测到高优先级任务完成。
    """
    return state.signals.get("task_complete_pos") is not None


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

    state.last_task_time = time.time()
    sleep(2)
    touch((363, 867))
    logger.info("任务已完成")

    sleep(2)
    touch((363, 867))
    logger.info("接受下一个任务")
    sleep(2)

    clear_signal(state, "task_complete_pos")


def action_request_task(state: WorldState) -> None:
    """处理任务请求流程。

    Args:
        state: 共享的世界状态。
    """
    request_el = state.signals.get("request_task_el")
    if not request_el:
        return

    request_el.click()
    sleep(1.5)

    tasks_available = False
    for _ in range(5):
        if should_preempt(state):
            return
        if state.actions.find_all(use_cache=False).contains("支线").first().click():
            sleep(1)
            touch((358, 865))
            tasks_available = True
        else:
            swipe((360, 900), (360, 300))

    if not tasks_available:
        logger.warning("未找到支线任务，正在切换区域")
        switch_el = state.actions.find("切换区域")
        if switch_el:
            switch_el.click()
        else:
            logger.warning("未找到切换区域元素")
            return

        temp_path = os.path.join(state.ocr.temp_dir, "task_request.png")
        snapshot(filename=temp_path)

        ocr_results = state.ocr.get_all_texts_from_image(temp_path)
        green_pos = ColorHelper.find_green_text(temp_path, ocr_results)

        if green_pos:
            logger.info("检测到当前区域（绿色文字）: %s", green_pos)
            next_area_pos = (green_pos[0], green_pos[1] + 50)
            logger.info("点击下一个区域: %s", next_area_pos)
            touch(next_area_pos)
            sleep(1)
        else:
            logger.warning("未找到绿色文字，需要手动选择")
            send_notification("副本助手 - 错误", "未找到绿色文字")

        if os.path.exists(temp_path):
            os.remove(temp_path)

    back_to_main(state)
    clear_signal(state, "request_task_el")


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
    touch((160, 112))
    sleep(1)
    goto_next_place(state)
    clear_signal(state, "xp_full")


def action_timeout_recovery(state: WorldState) -> None:
    """从任务超时中恢复。

    Args:
        state: 共享的世界状态。
    """
    logger.warning("任务超时，强制导航恢复")

    back_to_main(state)
    touch((65, 265))
    goto_next_place(state)
    state.last_task_time = time.time()


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


def goto_next_place(state: WorldState) -> None:
    """导航到下一个地点。

    Args:
        state: 共享的世界状态。
    """
    try:
        if not state.actions.find_all(use_cache=False).equals("前往").first().click():
            return

        sleep(1)
        for _ in range(5):
            if should_preempt(state):
                return
            arrow = exists(state.templates["arrow"])
            if not arrow:
                continue
            touch((arrow[0], arrow[1] + 100))
            sleep(1)
            if state.actions.find("声望商店"):
                touch((355, 780))
                sleep(30)
            elif state.actions.find("免费", use_cache=False).click():
                logger.info("检测到免费副本，正在进入")
                sleep(3)
                sell_trash(state)
                touch((357, 1209))
            else:
                state.failed_in_dungeon = True
                fail_msg = "未找到免费副本按钮"
                logger.warning(fail_msg)
                send_notification("副本助手 - 错误", fail_msg)
                back_to_main(state)
            return
    except Exception as exc:
        logger.error("导航失败: %s", exc)
        back_to_main(state)


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
        touch((719, 1))
