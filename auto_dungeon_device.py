"""
设备管理模块

提供统一的设备连接和OCR初始化管理。
推荐直接使用 emulator_manager 模块。
"""

from emulator_manager import (
    EmulatorManager,
    EmulatorError,
    create_emulator_manager,
)

# 保持向后兼容的别名
DeviceManager = EmulatorManager
DeviceConnectionError = EmulatorError
create_device_manager = create_emulator_manager

__all__ = [
    "EmulatorManager",
    "EmulatorError",
    "create_emulator_manager",
    # 向后兼容别名
    "DeviceManager",
    "DeviceConnectionError",
    "create_device_manager",
]
