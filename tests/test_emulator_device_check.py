#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试模拟器设备检查功能
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emulator_manager import EmulatorConnectionManager


class TestEmulatorDeviceCheck:
    """测试模拟器设备检查"""

    @pytest.fixture
    def manager(self):
        """创建 EmulatorConnectionManager 实例"""
        return EmulatorConnectionManager()

    @patch("subprocess.run")
    def test_get_adb_devices_success(self, mock_run, manager):
        """测试成功获取 ADB 设备列表"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\nemulator-5555\tdevice\n",
        )

        devices = manager.get_devices()
        
        assert "emulator-5554" in devices
        assert devices["emulator-5554"] == "device"
        assert "emulator-5555" in devices
        assert devices["emulator-5555"] == "device"
        assert len(devices) == 2

    @patch("subprocess.run")
    def test_get_adb_devices_empty(self, mock_run, manager):
        """测试没有设备连接的情况"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\n",
        )

        devices = manager.get_devices()
        
        assert len(devices) == 0
        assert isinstance(devices, dict)

    @patch("subprocess.run")
    def test_get_adb_devices_error(self, mock_run, manager):
        """测试 ADB 命令执行失败"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error: device not found",
        )

        devices = manager.get_devices()
        
        assert len(devices) == 0
        assert isinstance(devices, dict)

    @patch("subprocess.run")
    def test_device_check_exists(self, mock_run, manager):
        """测试检查存在的设备"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\n",
        )

        devices = manager.get_devices()
        assert "emulator-5554" in devices

    @patch("subprocess.run")
    def test_device_check_not_exists(self, mock_run, manager):
        """测试检查不存在的设备"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\n",
        )

        devices = manager.get_devices()
        assert "emulator-9999" not in devices

    @patch("subprocess.run")
    def test_multiple_devices(self, mock_run, manager):
        """测试多个设备的情况"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\nemulator-5555\tdevice\nemulator-5556\tdevice\n",
        )

        devices = manager.get_devices()
        
        assert len(devices) == 3
        assert "emulator-5554" in devices
        assert "emulator-5555" in devices
        assert "emulator-5556" in devices


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

