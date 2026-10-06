"""等待玩家处理指定副本，并在手工进入或跨日后恢复。"""

from __future__ import annotations

import logging
import time
from datetime import date

from dungeon_navigation import find_label
from state import WorldState
from task_workflow import read_task_screen

logger = logging.getLogger(__name__)


def refresh_manual_wait(state: WorldState) -> None:
    """只观察画面，不点击，避免干扰玩家手工处理。

    Args:
        state: 包含等待副本及日期的运行状态。
    """
    target = state.manual_dungeon
    if not target:
        return
    new_day = state.manual_wait_day != date.today().isoformat()
    entered = False
    if not new_day:
        entered = bool(find_label(read_task_screen(state), f"地下城-{target}", 150, 350))
    if new_day or entered:
        logger.info(
            "结束手工等待：%s，原因=%s", target, "次日重新检查" if new_day else "已手工进入"
        )
        state.manual_dungeon = None
        state.manual_wait_day = ""
        state.last_task_time = 0.0 if new_day else time.time()
        state.failed_in_dungeon = False
