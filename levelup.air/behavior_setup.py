"""构建升级行为树。"""

from __future__ import annotations

import time
from typing import Iterable

from actions import (
    action_combat,
    action_dungeon_transition,
    action_equip_item,
    action_request_task,
    action_task_completion,
    action_timeout_recovery,
)
from behavior_rule import BehaviorRule
from behavior_tree import BehaviorTree
from config import TASK_TIMEOUT
from state import WorldState


def build_behavior_tree(logger) -> BehaviorTree:
    """构建有序的升级行为树。

    Args:
        logger: 行为树使用的日志记录器。

    Returns:
        BehaviorTree: 配置好的行为树实例。
    """

    def has_task_completion(state: WorldState) -> bool:
        return state.signals.get("task_complete_pos") is not None

    def should_timeout(state: WorldState) -> bool:
        now = time.time()
        last_log = state.signals.get("timeout_debug_ts", 0.0)

        if state.signals.get("in_combat"):
            if now - last_log > 5:
                logger.debug("超时检查跳过: 战斗中")
                state.signals["timeout_debug_ts"] = now
            return False

        elapsed = now - state.last_task_time
        if now - last_log > 5:
            logger.debug(
                "超时检查: elapsed=%.2fs threshold=%s last_task_time=%.2f",
                elapsed,
                TASK_TIMEOUT,
                state.last_task_time,
            )
            state.signals["timeout_debug_ts"] = now
        return elapsed > TASK_TIMEOUT

    def has_request_task(state: WorldState) -> bool:
        if state.signals.get("in_combat"):
            return False
        return state.signals.get("request_task_el") is not None

    def has_xp_full(state: WorldState) -> bool:
        if state.signals.get("in_combat"):
            return False
        return bool(state.signals.get("xp_full"))

    def has_equip_item(state: WorldState) -> bool:
        if state.signals.get("in_combat"):
            return False
        return state.signals.get("equip_el") is not None

    def is_in_combat(state: WorldState) -> bool:
        return bool(state.signals.get("in_combat"))

    rules: Iterable[BehaviorRule] = [
        BehaviorRule("任务完成", has_task_completion, action_task_completion),
        BehaviorRule("任务超时", should_timeout, action_timeout_recovery),
        BehaviorRule("请求任务", has_request_task, action_request_task),
        BehaviorRule("下一副本", has_xp_full, action_dungeon_transition),
        BehaviorRule("装备物品", has_equip_item, action_equip_item),
        BehaviorRule("战斗", is_in_combat, action_combat),
    ]

    return BehaviorTree(rules, logger)
