# -*- encoding=utf8 -*-
"""
Airtest 设备 URI 解析工具

用于在 pytest 集成测试中通过命令行参数/环境变量选择要连接的设备/模拟器。
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

DEFAULT_AIRTEST_DEVICE_URI = "Android:///"

# 环境变量支持（可按需扩展）
DEVICE_URI_ENV_VARS = ("MINIWOW_DEVICE_URI", "AIRTEST_DEVICE_URI")
EMULATOR_ENV_VARS = ("MINIWOW_EMULATOR", "AIRTEST_EMULATOR")


def _strip_or_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_airtest_device_uri_from_emulator(emulator: str) -> str:
    """
    将模拟器标识转换为 Airtest 设备 URI。

    - 传入 `127.0.0.1:5555` / `emulator-5554` -> `Android:///<value>`
    - 若已是完整 URI（包含 `://`），则原样返回
    """
    emulator = emulator.strip()
    if not emulator:
        return DEFAULT_AIRTEST_DEVICE_URI
    if "://" in emulator:
        return emulator
    return f"Android:///{emulator}"


def resolve_airtest_device_uri(
    *,
    device_uri_opt: Optional[str] = None,
    emulator_opt: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    default: str = DEFAULT_AIRTEST_DEVICE_URI,
) -> str:
    """
    解析 Airtest 连接 URI。

    优先级：
    1) --device-uri / device_uri_opt（完整 URI）
    2) --emulator / emulator_opt（adb 序列或 host:port，会转成 Android:///<...>；也支持直接传完整 URI）
    3) 环境变量 MINIWOW_DEVICE_URI / AIRTEST_DEVICE_URI
    4) 环境变量 MINIWOW_EMULATOR / AIRTEST_EMULATOR
    5) default（默认 Android:///）
    """
    if env is None:
        env = os.environ

    device_uri = _strip_or_none(device_uri_opt)
    if device_uri:
        return device_uri

    emulator = _strip_or_none(emulator_opt)
    if emulator:
        return build_airtest_device_uri_from_emulator(emulator)

    for key in DEVICE_URI_ENV_VARS:
        value = _strip_or_none(env.get(key))
        if value:
            return value

    for key in EMULATOR_ENV_VARS:
        value = _strip_or_none(env.get(key))
        if value:
            return build_airtest_device_uri_from_emulator(value)

    return default

