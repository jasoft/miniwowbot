"""Behavior tree selector for levelup."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from behavior_rule import BehaviorRule
from state import WorldState


class BehaviorTree:
    """Priority-based behavior tree selector.

    Args:
        rules: Ordered iterable of behavior rules.
        logger: Logger instance for diagnostics.
    """

    def __init__(self, rules: Iterable[BehaviorRule], logger: logging.Logger) -> None:
        self._rules = list(rules)
        self._logger = logger

    def select(self, state: WorldState) -> Optional[BehaviorRule]:
        """Select the first matching rule.

        Args:
            state: Shared world state.

        Returns:
            The selected rule or None if no rule matches.
        """
        for rule in self._rules:
            try:
                if rule.condition(state):
                    return rule
            except Exception:
                self._logger.exception("Rule condition failed: %s", rule.name)
        return None
