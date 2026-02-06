# -*- encoding=utf8 -*-
"""Levelup behavior tree entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from airtest.core.api import auto_setup

# Add project root to sys.path for shared modules.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
