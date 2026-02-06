# -*- encoding=utf8 -*-
"""Levelup behavior tree entrypoint."""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import logging
import os
import sys

from airtest.core.api import auto_setup

# Add current directory and project root to sys.path for shared modules.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import configure_airtest
from engine import LevelUpEngine


def setup_logging() -> logging.Logger:
    """Configure and return the levelup logger."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("levelup")
    logger.setLevel(logging.DEBUG)
    logging.getLogger("airtest").setLevel(logging.CRITICAL)
    return logger


async def main() -> None:
    """Run the levelup behavior tree engine."""
    auto_setup(__file__)
    configure_airtest()
    logger = setup_logging()
    engine = LevelUpEngine(logger)
    await engine.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
