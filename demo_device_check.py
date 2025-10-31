#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
模拟器设备检查功能演示脚本
演示如何使用 EmulatorManager 检查设备列表
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emulator_manager import EmulatorManager
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def demo_device_check():
    """演示设备检查功能"""
    logger.info("=" * 60)
    logger.info("🎮 模拟器设备检查功能演示")
    logger.info("=" * 60)

    # 初始化模拟器管理器
    manager = EmulatorManager()

    # 获取所有已连接的设备
    logger.info("\n📱 获取所有已连接的设备...")
    devices = manager.get_adb_devices()

    if not devices:
        logger.warning("⚠️ 没有找到任何已连接的设备")
        logger.info("💡 请确保 BlueStacks 模拟器已启动")
        return

    logger.info(f"✅ 找到 {len(devices)} 个设备:")
    for device_name, status in devices.items():
        logger.info(f"   📱 {device_name}: {status}")

    # 演示检查特定设备
    logger.info("\n🔍 检查特定设备...")

    # 检查第一个设备
    first_device = list(devices.keys())[0]
    logger.info(f"\n1️⃣ 检查设备: {first_device}")
    if first_device in devices:
        logger.info(f"   ✅ 设备 {first_device} 存在")
        connection_string = manager.get_emulator_connection_string(first_device)
        logger.info(f"   📡 连接字符串: {connection_string}")
    else:
        logger.error(f"   ❌ 设备 {first_device} 不存在")

    # 检查不存在的设备
    logger.info(f"\n2️⃣ 检查不存在的设备: emulator-9999")
    if "emulator-9999" in devices:
        logger.info("   ✅ 设备 emulator-9999 存在")
    else:
        logger.warning("   ⚠️ 设备 emulator-9999 不存在")
        logger.info(f"   💡 可用设备: {list(devices.keys())}")

    # 演示检查模拟器是否运行
    logger.info(f"\n3️⃣ 检查模拟器是否运行...")
    for device_name in list(devices.keys())[:3]:  # 检查前 3 个设备
        is_running = manager.is_emulator_running(device_name)
        status = "✅ 运行中" if is_running else "⚠️ 未运行"
        logger.info(f"   {device_name}: {status}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ 演示完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    demo_device_check()

