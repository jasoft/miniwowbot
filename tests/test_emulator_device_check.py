#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""模拟器设备检查功能测试。

覆盖 ``EmulatorConnectionManager.get_devices`` 的解析与各类失败分支。

adb 调用边界已收敛到 ``adb_runner.run_adb_command``，因此这里打桩该函数，
而不再直接打桩 ``subprocess.run`` —— 后者已不再被生产代码使用（管道死锁的
改造背景见 ``process_utils`` 模块 docstring 与 ``tests/test_adb_pipe_deadlock.py``）。
"""

import os
import sys

import pytest
from unittest.mock import patch

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import process_utils
from emulator_manager import EmulatorConnectionManager

#: adb devices 的输出表头，与真机保持一致。
_DEVICES_HEADER = "List of devices attached\n"


def _adb_devices_result(
    stdout: str = "",
    returncode: int = 0,
    stderr: str = "",
    timed_out: bool = False,
) -> process_utils.CommandResult:
    """构造一条假 adb 命令的执行结果。

    Args:
        stdout: 标准输出文本。
        returncode: 退出码。
        stderr: 标准错误文本。
        timed_out: 是否标记为超时。

    Returns:
        process_utils.CommandResult: 填充好的结果对象。
    """
    return process_utils.CommandResult(
        command=("adb", "devices"),
        returncode=returncode,
        stdout=stdout.encode("utf-8"),
        stderr=stderr.encode("utf-8"),
        timed_out=timed_out,
    )


class TestEmulatorDeviceCheck:
    """测试模拟器设备检查"""

    @pytest.fixture
    def manager(self):
        """创建 EmulatorConnectionManager 实例。

        Returns:
            EmulatorConnectionManager: 被测实例。
        """
        return EmulatorConnectionManager()

    @patch("adb_runner.run_adb_command")
    def test_get_adb_devices_success(self, mock_run, manager):
        """成功获取 ADB 设备列表。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(
            _DEVICES_HEADER + "emulator-5554\tdevice\nemulator-5555\tdevice\n"
        )

        devices = manager.get_devices()

        assert "emulator-5554" in devices
        assert devices["emulator-5554"] == "device"
        assert "emulator-5555" in devices
        assert devices["emulator-5555"] == "device"
        assert len(devices) == 2

    @patch("adb_runner.run_adb_command")
    def test_get_adb_devices_empty(self, mock_run, manager):
        """没有设备连接时返回空字典。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(_DEVICES_HEADER)

        devices = manager.get_devices()

        assert len(devices) == 0
        assert isinstance(devices, dict)

    @patch("adb_runner.run_adb_command")
    def test_get_adb_devices_error(self, mock_run, manager):
        """ADB 命令执行失败时返回空字典。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(returncode=1, stderr="error: device not found")

        devices = manager.get_devices()

        assert len(devices) == 0
        assert isinstance(devices, dict)

    @patch("adb_runner.run_adb_command")
    def test_get_adb_devices_timeout(self, mock_run, manager):
        """ADB 命令超时时应返回空字典而不是抛异常。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(timed_out=True)

        devices = manager.get_devices()

        assert devices == {}
        assert mock_run.call_count == 1, "超时不应触发重试，直接放弃本次读取"

    @patch("adb_runner.run_adb_command")
    def test_device_check_exists(self, mock_run, manager):
        """检查存在的设备。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(_DEVICES_HEADER + "emulator-5554\tdevice\n")

        devices = manager.get_devices()

        assert "emulator-5554" in devices

    @patch("adb_runner.run_adb_command")
    def test_device_check_not_exists(self, mock_run, manager):
        """检查不存在的设备。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(_DEVICES_HEADER + "emulator-5554\tdevice\n")

        devices = manager.get_devices()

        assert "emulator-9999" not in devices

    @patch("adb_runner.run_adb_command")
    def test_multiple_devices(self, mock_run, manager):
        """多个设备的情况。

        Args:
            mock_run: 被替换的 ``adb_runner.run_adb_command``。
            manager: 被测实例。

        Returns:
            None
        """
        mock_run.return_value = _adb_devices_result(
            _DEVICES_HEADER
            + "emulator-5554\tdevice\nemulator-5555\tdevice\nemulator-5556\tdevice\n"
        )

        devices = manager.get_devices()

        assert len(devices) == 3
        assert "emulator-5554" in devices
        assert "emulator-5555" in devices
        assert "emulator-5556" in devices


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
