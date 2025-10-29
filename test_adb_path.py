#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 ADB 路径获取功能
验证是否能正确获取 Airtest 内置的 ADB 路径
"""

import os
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emulator_manager import EmulatorManager


def test_adb_path():
    """测试 ADB 路径获取"""
    logger.info("=" * 60)
    logger.info("🧪 测试 ADB 路径获取")
    logger.info("=" * 60)
    
    # 创建模拟器管理器实例
    manager = EmulatorManager()
    
    # 获取 ADB 路径
    adb_path = manager.adb_path
    logger.info(f"\n📍 获取到的 ADB 路径: {adb_path}")
    
    # 验证路径是否存在
    if adb_path and os.path.exists(adb_path):
        logger.info(f"✅ ADB 路径有效: {adb_path}")
        
        # 获取 ADB 版本
        import subprocess
        try:
            result = subprocess.run(
                [adb_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(f"\n📦 ADB 版本信息:")
            for line in result.stdout.strip().split('\n')[:2]:
                logger.info(f"   {line}")
        except Exception as e:
            logger.error(f"❌ 获取 ADB 版本失败: {e}")
    else:
        logger.warning(f"⚠️ ADB 路径无效或不存在: {adb_path}")
    
    # 测试获取设备列表
    logger.info(f"\n🔍 测试获取设备列表...")
    try:
        devices = manager.get_adb_devices()
        if devices:
            logger.info(f"✅ 发现 {len(devices)} 个设备:")
            for device_name, status in devices.items():
                logger.info(f"   - {device_name}: {status}")
        else:
            logger.warning("⚠️ 未发现任何设备（这可能是正常的，如果模拟器未启动）")
    except Exception as e:
        logger.error(f"❌ 获取设备列表失败: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ 测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_adb_path()

