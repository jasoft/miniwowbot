#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试网络连接方式的模拟器管理
"""

import logging
from emulator_manager import EmulatorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_network_connection():
    """测试网络连接方式"""
    logger.info("=" * 60)
    logger.info("🧪 测试网络连接方式的模拟器管理")
    logger.info("=" * 60)
    
    manager = EmulatorManager()
    
    # 1. 测试映射表
    logger.info("\n1️⃣ 测试模拟器到实例的映射")
    logger.info("-" * 60)
    for emulator_addr, instance_name in manager.EMULATOR_TO_INSTANCE.items():
        logger.info(f"   {emulator_addr} → {instance_name}")
    
    # 2. 测试连接字符串生成
    logger.info("\n2️⃣ 测试连接字符串生成")
    logger.info("-" * 60)
    test_addresses = [
        "127.0.0.1:5555",
        "127.0.0.1:5565",
        "127.0.0.1:5575",
        "127.0.0.1:5585",
    ]
    
    for addr in test_addresses:
        conn_str = manager.get_emulator_connection_string(addr)
        logger.info(f"   {addr} → {conn_str}")
    
    # 3. 测试获取 ADB 设备列表
    logger.info("\n3️⃣ 测试获取 ADB 设备列表")
    logger.info("-" * 60)
    devices = manager.get_adb_devices()
    if devices:
        logger.info(f"   发现 {len(devices)} 个设备:")
        for device_name, status in devices.items():
            logger.info(f"      {device_name}: {status}")
    else:
        logger.warning("   未发现任何设备（这可能是正常的，如果模拟器未启动）")
    
    # 4. 测试模拟器运行状态检查
    logger.info("\n4️⃣ 测试模拟器运行状态检查")
    logger.info("-" * 60)
    for addr in test_addresses:
        is_running = manager.is_emulator_running(addr)
        status = "✅ 运行中" if is_running else "❌ 未运行"
        logger.info(f"   {addr}: {status}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ 测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_network_connection()

