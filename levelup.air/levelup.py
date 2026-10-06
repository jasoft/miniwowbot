# -*- encoding=utf8 -*-
"""升级行为树入口点。"""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import logging
import os
import sys

from airtest.core.api import auto_setup, device
from airtest.core.helper import G

# 添加当前目录和项目根目录到 sys.path 以便使用共享模块。
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import configure_airtest
from engine import LevelUpEngine

# 要升级的模拟器实例（adb 序列号）。多开时必须显式指定，否则 Airtest 会挑错设备。
# 取值与 emulators.json 保持一致：
#   192.168.1.150:5555 -> 主账号（战士）
#   192.168.1.150:5565 -> 金币法师号
DEFAULT_EMULATOR = "192.168.1.150:5565"


def setup_logging() -> logging.Logger:
    """配置并返回升级日志记录器。

    Returns:
        升级日志记录器。
    """
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
    # Airtest CLI 已根据 --device 连接设备，直接复用，避免重复连接到默认账号。
    if G.DEVICE_LIST:
        auto_setup(__file__)
    else:
        emulator = os.environ.get("MINIWOW_EMULATOR", DEFAULT_EMULATOR)
        auto_setup(__file__, devices=[f"Android://127.0.0.1:5037/{emulator}"])
    os.environ["ANDROID_SERIAL"] = device().uuid
    print(f"[levelup] 目标设备: {device().uuid}")
    configure_airtest()
    logger = setup_logging()
    engine = LevelUpEngine(logger)
    await engine.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
