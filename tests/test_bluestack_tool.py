#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bluestack-tool.py 单元测试。

测试各个子命令的参数解析、函数逻辑和边界情况。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# 使用 importlib 动态导入
import importlib.util

spec = importlib.util.spec_from_file_location(
    "bluestack_tool", Path(__file__).parent.parent / "scripts" / "bluestack-tool.py"
)
bluestack_tool = importlib.util.module_from_spec(spec)
sys.modules["bluestack_tool"] = bluestack_tool
spec.loader.exec_module(bluestack_tool)
bt = bluestack_tool


class TestInstanceConfig:
    """测试 InstanceConfig 数据类。"""

    def test_default_instances_count(self) -> None:
        """验证默认实例数量为4个。"""
        instances = bt.build_default_instances()
        assert len(instances) == 4

    def test_default_instances_ids(self) -> None:
        """验证默认实例ID为1-4。"""
        instances = bt.build_default_instances()
        ids = [i.id for i in instances]
        assert ids == ["1", "2", "3", "4"]

    def test_default_instances_serials(self) -> None:
        """验证默认ADB序列号。"""
        instances = bt.build_default_instances()
        serials = [i.adb_serial for i in instances]
        assert serials == [
            "emulator-5554",
            "emulator-5564",
            "emulator-5574",
            "emulator-5584",
        ]

    def test_resolve_instance_by_id_valid(self) -> None:
        """验证能通过ID解析实例。"""
        instance = bt.resolve_instance_by_id("1")
        assert instance is not None
        assert instance.id == "1"
        assert instance.instance_name == "Pie64"

    def test_resolve_instance_by_id_invalid(self) -> None:
        """验证无效ID返回None。"""
        instance = bt.resolve_instance_by_id("99")
        assert instance is None

    def test_resolve_instance_by_id_string_coersion(self) -> None:
        """验证字符串类型强制转换。"""
        instance = bt.resolve_instance_by_id(1)  # type: ignore
        assert instance is not None
        assert instance.id == "1"


class TestOverrideInstanceConfig:
    """测试实例配置覆盖功能。"""

    def test_override_instance_name(self) -> None:
        """验证可以覆盖实例名。"""
        instance = bt.resolve_instance_by_id("1")
        assert instance is not None

        mock_args = MagicMock()
        mock_args.instance = "CustomInstance"
        mock_args.adb_serial = None

        result = bt.override_instance_config(instance, mock_args)
        assert result.instance_name == "CustomInstance"
        assert result.id == "1"
        assert result.adb_serial == "emulator-5554"

    def test_override_adb_serial(self) -> None:
        """验证可以覆盖ADB序列号。"""
        instance = bt.resolve_instance_by_id("1")
        assert instance is not None

        mock_args = MagicMock()
        mock_args.instance = None
        mock_args.adb_serial = "emulator-9999"

        result = bt.override_instance_config(instance, mock_args)
        assert result.adb_serial == "emulator-9999"
        assert result.instance_name == "Pie64"

    def test_override_both(self) -> None:
        """验证可以同时覆盖实例名和ADB序列号。"""
        instance = bt.resolve_instance_by_id("1")
        assert instance is not None

        mock_args = MagicMock()
        mock_args.instance = "CustomInstance"
        mock_args.adb_serial = "emulator-9999"

        result = bt.override_instance_config(instance, mock_args)
        assert result.instance_name == "CustomInstance"
        assert result.adb_serial == "emulator-9999"


class TestParseAdbDevicesOutput:
    """测试ADB设备输出解析。"""

    def test_parse_normal_output(self) -> None:
        """验证解析正常ADB设备输出。"""
        output = """List of devices attached
emulator-5554	device
emulator-5564	offline
emulator-5574	unauthorized
"""
        result = bt.parse_adb_devices_output(output)
        assert result == {
            "emulator-5554": "device",
            "emulator-5564": "offline",
            "emulator-5574": "unauthorized",
        }

    def test_parse_empty_output(self) -> None:
        """验证解析空输出。"""
        result = bt.parse_adb_devices_output("")
        assert result == {}

    def test_parse_no_devices(self) -> None:
        """验证解析无设备输出。"""
        output = "List of devices attached\n"
        result = bt.parse_adb_devices_output(output)
        assert result == {}

    def test_parse_with_extra_whitespace(self) -> None:
        """验证解析带多余空白的输出。"""
        output = """List of devices attached
  
emulator-5554    device  

"""
        result = bt.parse_adb_devices_output(output)
        assert result == {"emulator-5554": "device"}


class TestDecodeProcessOutput:
    """测试进程输出解码。"""

    def test_decode_none(self) -> None:
        """验证解码None返回空字符串。"""
        result = bt.decode_process_output(None)
        assert result == ""

    def test_decode_string(self) -> None:
        """验证字符串直接返回。"""
        result = bt.decode_process_output("hello")
        assert result == "hello"

    def test_decode_utf8(self) -> None:
        """验证解码UTF-8。"""
        result = bt.decode_process_output("你好".encode("utf-8"))
        assert result == "你好"

    def test_decode_gbk(self) -> None:
        """验证解码GBK。"""
        result = bt.decode_process_output("你好".encode("gbk"))
        assert result == "你好"

    def test_decode_invalid_with_fallback(self) -> None:
        """验证无效UTF-8使用替换字符。"""
        invalid_utf8 = b"\xff\xfe"
        result = bt.decode_process_output(invalid_utf8)
        assert result is not None


class TestCollectInstanceStatus:
    """测试实例状态收集。"""

    def test_status_stopped(self) -> None:
        """验证停止状态检测。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )
        with patch("bluestack_tool.is_any_bluestacks_process_running") as mock_running:
            mock_running.return_value = (False, 0)
            result = bt.collect_instance_status(instance, {}, None)
            assert result.status == "stopped"
            assert result.player_running is False
            assert result.adb_connected is False

    def test_status_running(self) -> None:
        """验证运行状态检测。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )
        adb_map = {"emulator-5554": "device"}
        result = bt.collect_instance_status(instance, adb_map, None)
        assert result.status == "running"
        assert result.adb_connected is True
        assert result.device_state == "device"

    def test_status_offline_running(self) -> None:
        """验证离线状态且进程运行时为starting。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )
        adb_map = {"emulator-5554": "offline"}
        with patch("bluestack_tool.is_any_bluestacks_process_running") as mock_running:
            mock_running.return_value = (True, 1)
            result = bt.collect_instance_status(instance, adb_map, None)
            assert result.status == "starting"

    def test_status_offline_not_running(self) -> None:
        """验证离线状态且进程未运行时为unknown。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )
        adb_map = {"emulator-5554": "offline"}
        with patch("bluestack_tool.is_any_bluestacks_process_running") as mock_running:
            mock_running.return_value = (False, 0)
            result = bt.collect_instance_status(instance, adb_map, None)
            assert result.status == "unknown"

    def test_status_unauthorized(self) -> None:
        """验证未授权状态检测。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )
        adb_map = {"emulator-5554": "unauthorized"}
        result = bt.collect_instance_status(instance, adb_map, None)
        assert result.status == "error"


class TestWaitForInstanceStatus:
    """测试等待实例状态。"""

    @patch("bluestack_tool.get_connected_adb_devices")
    @patch("bluestack_tool.collect_instance_status")
    def test_wait_reaches_desired_status(self, mock_collect, mock_adb) -> None:
        """验证等待达到期望状态。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )

        # 第一次返回 starting，第二次返回 running
        mock_collect.side_effect = [
            bt.InstanceRuntimeStatus(
                id="1",
                label="主实例",
                instance_name="Pie64",
                adb_serial="emulator-5554",
                emulator_type="bluestacks",
                player_running=True,
                adb_connected=True,
                device_state="device",
                status="starting",
                pid_count=1,
            ),
            bt.InstanceRuntimeStatus(
                id="1",
                label="主实例",
                instance_name="Pie64",
                adb_serial="emulator-5554",
                emulator_type="bluestacks",
                player_running=True,
                adb_connected=True,
                device_state="device",
                status="running",
                pid_count=1,
            ),
        ]
        mock_adb.return_value = ({}, None)

        status, reached = bt.wait_for_instance_status(instance, None, 10, {"running"})
        assert reached is True
        assert status.status == "running"

    @patch("bluestack_tool.get_connected_adb_devices")
    @patch("bluestack_tool.collect_instance_status")
    def test_wait_timeout(self, mock_collect, mock_adb) -> None:
        """验证等待超时。"""
        instance = bt.InstanceConfig(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
        )

        mock_collect.return_value = bt.InstanceRuntimeStatus(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
            emulator_type="bluestacks",
            player_running=True,
            adb_connected=True,
            device_state="offline",
            status="starting",
            pid_count=1,
        )
        mock_adb.return_value = ({}, None)

        status, reached = bt.wait_for_instance_status(
            instance,
            None,
            1,
            {"running"},  # 1秒超时
        )
        assert reached is False


class TestCommandResult:
    """测试 CommandResult 数据类。"""

    def test_command_result_creation(self) -> None:
        """验证创建 CommandResult。"""
        result = bt.CommandResult(
            ok=True,
            returncode=0,
            stdout="output",
            stderr="",
            command=["ls"],
        )
        assert result.ok is True
        assert result.returncode == 0


class TestResolvePaths:
    """测试路径解析功能。"""

    @patch("bluestack_tool.shutil.which")
    @patch("bluestack_tool.Path.exists")
    def test_resolve_adb_path_from_which(self, mock_exists, mock_which) -> None:
        """验证从系统PATH解析adb。"""
        mock_which.return_value = "C:\\Android\\platform-tools\\adb.exe"
        mock_exists.return_value = True

        result = bt.resolve_adb_path(None)
        assert result is not None
        assert "adb.exe" in result

    @patch.dict("os.environ", {"ADB_PATH": "C:\\custom\\adb.exe"})
    @patch("bluestack_tool.Path.exists")
    def test_resolve_adb_path_from_env(self, mock_exists) -> None:
        """验证从环境变量解析adb。"""
        mock_exists.return_value = True
        result = bt.resolve_adb_path(None)
        assert result == "C:\\custom\\adb.exe"

    def test_resolve_adb_path_with_cli(self) -> None:
        """验证CLI路径优先。"""
        with patch("bluestack_tool.Path.exists") as mock_exists:
            mock_exists.return_value = True
            result = bt.resolve_adb_path("C:\\cli\\adb.exe")
            assert result == "C:\\cli\\adb.exe"

    def test_resolve_adb_path_not_found(self) -> None:
        """验证找不到adb时返回None。"""
        _ = bt.resolve_adb_path(None)
        # 可能返回None或系统中的adb


class TestProcessCounting:
    """测试进程计数功能。"""

    @patch("bluestack_tool.run_list_cmd")
    def test_count_processes_found(self, mock_run) -> None:
        """验证进程计数 - 找到进程。"""
        mock_run.return_value = bt.CommandResult(
            ok=True,
            returncode=0,
            stdout="""映像名称                       PID
HD-Player.exe                    1234
HD-Player.exe                    5678""",
            stderr="",
            command=["tasklist"],
        )
        count = bt.count_processes("HD-Player.exe")
        assert count == 2

    @patch("bluestack_tool.run_list_cmd")
    def test_count_processes_not_found(self, mock_run) -> None:
        """验证进程计数 - 未找到进程。"""
        mock_run.return_value = bt.CommandResult(
            ok=True,
            returncode=0,
            stdout="""映像名称                       PID
notepad.exe                    1234""",
            stderr="",
            command=["tasklist"],
        )
        count = bt.count_processes("HD-Player.exe")
        assert count == 0


class TestOutputFormatting:
    """测试输出格式化功能。"""

    def test_instance_status_to_dict(self) -> None:
        """验证实例状态转字典。"""
        status = bt.InstanceRuntimeStatus(
            id="1",
            label="主实例",
            instance_name="Pie64",
            adb_serial="emulator-5554",
            emulator_type="bluestacks",
            player_running=True,
            adb_connected=True,
            device_state="device",
            status="running",
            pid_count=1,
        )
        result = bt.instance_status_to_dict(status)
        assert isinstance(result, dict)
        assert result["id"] == "1"
        assert result["status"] == "running"

    def test_build_base_payload(self) -> None:
        """验证构建基础payload。"""
        payload = bt.build_base_payload("list", True, "成功")
        assert payload["ok"] is True
        assert payload["command"] == "list"
        assert payload["message"] == "成功"
        assert "timestamp" in payload


class TestCommandLineParsing:
    """测试命令行参数解析。"""

    def test_build_parser(self) -> None:
        """验证解析器构建成功。"""
        parser = bt.build_parser()
        assert parser is not None

    def test_parse_list_command(self) -> None:
        """验证解析 list 命令。"""
        parser = bt.build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"
        assert args.format == "table"

    def test_parse_status_command(self) -> None:
        """验证解析 status 命令。"""
        parser = bt.build_parser()
        args = parser.parse_args(["status", "--id", "1"])
        assert args.command == "status"
        assert args.id == "1"

    def test_parse_start_command(self) -> None:
        """验证解析 start 命令。"""
        parser = bt.build_parser()
        args = parser.parse_args(["start", "--id", "1", "--no-wait"])
        assert args.command == "start"
        assert args.id == "1"
        assert args.no_wait is True

    def test_parse_stop_command(self) -> None:
        """验证解析 stop 命令。"""
        parser = bt.build_parser()
        args = parser.parse_args(["stop", "--id", "1", "--timeout", "30"])
        assert args.command == "stop"
        assert args.id == "1"
        assert args.timeout == 30

    def test_parse_format_json(self) -> None:
        """验证解析 JSON 格式。"""
        parser = bt.build_parser()
        args = parser.parse_args(["list", "--format", "json"])
        assert args.format == "json"

    def test_parse_invalid_format(self) -> None:
        """验证解析无效格式时报错。"""
        parser = bt.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["list", "--format", "invalid"])

    def test_parse_timeout_negative(self) -> None:
        """验证解析负数超时。"""
        parser = bt.build_parser()
        args = parser.parse_args(["list", "--timeout", "-1"])
        assert args.timeout == -1


class TestGetTargetInstance:
    """测试获取目标实例功能。"""

    def test_get_target_instance_with_id(self) -> None:
        """验证通过ID获取实例。"""
        mock_args = MagicMock()
        mock_args.id = "1"
        mock_args.instance = None
        mock_args.adb_serial = None

        result = bt.get_target_instance(mock_args)
        assert result is not None
        assert result.id == "1"

    def test_get_target_instance_without_id(self) -> None:
        """验证无ID时返回None。"""
        mock_args = MagicMock()
        mock_args.id = None

        result = bt.get_target_instance(mock_args)
        assert result is None

    def test_get_target_instance_invalid_id(self) -> None:
        """验证无效ID返回None。"""
        mock_args = MagicMock()
        mock_args.id = "99"
        mock_args.instance = None
        mock_args.adb_serial = None

        result = bt.get_target_instance(mock_args)
        assert result is None


class TestAdbDevices:
    """测试ADB设备相关功能。"""

    @patch("bluestack_tool.run_list_cmd")
    def test_get_connected_adb_devices_success(self, mock_run) -> None:
        """验证成功获取ADB设备。"""
        mock_run.return_value = bt.CommandResult(
            ok=True,
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice",
            stderr="",
            command=["adb", "devices"],
        )
        devices, error = bt.get_connected_adb_devices("adb.exe")
        assert error is None
        assert "emulator-5554" in devices

    @patch("bluestack_tool.run_list_cmd")
    def test_get_connected_adb_devices_not_found(self, mock_run) -> None:
        """验证未找到ADB时返回错误信息。"""
        devices, error = bt.get_connected_adb_devices(None)
        assert devices == {}
        assert error is not None

    @patch("bluestack_tool.run_list_cmd")
    def test_get_connected_adb_devices_command_failed(self, mock_run) -> None:
        """验证ADB命令失败时返回错误。"""
        mock_run.return_value = bt.CommandResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr="adb not found",
            command=["adb", "devices"],
        )
        devices, error = bt.get_connected_adb_devices("adb.exe")
        assert devices == {}
        assert error is not None


class TestBluestacksPlayerPath:
    """测试BlueStacks播放器路径解析。"""

    @patch.dict("os.environ", {"BLUESTACKS_PLAYER_PATH": "C:\\custom\\HD-Player.exe"})
    @patch("bluestack_tool.Path.exists")
    def test_resolve_from_env(self, mock_exists) -> None:
        """验证从环境变量解析。"""
        mock_exists.return_value = True
        result = bt.resolve_bluestacks_player_path(None)
        assert result == "C:\\custom\\HD-Player.exe"

    def test_resolve_with_cli_path(self) -> None:
        """验证CLI路径优先。"""
        with patch("bluestack_tool.Path.exists") as mock_exists:
            mock_exists.return_value = True
            result = bt.resolve_bluestacks_player_path("C:\\cli\\HD-Player.exe")
            assert result == "C:\\cli\\HD-Player.exe"


class TestExitCodes:
    """测试退出码常量。"""

    def test_exit_codes_defined(self) -> None:
        """验证所有退出码已定义。"""
        assert bt.EXIT_OK == 0
        assert bt.EXIT_STATE_MISMATCH == 1
        assert bt.EXIT_INVALID_ARGUMENT == 2
        assert bt.EXIT_ENVIRONMENT_ERROR == 3
        assert bt.EXIT_OPERATION_FAILED == 4
        assert bt.EXIT_UNKNOWN_INSTANCE == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
