"""Engine wiring for the levelup behavior tree runtime."""

from __future__ import annotations

import asyncio
import logging

from airtest.core.api import snapshot

from behavior_setup import build_behavior_tree
from behavior_rule import BehaviorRule
from config import DECISION_INTERVAL, FAST_SCAN_INTERVAL, WORKFLOW_SCAN_INTERVAL
from detectors import scan_fast, scan_workflow
from game_actions import GameActions
from state import WorldState
from templates import build_templates
from vibe_ocr import OCRHelper


class LevelUpEngine:
    """Orchestrates sensors and behavior tree decisions.

    Args:
        logger: Logger used for runtime diagnostics.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        ocr = OCRHelper(snapshot_func=snapshot)
        actions = GameActions(ocr)
        templates = build_templates()

        self._state = WorldState(
            ocr=ocr,
            actions=actions,
            templates=templates,
        )
        self._state.signals.update(
            {
                "task_complete_pos": None,
                "in_combat": False,
                "xp_full": False,
                "request_task_el": None,
                "equip_el": None,
            }
        )

        self._tree = build_behavior_tree(logger)
        self._running = True
        self._action_lock = asyncio.Lock()

    async def run(self) -> None:
        """Run the engine loops."""
        await asyncio.gather(
            self._fast_sensor_loop(),
            self._workflow_sensor_loop(),
            self._decision_loop(),
        )

    async def _fast_sensor_loop(self) -> None:
        """Run the fast sensor loop."""
        self._logger.info("Fast sensor loop started")
        while self._running:
            try:
                await scan_fast(self._state)
            except Exception as exc:
                self._logger.error("Fast sensor error: %s", exc)
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(FAST_SCAN_INTERVAL)

    async def _workflow_sensor_loop(self) -> None:
        """Run the workflow sensor loop."""
        self._logger.info("Workflow sensor loop started")
        while self._running:
            try:
                await scan_workflow(self._state, WORKFLOW_SCAN_INTERVAL)
            except Exception as exc:
                self._logger.error("Workflow sensor error: %s", exc)
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(WORKFLOW_SCAN_INTERVAL)

    async def _decision_loop(self) -> None:
        """Run the decision loop."""
        self._logger.info("Decision loop started")
        while self._running:
            rule = self._tree.select(self._state)
            if rule is None:
                await asyncio.sleep(DECISION_INTERVAL)
                continue

            await self._execute_rule(rule)
            await asyncio.sleep(DECISION_INTERVAL)

    async def _execute_rule(self, rule: BehaviorRule) -> None:
        """Execute a behavior rule.

        Args:
            rule: Behavior rule to execute.
        """
        async with self._action_lock:
            self._logger.info("Execute rule: %s", rule.name)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, rule.action, self._state)
