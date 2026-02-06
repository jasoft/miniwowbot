"""升级行为树选择器。"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

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

    def select(self, state: WorldState) -> Optional[BehaviorRule]:
        """选择第一个匹配的规则。

        Args:
            state: 共享的世界状态。

        Returns:
            选中的规则，如果没有规则匹配则返回 None。
        """
        for rule in self._rules:
            try:
                if rule.condition(state):
                    return rule
            except Exception:
                self._logger.exception("规则条件失败: %s", rule.name)
        return None