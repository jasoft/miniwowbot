"""升级自动化的共享运行时状态。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict

from airtest.core.api import Template

from game_actions import GameActions
from vibe_ocr import OCRHelper


@dataclass
class WorldState:
    """跨传感器和动作的共享状态容器。

    Args:
        ocr: 用于文本检测的 OCR 助手。
        actions: 用于 UI 交互的动作助手。
        templates: 用于模板匹配的模板映射。
        signals: 最新的检测信号和缓存结果。
        last_task_time: 上次任务完成或进展的时间戳。
        failed_in_dungeon: 副本进度是否失败。
        last_workflow_scan: 上次工作流扫描的时间戳。
        request_retry_after: 领取流程失败或任务已满后的下次重试时间。
        navigation_notice_after: 导航异常通知的下次允许发送时间。
    """

    ocr: OCRHelper
    actions: GameActions
    templates: Dict[str, Template]
    signals: Dict[str, Any] = field(default_factory=dict)
    last_task_time: float = field(default_factory=time.time)
    failed_in_dungeon: bool = False
    last_workflow_scan: float = 0.0
    request_retry_after: float = 0.0
    navigation_notice_after: float = 0.0
