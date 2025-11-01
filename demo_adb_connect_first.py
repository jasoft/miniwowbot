#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
演示脚本：展示优化后的模拟器启动流程
先尝试 adb connect，失败后再启动 BlueStacks
"""

import logging
from emulator_manager import EmulatorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_startup_flow():
    """演示优化后的启动流程"""
    logger.info("=" * 70)
    logger.info("🎬 演示：优化后的模拟器启动流程")
    logger.info("=" * 70)
    
    manager = EmulatorManager()
    
    logger.info("\n📋 启动流程说明：")
    logger.info("-" * 70)
    logger.info("1️⃣ 检查模拟器是否已运行")
    logger.info("2️⃣ 如果未运行，尝试 adb connect 连接")
    logger.info("3️⃣ 如果 adb connect 成功，直接返回（无需启动 BlueStacks）")
    logger.info("4️⃣ 如果 adb connect 失败，启动对应的 BlueStacks 实例")
    
    logger.info("\n🧪 场景 1：模拟器已在运行")
    logger.info("-" * 70)
    logger.info("检查 127.0.0.1:5555 是否运行...")
    is_running = manager.is_emulator_running("127.0.0.1:5555")
    if is_running:
        logger.info("✅ 模拟器已在运行，无需启动")
    else:
        logger.info("❌ 模拟器未运行")
    
    logger.info("\n🧪 场景 2：尝试 adb connect")
    logger.info("-" * 70)
    logger.info("尝试连接到 127.0.0.1:5555...")
    result = manager.try_adb_connect("127.0.0.1:5555")
    if result:
        logger.info("✅ adb connect 成功，模拟器已就绪")
    else:
        logger.info("❌ adb connect 失败，可能需要启动 BlueStacks")
    
    logger.info("\n🧪 场景 3：获取所有设备")
    logger.info("-" * 70)
    devices = manager.get_adb_devices()
    if devices:
        logger.info(f"发现 {len(devices)} 个设备:")
        for device_name, status in devices.items():
            logger.info(f"   • {device_name}: {status}")
    else:
        logger.info("未发现任何设备")
    
    logger.info("\n🧪 场景 4：获取连接字符串")
    logger.info("-" * 70)
    test_addresses = [
        "127.0.0.1:5555",
        "127.0.0.1:5565",
        "127.0.0.1:5575",
        "127.0.0.1:5585",
    ]
    
    for addr in test_addresses:
        conn_str = manager.get_emulator_connection_string(addr)
        logger.info(f"   {addr} → {conn_str}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ 演示完成")
    logger.info("=" * 70)
    
    logger.info("\n💡 优势总结：")
    logger.info("-" * 70)
    logger.info("1. 避免不必要的 BlueStacks 启动")
    logger.info("2. 更快的连接速度（如果模拟器已在运行）")
    logger.info("3. 更智能的启动逻辑")
    logger.info("4. 支持多个 BlueStacks 实例")
    logger.info("5. 跨平台兼容性（macOS、Windows、Linux）")


if __name__ == "__main__":
    demo_startup_flow()

