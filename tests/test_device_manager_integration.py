#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
集成测试 - DeviceManager 功能测试
需要连接真实设备或模拟器才能运行
"""

import logging
import pytest
from unittest.mock import MagicMock, patch
from auto_dungeon_device import DeviceManager, DeviceConnectionError

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.integration
class TestDeviceManagerIntegration:
    """测试 DeviceManager 功能 - 集成测试"""

    def test_device_manager_initialization(self):
        """测试 DeviceManager 初始化"""
        try:
            # 使用默认参数初始化
            manager = DeviceManager()
            assert manager.emulator_manager is not None
            logger.info("✅ DeviceManager 初始化成功")
        except Exception as e:
            logger.error(f"❌ DeviceManager 初始化失败: {e}")
            pytest.fail(f"DeviceManager 初始化失败: {e}")

    def test_check_connection_no_target(self):
        """测试未设置目标时的连接检查"""
        manager = DeviceManager()
        assert manager.check_connection() is False
        logger.info("✅ 未设置目标时 check_connection 返回 False")

    @patch("auto_dungeon_device.subprocess.run")
    def test_check_connection_success(self, mock_run):
        """测试连接检查成功的情况 (Mock)"""
        manager = DeviceManager()
        manager.target_emulator = "127.0.0.1:5555"
        manager.emulator_manager.adb_path = "adb"

        # Mock subprocess.run 返回成功
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1\n"
        mock_run.return_value = mock_result

        assert manager.check_connection() is True
        logger.info("✅ check_connection 成功情况测试通过")

    @patch("auto_dungeon_device.subprocess.run")
    def test_check_connection_failure(self, mock_run):
        """测试连接检查失败的情况 (Mock)"""
        manager = DeviceManager()
        manager.target_emulator = "127.0.0.1:5555"
        manager.emulator_manager.adb_path = "adb"

        # Mock subprocess.run 返回失败
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        assert manager.check_connection() is False
        logger.info("✅ check_connection 失败情况测试通过")

    @patch("auto_dungeon_device.EmulatorManager")
    def test_ensure_emulator_running_already_connected(self, MockEmulatorManager):
        """测试确保模拟器运行 - 已连接情况"""
        manager = DeviceManager()
        manager.target_emulator = "127.0.0.1:5555"

        # Mock check_connection 返回 True
        with patch.object(manager, "check_connection", return_value=True):
            assert manager.ensure_emulator_running() is True
            logger.info("✅ ensure_emulator_running 已连接情况测试通过")

    @patch("auto_dungeon_device.EmulatorManager")
    def test_ensure_emulator_running_needs_start(self, MockEmulatorManager):
        """测试确保模拟器运行 - 需要启动情况"""
        manager = DeviceManager()
        manager.target_emulator = "127.0.0.1:5555"

        # Mock EmulatorManager
        mock_em = MockEmulatorManager.return_value
        manager.emulator_manager = mock_em

        # Mock check_connection 返回 False
        with patch.object(manager, "check_connection", return_value=False):
            # Mock is_emulator_running 返回 False
            mock_em.is_emulator_running.return_value = False
            # Mock start_bluestacks_instance 返回 True
            mock_em.start_bluestacks_instance.return_value = True

            assert manager.ensure_emulator_running() is True
            mock_em.start_bluestacks_instance.assert_called_with("127.0.0.1:5555")
            logger.info("✅ ensure_emulator_running 启动情况测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
