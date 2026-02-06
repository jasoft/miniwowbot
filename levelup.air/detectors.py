"""Detection helpers for the levelup behavior tree."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

from airtest.core.api import exists

from state import WorldState


def _set_signal(signals: Dict[str, Any], key: str, value: Any) -> None:
    """Update a signal value.

    Args:
        signals: Signal dictionary to update.
        key: Signal name.
        value: Signal value.
    """
    signals[key] = value


async def scan_fast(state: WorldState) -> None:
    """Run fast template-based detections.

    Args:
        state: Shared world state.
    """
    loop = asyncio.get_running_loop()
    task_future = loop.run_in_executor(None, exists, state.templates["task_complete"])
    combat_future = loop.run_in_executor(None, exists, state.templates["in_dungeon"])
    task_pos, combat_pos = await asyncio.gather(task_future, combat_future)

    _set_signal(state.signals, "task_complete_pos", task_pos)
    _set_signal(state.signals, "in_combat", bool(combat_pos))

    if combat_pos:
        state.last_task_time = time.time()


async def scan_workflow(state: WorldState, cooldown: float) -> None:
    """Run slower workflow detections with cooldown.

    Args:
        state: Shared world state.
        cooldown: Minimum seconds between workflow scans.
    """
    now = time.time()
    if now - state.last_workflow_scan < cooldown:
        return
    state.last_workflow_scan = now

    if state.signals.get("in_combat"):
        return

    loop = asyncio.get_running_loop()
    xp_future = loop.run_in_executor(None, exists, state.templates["xp_full"])
    request_future = loop.run_in_executor(
        None, state.actions.find, "领取任务", 0.5, 0.8, 1, False, [1]
    )
    equip_future = loop.run_in_executor(
        None, state.actions.find, "装备", 0.5, 0.8, 1, False, [1]
    )

    xp_full, request_el, equip_el = await asyncio.gather(
        xp_future, request_future, equip_future
    )

    _set_signal(state.signals, "xp_full", bool(xp_full))
    _set_signal(state.signals, "request_task_el", request_el)
    _set_signal(state.signals, "equip_el", equip_el)
