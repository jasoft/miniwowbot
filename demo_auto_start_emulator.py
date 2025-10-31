#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
自动启动 BlueStacks 实例演示脚本
演示当模拟器不在设备列表中时，如何自动启动对应的 BlueStacks 实例
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


def demo_auto_start():
    """演示自动启动 BlueStacks 实例功能"""
    logger.info("=" * 70)
    logger.info("🎮 自动启动 BlueStacks 实例演示")
    logger.info("=" * 70)

    # 初始化模拟器管理器
    manager = EmulatorManager()

    # 显示模拟器到实例的映射
    logger.info("\n📋 模拟器到 BlueStacks 实例的映射关系:")
    for emulator_name, instance_name in manager.EMULATOR_TO_INSTANCE.items():
        logger.info(f"   {emulator_name} → {instance_name}")

    # 获取当前设备列表
    logger.info("\n📱 当前已连接的设备:")
    devices = manager.get_adb_devices()
    if devices:
        for device_name, status in devices.items():
            logger.info(f"   {device_name}: {status}")
    else:
        logger.info("   (无设备连接)")

    # 演示自动启动逻辑
    logger.info("\n🚀 演示自动启动逻辑:")
    logger.info("   场景 1: 模拟器已在运行")
    logger.info("   场景 2: 模拟器不在设备列表中，需要启动")
    logger.info("   场景 3: 未知的模拟器")

    # 场景 1: 检查第一个模拟器
    test_emulator = "emulator-5554"
    logger.info(f"\n1️⃣ 检查 {test_emulator}:")
    if manager.is_emulator_running(test_emulator):
        logger.info(f"   ✅ {test_emulator} 已在运行")
    else:
        logger.info(f"   ⚠️ {test_emulator} 未在运行")
        logger.info(f"   💡 可以调用 start_bluestacks_instance() 自动启动")

    # 场景 2: 检查第二个模拟器
    test_emulator_2 = "emulator-5564"
    logger.info(f"\n2️⃣ 检查 {test_emulator_2}:")
    if manager.is_emulator_running(test_emulator_2):
        logger.info(f"   ✅ {test_emulator_2} 已在运行")
    else:
        logger.info(f"   ⚠️ {test_emulator_2} 未在运行")
        logger.info(f"   💡 可以调用 start_bluestacks_instance() 自动启动")

    # 场景 3: 未知的模拟器
    test_emulator_3 = "emulator-9999"
    logger.info(f"\n3️⃣ 检查 {test_emulator_3}:")
    if test_emulator_3 in manager.EMULATOR_TO_INSTANCE:
        logger.info(f"   ✅ {test_emulator_3} 在映射表中")
    else:
        logger.info(f"   ❌ {test_emulator_3} 不在映射表中")
        logger.info(f"   💡 需要先在 EMULATOR_TO_INSTANCE 中添加映射")

    # 显示工作流程
    logger.info("\n" + "=" * 70)
    logger.info("📊 自动启动工作流程:")
    logger.info("=" * 70)
    logger.info("""
1. 用户指定模拟器: --emulator emulator-5564
   ↓
2. 获取设备列表: adb devices
   ↓
3. 检查模拟器是否在列表中
   ├─ 存在 → 直接启动 ✅
   └─ 不存在 → 进入自动启动流程
      ↓
4. 查找模拟器对应的 BlueStacks 实例
   ├─ 找到 → 启动实例
   └─ 未找到 → 报错并发送 Bark 通知 ❌
      ↓
5. 启动 BlueStacks 实例
   ├─ macOS: open -a BlueStacksMIM
   ├─ Windows: HD-Player.exe --instance Tiramisu64_1
   └─ Linux: bluestacks
      ↓
6. 等待模拟器启动（最多 60 秒）
   ├─ 启动成功 → 继续执行脚本 ✅
   └─ 启动超时 → 报错并发送 Bark 通知 ❌
    """)

    logger.info("=" * 70)
    logger.info("✅ 演示完成")
    logger.info("=" * 70)


if __name__ == "__main__":
    demo_auto_start()

