"""升级行为树选择器。"""

from __future__ import annotations

import logging
import time
from typing import Dict, Iterable, Optional

from behavior_rule import BehaviorRule
from state import WorldState


class BehaviorTree:
    """基于优先级的行为树选择器。

    Args:
        rules: 有序的行为规则可迭代对象。
        logger: 用于诊断的日志记录器实例。
    """

    def __init__(self, rules: Iterable[BehaviorRule], logger: logging.Logger) -> None:
        self._rules = list(rules)
        self._logger = logger
        self._last_rule_log: Dict[str, float] = {}

    def select(self, state: WorldState) -> Optional[BehaviorRule]:
        """选择第一个匹配的规则。

        Args:
            state: 共享的世界状态。

        Returns:
            选中的规则，如果没有规则匹配则返回 None。
        """
        first_match: Optional[BehaviorRule] = None
        for rule in self._rules:
            try:
                matched = rule.condition(state)
            except Exception:
                self._logger.exception("规则条件失败: %s", rule.name)
                continue

            if matched:
                if first_match is None:
                    first_match = rule
                    self._log_rule(rule.name, "规则命中", 1.0)
                else:
                    self._log_rule(rule.name, "规则命中但被高优先级抢占", 1.0)
            else:
                self._log_rule(rule.name, "规则未命中", 5.0)

        return first_match

    def _log_rule(self, name: str, message: str, interval: float) -> None:
        """节流记录规则命中情况。

        Args:
            name: 规则名称。
            message: 日志消息。
            interval: 同一规则两次日志之间的最小秒数。
        """
        now = time.time()
        last = self._last_rule_log.get(name, 0.0)
        if now - last >= interval:
            self._logger.debug("%s: %s", message, name)
            self._last_rule_log[name] = now
