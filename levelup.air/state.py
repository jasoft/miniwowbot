"""Shared runtime state for levelup automation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict

from airtest.core.api import Template

from game_actions import GameActions
from vibe_ocr import OCRHelper


@dataclass
class WorldState:
    """Container for shared state across sensors and actions.

    Args:
        ocr: OCR helper used for text detection.
        actions: Action helper used for UI interactions.
        templates: Template mapping used for template matching.
        signals: Latest detection signals and cached results.
        last_task_time: Timestamp for last task completion or progress.
        failed_in_dungeon: Whether dungeon progression has failed.
        last_workflow_scan: Timestamp of last workflow scan.
    """

    ocr: OCRHelper
    actions: GameActions
    templates: Dict[str, Template]
    signals: Dict[str, Any] = field(default_factory=dict)
    last_task_time: float = field(default_factory=time.time)
    failed_in_dungeon: bool = False
    last_workflow_scan: float = 0.0
