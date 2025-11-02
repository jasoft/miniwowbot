# -*- encoding=utf8 -*-
"""
多模拟器管理模块测试
"""

import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock
from emulator_manager import EmulatorManager


class TestEmulatorManager:
    """EmulatorManager 类的单元测试"""

    @pytest.fixture
    def manager(self):
        """创建 EmulatorManager 实例"""
        return EmulatorManager()

    def test_get_emulator_port(self, manager):
        """测试获取模拟器端口"""
        assert manager.get_emulator_port("emulator-5554") == 5555
        assert manager.get_emulator_port("emulator-5555") == 5556
        assert manager.get_emulator_port("emulator-5556") == 5557
        assert manager.get_emulator_port("unknown") is None

    def test_get_emulator_connection_string(self, manager):
        """测试获取 Airtest 连接字符串"""
        conn_str = manager.get_emulator_connection_string("emulator-5554")
        assert conn_str == "Android://127.0.0.1:5555/emulator-5554"

        conn_str = manager.get_emulator_connection_string("emulator-5555")
        assert conn_str == "Android://127.0.0.1:5556/emulator-5555"

    @patch("subprocess.run")
    def test_get_adb_devices(self, mock_run, manager):
        """测试获取 ADB 设备列表"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\nemulator-5555\tdevice\n",
        )

        devices = manager.get_adb_devices()
        assert "emulator-5554" in devices
        assert devices["emulator-5554"] == "device"
        assert "emulator-5555" in devices
        assert devices["emulator-5555"] == "device"

    @patch("subprocess.run")
    def test_get_adb_devices_empty(self, mock_run, manager):
        """测试获取空的 ADB 设备列表"""
        mock_run.return_value = Mock(returncode=0, stdout="List of devices attached\n")

        devices = manager.get_adb_devices()
        assert len(devices) == 0

    @patch("subprocess.run")
    def test_get_adb_devices_error(self, mock_run, manager):
        """测试 ADB 命令执行失败"""
        mock_run.side_effect = Exception("ADB error")

        devices = manager.get_adb_devices()
        assert len(devices) == 0

    @patch.object(EmulatorManager, "get_adb_devices")
    def test_is_emulator_running(self, mock_get_devices, manager):
        """测试检查模拟器是否运行"""
        mock_get_devices.return_value = {
            "emulator-5554": "device",
            "emulator-5555": "offline",
        }

        assert manager.is_emulator_running("emulator-5554") is True
        assert manager.is_emulator_running("emulator-5555") is False
        assert manager.is_emulator_running("emulator-5556") is False

    @patch.object(EmulatorManager, "get_adb_devices")
    def test_is_emulator_running_with_retry(self, mock_get_devices, manager):
        """测试检查模拟器是否运行（带重试机制）"""
        # 第一次返回空，第二次返回设备列表（模拟 ADB 延迟）
        mock_get_devices.side_effect = [
            {},  # 第一次尝试：设备列表为空
            {"emulator-5554": "device"},  # 第二次尝试：设备已连接
        ]

        result = manager.is_emulator_running("emulator-5554", retry_count=2)
        assert result is True
        # 应该调用两次 get_adb_devices
        assert mock_get_devices.call_count == 2

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_emulator_already_running(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试启动已运行的模拟器"""
        mock_is_running.return_value = True

        result = manager.start_emulator("emulator-5554")
        assert result is True
        mock_popen.assert_not_called()

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_emulator_success(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试成功启动模拟器"""
        # 第一次返回 False（未运行），后续返回 True（已启动）
        mock_is_running.side_effect = [False, True]

        result = manager.start_emulator("emulator-5554")
        assert result is True
        mock_popen.assert_called_once()

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_emulator_timeout(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试模拟器启动超时"""
        mock_is_running.return_value = False

        result = manager.start_emulator("emulator-5554")
        assert result is False

    @patch.object(EmulatorManager, "start_emulator")
    def test_start_multiple_emulators(self, mock_start, manager):
        """测试启动多个模拟器"""
        mock_start.return_value = True

        emulators = ["emulator-5554", "emulator-5555", "emulator-5556"]
        result = manager.start_multiple_emulators(emulators)

        assert result is True
        assert mock_start.call_count == 3

    @patch.object(EmulatorManager, "start_emulator")
    def test_start_multiple_emulators_partial_failure(self, mock_start, manager):
        """测试启动多个模拟器时部分失败"""
        mock_start.side_effect = [True, False, True]

        emulators = ["emulator-5554", "emulator-5555", "emulator-5556"]
        result = manager.start_multiple_emulators(emulators)

        assert result is False
        assert mock_start.call_count == 3


class TestEmulatorManagerIntegration:
    """EmulatorManager 集成测试"""

    @pytest.mark.skipif(True, reason="需要真实的 BlueStacks 环境，跳过集成测试")
    def test_real_adb_devices(self):
        """测试真实 ADB 设备列表"""
        manager = EmulatorManager()
        devices = manager.get_adb_devices()
        # 这个测试需要真实的 ADB 环境
        assert isinstance(devices, dict)

    @pytest.mark.skipif(True, reason="需要真实的 BlueStacks 环境，跳过集成测试")
    def test_real_emulator_status(self):
        """测试真实模拟器状态"""
        manager = EmulatorManager()
        # 这个测试需要真实的 ADB 环境
        result = manager.is_emulator_running("emulator-5554")
        assert isinstance(result, bool)
