# -*- encoding=utf8 -*-
"""升级行为树入口点。"""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import logging
import os
import sys

from airtest.core.api import auto_setup

# 添加当前目录和项目根目录到 sys.path 以便使用共享模块。
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import configure_airtest
from engine import LevelUpEngine


def setup_logging() -> logging.Logger:
    """配置并返回升级日志记录器。"""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("levelup")
    logger.setLevel(logging.DEBUG)
    logging.getLogger("airtest").setLevel(logging.CRITICAL)
    return logger


async def main() -> None:
    """运行升级行为树引擎。"""
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