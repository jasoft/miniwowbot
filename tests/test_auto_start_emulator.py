# -*- encoding=utf8 -*-
"""
自动启动模拟器功能测试
测试当模拟器不在设备列表中时，是否能自动启动对应的 BlueStacks 实例
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from emulator_manager import EmulatorManager


class TestAutoStartEmulator:
    """自动启动模拟器功能的单元测试"""

    @pytest.fixture
    def manager(self):
        """创建 EmulatorManager 实例"""
        return EmulatorManager()

    def test_emulator_to_instance_mapping(self, manager):
        """测试模拟器名称到 BlueStacks 实例名称的映射"""
        assert manager.EMULATOR_TO_INSTANCE["emulator-5554"] == "Tiramisu64"
        assert manager.EMULATOR_TO_INSTANCE["emulator-5564"] == "Tiramisu64_1"
        assert manager.EMULATOR_TO_INSTANCE["emulator-5574"] == "Tiramisu64_2"
        assert manager.EMULATOR_TO_INSTANCE["emulator-5584"] == "Tiramisu64_3"

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_bluestacks_instance_success(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试成功启动 BlueStacks 实例"""
        # 第一次返回 False（未运行），后续返回 True（已启动）
        mock_is_running.side_effect = [False, True]

        result = manager.start_bluestacks_instance("emulator-5554")
        assert result is True
        mock_popen.assert_called_once()

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_bluestacks_instance_timeout(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试 BlueStacks 实例启动超时"""
        mock_is_running.return_value = False

        result = manager.start_bluestacks_instance("emulator-5554")
        assert result is False

    def test_start_bluestacks_instance_unknown_emulator(self, manager):
        """测试启动未知的模拟器"""
        result = manager.start_bluestacks_instance("emulator-9999")
        assert result is False

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_bluestacks_instance_second_emulator(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试启动第二个 BlueStacks 实例"""
        mock_is_running.side_effect = [False, True]

        result = manager.start_bluestacks_instance("emulator-5564")
        assert result is True
        mock_popen.assert_called_once()

    @patch.object(EmulatorManager, "is_emulator_running")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_bluestacks_instance_already_running(
        self, mock_sleep, mock_popen, mock_is_running, manager
    ):
        """测试启动已运行的 BlueStacks 实例"""
        mock_is_running.return_value = True

        result = manager.start_bluestacks_instance("emulator-5554")
        assert result is True
        # 应该立即返回，不需要启动
        mock_popen.assert_not_called()

