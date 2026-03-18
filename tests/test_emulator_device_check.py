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

    @patch("subprocess.run")
    def test_get_devices_decodes_bytes_output(self, mock_run, manager):
        """测试获取设备列表时可安全解码字节输出。"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b"List of devices attached\nemulator-5554\tdevice\n",
            stderr=b"",
        )

        devices = manager.get_devices()

        assert devices == {"emulator-5554": "device"}

    @patch("subprocess.run")
    def test_connect_handles_non_utf8_bytes_output(self, mock_run, manager):
        """测试连接模拟器时可处理包含异常字节的输出。"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b"already connected to 192.168.1.150:5565\xae",
            stderr=b"",
        )

        connected = manager.connect("192.168.1.150:5565")

        assert connected is True

    @patch("socket.create_connection")
    def test_normalize_emulator_prefers_localhost_when_local_port_is_open(
        self, mock_create_connection, manager
    ):
        """测试本地已监听端口时优先使用 127.0.0.1。"""
        manager.start_cmd = "start.cmd"
        mock_socket = Mock()
        mock_socket.__enter__ = Mock(return_value=mock_socket)
        mock_socket.__exit__ = Mock(return_value=False)
        mock_create_connection.return_value = mock_socket

        normalized = manager._normalize_emulator("192.168.1.150:5555")

        assert normalized == "127.0.0.1:5555"

    @patch("socket.create_connection", side_effect=OSError("port closed"))
    def test_normalize_emulator_keeps_remote_host_when_local_port_is_closed(
        self, _mock_create_connection, manager
    ):
        """测试本地端口不可用时保留原始地址。"""
        manager.start_cmd = "start.cmd"

        normalized = manager._normalize_emulator("192.168.1.150:5555")

        assert normalized == "192.168.1.150:5555"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

