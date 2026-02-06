"""升级行为树的检测助手。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from airtest.core.api import exists

from state import WorldState

logger = logging.getLogger(__name__)


def _set_signal(signals: Dict[str, Any], key: str, value: Any) -> None:
    """更新信号值，并在变更时记录日志。

    Args:
        signals: 要更新的信号字典。
        key: 信号名称。
        value: 信号值。
    """
    previous = signals.get(key)
    signals[key] = value
    if previous != value:
        logger.debug("信号变化: %s %r -> %r", key, previous, value)


async def scan_fast(state: WorldState) -> None:
    """运行快速基于模板的检测。

    Args:
        state: 共享的世界状态。
    """
    start = time.time()
    loop = asyncio.get_running_loop()
    task_future = loop.run_in_executor(None, exists, state.templates["task_complete"])
    combat_future = loop.run_in_executor(None, exists, state.templates["in_dungeon"])
    task_pos, combat_pos = await asyncio.gather(task_future, combat_future)

    _set_signal(state.signals, "task_complete_pos", task_pos)
    _set_signal(state.signals, "in_combat", bool(combat_pos))

    if combat_pos:
        state.last_task_time = time.time()
    logger.debug(
        "scan_fast完成: task_complete=%s in_combat=%s cost=%.3fs",
        bool(task_pos),
        bool(combat_pos),
        time.time() - start,
    )


async def scan_workflow(state: WorldState, cooldown: float) -> None:
    """运行较慢的工作流检测（带冷却）。

    Args:
        state: 共享的世界状态。
        cooldown: 工作流扫描之间的最小秒数。
    """
    now = time.time()
    if now - state.last_workflow_scan < cooldown:
        logger.debug(
            "scan_workflow跳过: 冷却剩余%.2fs",
            cooldown - (now - state.last_workflow_scan),
        )
        return
    state.last_workflow_scan = now

    if state.signals.get("in_combat"):
        logger.debug("scan_workflow跳过: 战斗中")
        return

    loop = asyncio.get_running_loop()
    xp_future = loop.run_in_executor(None, exists, state.templates["xp_full"])
    request_future = loop.run_in_executor(
        None, state.actions.find, "领取任务", 0.5, 0.8, 1, False, [1]
    )
    equip_future = loop.run_in_executor(
        None, state.actions.find, "装备", 0.5, 0.8, 1, False, [1]
    )

    start = time.time()
    xp_full, request_el, equip_el = await asyncio.gather(
        xp_future, request_future, equip_future
    )

    _set_signal(state.signals, "xp_full", bool(xp_full))
    _set_signal(state.signals, "request_task_el", request_el)
    _set_signal(state.signals, "equip_el", equip_el)
    logger.debug(
        "scan_workflow完成: xp_full=%s request_task=%s equip=%s cost=%.3fs",
        bool(xp_full),
        bool(request_el),
        bool(equip_el),
        time.time() - start,
    )
