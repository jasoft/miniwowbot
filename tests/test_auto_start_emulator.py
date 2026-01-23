# -*- encoding=utf8 -*-
"""
自动启动模拟器功能测试
"""

import json
from unittest.mock import patch

import pytest

from emulator_manager import EmulatorManager


class TestAutoStartEmulator:
    """自动启动模拟器功能的单元测试"""

    @pytest.fixture
    def manager(self, tmp_path):
        config_path = tmp_path / "system_config.json"
        config_path.write_text(
            json.dumps({"emulators": {"startCmd": "c:\\tools\\scripts\\start.bat"}}),
            encoding="utf-8",
        )
        return EmulatorManager(config_file=str(config_path))

    @patch("time.sleep")
    @patch.object(EmulatorManager, "try_adb_connect")
    @patch.object(EmulatorManager, "_run_start_cmd")
    def test_start_cmd_triggered_on_connect_fail(
        self, mock_start_cmd, mock_connect, mock_sleep, manager
    ):
        mock_connect.side_effect = [False, False]
        mock_start_cmd.return_value = True

        result = manager.start_bluestacks_instance("127.0.0.1:5555")
        assert result is False
        mock_start_cmd.assert_called_once()
        mock_sleep.assert_called_once_with(30)
        assert mock_connect.call_count == 2

    @patch.object(EmulatorManager, "try_adb_connect")
    @patch.object(EmulatorManager, "_run_start_cmd")
    def test_skip_start_when_already_connected(
        self, mock_start_cmd, mock_connect, manager
    ):
        mock_connect.return_value = True

        result = manager.start_bluestacks_instance("127.0.0.1:5555")
        assert result is True
        mock_start_cmd.assert_not_called()

    def test_missing_start_cmd_returns_false(self, tmp_path):
        config_path = tmp_path / "system_config.json"
        config_path.write_text(json.dumps({"emulators": {}}), encoding="utf-8")
        manager = EmulatorManager(config_file=str(config_path))

        with patch.object(manager, "try_adb_connect", return_value=False):
            assert manager.start_bluestacks_instance("127.0.0.1:5555") is False
