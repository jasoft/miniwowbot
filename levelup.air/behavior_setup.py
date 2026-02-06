"""Behavior tree construction for levelup."""

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
    """Build the ordered behavior tree for levelup.

    Args:
        logger: Logger used by the behavior tree.

    Returns:
        BehaviorTree: Configured behavior tree instance.
    """

    def has_task_completion(state: WorldState) -> bool:
        return state.signals.get("task_complete_pos") is not None

    def should_timeout(state: WorldState) -> bool:
        if state.signals.get("in_combat"):
            return False
        return time.time() - state.last_task_time > TASK_TIMEOUT

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
        BehaviorRule("task_completion", has_task_completion, action_task_completion),
        BehaviorRule("task_timeout", should_timeout, action_timeout_recovery),
        BehaviorRule("request_task", has_request_task, action_request_task),
        BehaviorRule("next_dungeon", has_xp_full, action_dungeon_transition),
        BehaviorRule("equip_item", has_equip_item, action_equip_item),
        BehaviorRule("combat", is_in_combat, action_combat),
    ]

    return BehaviorTree(rules, logger)
