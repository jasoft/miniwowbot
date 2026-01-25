# -*- encoding=utf8 -*-
"""
模拟器连接自动恢复逻辑测试
"""

from unittest.mock import patch

import pytest

from emulator_manager import EmulatorConnectionError, EmulatorConnectionManager


class TestEnsureConnected:
    """测试 ensure_connected 行为"""

    def test_already_connected_short_circuit(self):
        manager = EmulatorConnectionManager()
        with patch.object(manager, "is_connected", return_value=True) as mock_is_connected, patch.object(
            manager, "connect"
        ) as mock_connect:
            assert manager.ensure_connected("127.0.0.1:5555") is True
            mock_is_connected.assert_called_once()
            mock_connect.assert_not_called()

    def test_connect_success_without_start_cmd(self):
        manager = EmulatorConnectionManager()
        with patch.object(manager, "is_connected", side_effect=[False, True]) as mock_is_connected, patch.object(
            manager, "connect", return_value=True
        ) as mock_connect, patch.object(manager, "_run_start_cmd") as mock_start_cmd:
            assert manager.ensure_connected("127.0.0.1:5555") is True
            assert mock_connect.called
            mock_start_cmd.assert_not_called()
            assert mock_is_connected.call_count >= 2

    def test_missing_start_cmd_raises(self):
        manager = EmulatorConnectionManager(start_cmd=None)
        with patch.object(manager, "is_connected", return_value=False), patch.object(
            manager, "connect", return_value=False
        ):
            with pytest.raises(EmulatorConnectionError):
                manager.ensure_connected("127.0.0.1:5555", max_retries=2)

    def test_start_cmd_failure_raises(self):
        manager = EmulatorConnectionManager(start_cmd="start.cmd")
        with patch.object(manager, "is_connected", return_value=False), patch.object(
            manager, "connect", return_value=False
        ), patch.object(manager, "_run_start_cmd", return_value=False):
            with pytest.raises(EmulatorConnectionError):
                manager.ensure_connected("127.0.0.1:5555", max_retries=2)

    @patch("time.sleep")
    def test_retries_exhausted_returns_false(self, mock_sleep):
        manager = EmulatorConnectionManager(start_cmd="start.cmd")
        with patch.object(manager, "is_connected", return_value=False), patch.object(
            manager, "connect", return_value=False
        ), patch.object(manager, "_run_start_cmd", return_value=True):
            assert manager.ensure_connected("127.0.0.1:5555", max_retries=2) is False
            mock_sleep.assert_called_once()
