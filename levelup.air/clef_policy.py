"""将受约束动作映射到现有升级工作流。"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from actions import (
    action_combat,
    action_dungeon_transition,
    action_equip_item,
    action_request_task,
    action_task_completion,
    action_timeout_recovery,
)
from config import TASK_TIMEOUT
from state import WorldState

ACTION_HANDLERS: dict[str, Callable[[WorldState], None]] = {
    "complete": action_task_completion,
    "request": action_request_task,
    "advance": action_dungeon_transition,
    "equip": action_equip_item,
    "combat": action_combat,
    "recover": action_timeout_recovery,
}


def supplement_combat_signal(state: WorldState, texts: list[dict[str, Any]]) -> None:
    """用血量条和技能数字识别可用技能，保留副本战斗信号语义。

    Args:
        state: 需要补充战斗信号的世界状态。
        texts: 当前画面的完整 OCR 结果。
    """
    state.signals["combat_controls_visible"] = False
    if any(
        item.get("text", "").strip() in ("接受任务", "前往", "完成")
        or "任务清单" in item.get("text", "") for item in texts
    ):
        return
    health = any(
        re.fullmatch(r"[\d.KM]+/[\d.KM]+", item.get("text", ""), re.IGNORECASE)
        and item.get("center") and 395 <= item["center"][1] <= 445
        for item in texts
    )
    cooldowns = sum(
        bool(item.get("text", "").isdigit())
        and bool(item.get("center")) and 625 <= item["center"][1] <= 795
        for item in texts
    )
    if health and cooldowns >= 3:
        state.signals["combat_controls_visible"] = True


def allowed_actions(state: WorldState) -> list[str]:
    """根据新鲜检测信号给出可执行动作。

    Args:
        state: 当前世界状态。

    Returns:
        可执行动作名称，始终包含等待。
    """
    signals = state.signals
    if signals.get("task_complete_pos"):
        return ["complete", "wait"]
    if signals.get("in_combat"):
        return ["combat", "wait"]
    allowed = ["wait"]
    if signals.get("request_task_el") and time.time() >= state.request_retry_after:
        allowed.append("request")
    if signals.get("xp_full"):
        allowed.append("advance")
    if signals.get("equip_el"):
        allowed.append("equip")
    if signals.get("combat_controls_visible"):
        allowed.append("combat")
    if time.time() - state.last_task_time > TASK_TIMEOUT:
        allowed.append("recover")
    return allowed


def build_observation(state: WorldState, texts: list[dict[str, Any]]) -> dict[str, Any]:
    """提取可序列化且不包含凭据的游戏观察。

    Args:
        state: 当前世界状态。
        texts: 当前截图的 OCR 条目。

    Returns:
        提交模型的状态描述。
    """
    return {
        "goal": "持续升级：交接任务，清空本区任务后切下一大陆并接任务。",
        "allowed_actions": allowed_actions(state),
        "signals": {
            key: bool(state.signals.get(key))
            for key in (
                "task_complete_pos", "in_combat", "request_task_el", "xp_full",
                "equip_el", "combat_controls_visible",
            )
        },
        "seconds_since_progress": round(time.time() - state.last_task_time, 1),
        "ocr": [{"text": item.get("text", ""), "center": item.get("center")} for item in texts],
    }


def execute_action(action: str, state: WorldState) -> bool:
    """复核前置条件后执行固定动作，拒绝模型越界选择。

    Args:
        action: 模型选择的白名单动作。
        state: 已重新检测的当前状态。

    Returns:
        动作处理器已调用时返回 True；等待或信号变化时返回 False。
    """
    if action == "wait" or action not in allowed_actions(state):
        return False
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        return False
    previous_combat = state.signals.get("in_combat", False)
    try:
        if action == "combat":
            state.signals["in_combat"] = True
        handler(state)
    finally:
        state.signals["in_combat"] = previous_combat
    return True
