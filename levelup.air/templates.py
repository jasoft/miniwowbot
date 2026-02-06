"""Template factory for levelup detection."""

from __future__ import annotations

from typing import Dict

from airtest.core.api import Template


def build_templates() -> Dict[str, Template]:
    """Build template mappings used by detectors.

    Returns:
        Dict[str, Template]: Mapping of template names to Template instances.
    """
    return {
        "task_complete": Template(
            r"task_complete.png", resolution=(720, 1280), rgb=True, threshold=0.8
        ),
        "in_dungeon": Template(r"in_dungeon.png", resolution=(720, 1280), threshold=0.9),
        "xp_full": Template(
            r"next_dungeon_xp_full.png", resolution=(720, 1280), threshold=0.9
        ),
        "arrow": Template(r"arrow.png", resolution=(720, 1280), rgb=True, threshold=0.4),
    }
