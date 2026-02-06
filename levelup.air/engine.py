"""升级行为树运行时的引擎接线。"""

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
    """编排传感器和行为树决策。

    Args:
        logger: 用于运行时诊断的日志记录器。
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
        """运行引擎循环。"""
        await asyncio.gather(
            self._fast_sensor_loop(),
            self._workflow_sensor_loop(),
            self._decision_loop(),
        )

    async def _fast_sensor_loop(self) -> None:
        """运行快速传感器循环。"""
        self._logger.info("快速传感器循环已启动")
        while self._running:
            try:
                await scan_fast(self._state)
            except Exception as exc:
                self._logger.error("快速传感器错误: %s", exc)
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(FAST_SCAN_INTERVAL)

    async def _workflow_sensor_loop(self) -> None:
        """运行工作流传感器循环。"""
        self._logger.info("工作流传感器循环已启动")
        while self._running:
            try:
                await scan_workflow(self._state, WORKFLOW_SCAN_INTERVAL)
            except Exception as exc:
                self._logger.error("工作流传感器错误: %s", exc)
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(WORKFLOW_SCAN_INTERVAL)

    async def _decision_loop(self) -> None:
        """运行决策循环。"""
        self._logger.info("决策循环已启动")
        while self._running:
            rule = self._tree.select(self._state)
            if rule is None:
                await asyncio.sleep(DECISION_INTERVAL)
                continue

            await self._execute_rule(rule)
            await asyncio.sleep(DECISION_INTERVAL)

    async def _execute_rule(self, rule: BehaviorRule) -> None:
        """执行行为规则。

        Args:
            rule: 要执行的行为规则。
        """
        async with self._action_lock:
            self._logger.info("执行规则: %s", rule.name)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, rule.action, self._state)