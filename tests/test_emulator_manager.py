# -*- encoding=utf8 -*-
"""
EmulatorManager 模块测试
"""

import json
from unittest.mock import Mock, patch

import pytest

from emulator_manager import EmulatorManager


class TestEmulatorManager:
    """EmulatorManager 类的单元测试"""

    @pytest.fixture
    def manager(self, tmp_path):
        config_path = tmp_path / "system_config.json"
        config_path.write_text(
            json.dumps({"emulators": {"startCmd": "c:\\tools\\scripts\\start.bat"}}),
            encoding="utf-8",
        )
        return EmulatorManager(config_file=str(config_path))

    def test_load_start_cmd(self, manager):
        assert manager.start_cmd == "c:\\tools\\scripts\\start.bat"

    @patch("subprocess.run")
    def test_get_adb_devices(self, mock_run, manager):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\nemulator-5555\tdevice\n",
        )

        devices = manager.get_adb_devices()
        assert devices["emulator-5554"] == "device"
        assert devices["emulator-5555"] == "device"

    @patch("subprocess.run")
    def test_get_adb_devices_error(self, mock_run, manager):
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
        devices = manager.get_adb_devices()
        assert devices == {}

    @patch.object(EmulatorManager, "get_adb_devices")
    def test_is_emulator_running_with_retry(self, mock_get_devices, manager):
        mock_get_devices.side_effect = [
            {},
            {"emulator-5554": "device"},
        ]
        assert manager.is_emulator_running("emulator-5554", retry_count=2) is True
        assert mock_get_devices.call_count == 2

    @patch.object(EmulatorManager, "try_adb_connect")
    @patch.object(EmulatorManager, "_run_start_cmd")
    def test_start_bluestacks_instance_connect_first(
        self, mock_start_cmd, mock_connect, manager
    ):
        mock_connect.return_value = True
        result = manager.start_bluestacks_instance("127.0.0.1:5555")
        assert result is True
        mock_start_cmd.assert_not_called()

    @patch("time.sleep")
    @patch.object(EmulatorManager, "try_adb_connect")
    @patch.object(EmulatorManager, "_run_start_cmd")
    def test_start_bluestacks_instance_start_then_connect(
        self, mock_start_cmd, mock_connect, mock_sleep, manager
    ):
        mock_connect.side_effect = [False, True]
        mock_start_cmd.return_value = True

        result = manager.start_bluestacks_instance("127.0.0.1:5555")
        assert result is True
        mock_start_cmd.assert_called_once()
        mock_sleep.assert_called_once_with(30)
        assert mock_connect.call_count == 2

    @patch("time.sleep")
    @patch.object(EmulatorManager, "try_adb_connect")
    @patch.object(EmulatorManager, "_run_start_cmd")
    def test_start_bluestacks_instance_start_fail(
        self, mock_start_cmd, mock_connect, mock_sleep, manager
    ):
        mock_connect.return_value = False
        mock_start_cmd.return_value = False

        result = manager.start_bluestacks_instance("127.0.0.1:5555")
        assert result is False
        mock_sleep.assert_not_called()


class TestEmulatorManagerIntegration:
    """EmulatorManager 集成测试"""

    @pytest.mark.skipif(True, reason="需要真实的模拟器环境，跳过集成测试")
    def test_real_adb_devices(self):
        manager = EmulatorManager()
        devices = manager.get_adb_devices()
        assert isinstance(devices, dict)
