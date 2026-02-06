"""升级行为树的行为规则定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from state import WorldState


@dataclass(frozen=True)
class BehaviorRule:
    """包含条件和动作的单个行为规则。

    Args:
        name: 用于日志记录的规则名称。
        condition: 决定规则是否应运行的可调用对象。
        action: 当条件满足时执行的可调用对象。
    """

    name: str
    condition: Callable[[WorldState], bool]
    action: Callable[[WorldState], None]