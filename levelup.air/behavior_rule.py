"""Behavior rule definition for the levelup behavior tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from state import WorldState


@dataclass(frozen=True)
class BehaviorRule:
    """Single behavior rule with condition and action.

    Args:
        name: Rule name used for logging.
        condition: Callable that decides whether the rule should run.
        action: Callable executed when the condition is satisfied.
    """

    name: str
    condition: Callable[[WorldState], bool]
    action: Callable[[WorldState], None]
