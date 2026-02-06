"""升级检测的模板工厂。"""

from __future__ import annotations

from typing import Dict

from airtest.core.api import Template


def build_templates() -> Dict[str, Template]:
    """构建检测器使用的模板映射。

    Returns:
        Dict[str, Template]: 模板名称到 Template 实例的映射。
    """
    return {
        "task_complete": Template(
            r"images/task_complete.png", resolution=(720, 1280), rgb=True, threshold=0.8
        ),
        "in_dungeon": Template(r"images/in_dungeon.png", resolution=(720, 1280), threshold=0.9),
        "xp_full": Template(
            r"images/next_dungeon_xp_full.png", resolution=(720, 1280), threshold=0.9
        ),
        "arrow": Template(r"images/arrow.png", resolution=(720, 1280), rgb=True, threshold=0.4),
    }