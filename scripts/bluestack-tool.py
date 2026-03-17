#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BlueStacks 单文件控制工具。

支持：
- list: 列出所有已知实例
- status: 查询一个或全部实例状态
- start: 启动指定实例
- stop: 停止指定实例

优化方案：
- 批量进程查询：一次性获取所有蓝叠相关进程及其命令行。
- 快速端口探测：利用 socket 快速检测 ADB 端口开放状态。
- 缩短轮询间隔：探测变快后，减小轮询间隔，实现秒级响应。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


EXIT_OK = 0
EXIT_STATE_MISMATCH = 1
EXIT_INVALID_ARGUMENT = 2
EXIT_ENVIRONMENT_ERROR = 3
EXIT_OPERATION_FAILED = 4
EXIT_UNKNOWN_INSTANCE = 5

DEFAULT_TIMEOUT = 60
POLL_INTERVAL_SECONDS = 0.5  # 缩短轮询间隔
BLUESTACKS_PROCESS_NAMES = ("HD-Player.exe", "Bluestacks.exe")


@dataclass(frozen=True)
class InstanceConfig:
    id: str
    label: str
    instance_name: str
    adb_serial: str
    emulator_type: str = "bluestacks"
    expected_port: int | None = None
    enabled: bool = True


@dataclass
class InstanceRuntimeStatus:
    id: str
    label: str
    instance_name: str
    adb_serial: str
    emulator_type: str
    player_running: bool
    adb_connected: bool
    device_state: str | None
    status: str
    pid_count: int
    last_error: str | None = None


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    command: list[str]


DEFAULT_INSTANCES = [
    InstanceConfig(
        id="1",
        label="主实例",
        instance_name="Pie64",
        adb_serial="emulator-5554",
        expected_port=5554,
    ),
    InstanceConfig(
        id="2",
        label="多开 1",
        instance_name="Pie64_1",
        adb_serial="emulator-5564",
        expected_port=5564,
    ),
    InstanceConfig(
        id="3",
        label="多开 2",
        instance_name="Pie64_2",
        adb_serial="emulator-5574",
        expected_port=5574,
    ),
    InstanceConfig(
        id="4",
        label="多开 3",
        instance_name="Pie64_3",
        adb_serial="emulator-5584",
        expected_port=5584,
    ),
]


class ProcessCache:
    """进程信息缓存，避免多次调用外部命令。"""

    _cache: list[dict[str, Any]] | None = None
    _last_update: float = 0

    @classmethod
    def get_all_processes(cls, force_refresh: bool = False) -> list[dict[str, Any]]:
        """获取所有蓝叠相关的进程信息。"""
        now = time.time()
        if cls._cache is not None and not force_refresh and (now - cls._last_update < 0.5):
            return cls._cache

        processes = []
        try:
            # 使用 wmic 一次性获取所有 HD-Player.exe 进程的 PID 和命令行
            # 这是 Windows 上获取命令行信息较快且无需第三方库的方法
            cmd = ["wmic", "process", "where", "name='HD-Player.exe' or name='Bluestacks.exe'", "get", "ProcessId,CommandLine,Name", "/format:list"]
            result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
            
            if result.returncode == 0:
                current_proc = {}
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        if current_proc:
                            processes.append(current_proc)
                            current_proc = {}
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        current_proc[key] = val
                if current_proc:
                    processes.append(current_proc)
        except Exception:
            # 回退到 tasklist，虽然没有命令行信息，但能知道进程是否存在
            try:
                cmd = ["tasklist", "/FO", "CSV", "/NH"]
                result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if not line.strip():
                            continue
                        parts = line.strip().split(",")
                        if len(parts) > 1:
                            name = parts[0].strip('"')
                            if name in BLUESTACKS_PROCESS_NAMES:
                                processes.append({"Name": name, "ProcessId": parts[1].strip('"'), "CommandLine": ""})
            except Exception:
                pass

        cls._cache = processes
        cls._last_update = now
        return processes

    @classmethod
    def find_instance_pids(cls, instance_name: str) -> list[int]:
        """根据实例名查找对应的进程 PID。"""
        all_procs = cls.get_all_processes()
        pids = []
        for proc in all_procs:
            cmdline = proc.get("CommandLine", "")
            if f"--instance {instance_name}" in cmdline or f"--instance={instance_name}" in cmdline:
                try:
                    pids.append(int(proc.get("ProcessId", 0)))
                except ValueError:
                    continue
        return pids

    @classmethod
    def get_any_running(cls) -> bool:
        """是否有任何蓝叠进程在运行。"""
        return len(cls.get_all_processes()) > 0


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def decode_process_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output

    for encoding in ("utf-8", "gbk", "cp936", sys.getdefaultencoding(), "latin1"):
        try:
            return output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return output.decode("utf-8", errors="replace")


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    """快速检测端口是否开放。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def run_list_cmd(
    command: list[str], timeout: int = 30, allow_failure: bool = False
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(
            ok=False,
            returncode=127,
            stdout="",
            stderr=f"命令不存在: {command[0]}",
            command=command,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            ok=False,
            returncode=124,
            stdout="",
            stderr=f"命令执行超时（{timeout}s）: {' '.join(command)}",
            command=command,
        )
    except Exception as exc:
        return CommandResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr=f"命令执行失败: {exc}",
            command=command,
        )

    stdout = decode_process_output(completed.stdout).strip()
    stderr = decode_process_output(completed.stderr).strip()
    ok = completed.returncode == 0 or allow_failure
    return CommandResult(
        ok=ok,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        command=command,
    )


def launch_instance_no_wait(command: list[str]) -> CommandResult:
    """启动实例进程，不等待进程退出。"""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        return CommandResult(
            ok=False,
            returncode=127,
            stdout="",
            stderr=f"命令不存在: {command[0]}",
            command=command,
        )
    except Exception as exc:
        return CommandResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr=f"命令启动失败: {exc}",
            command=command,
        )

    return CommandResult(
        ok=True,
        returncode=0,
        stdout=f"进程已启动 (PID: {process.pid})",
        stderr="",
        command=command,
    )


def build_default_instances() -> list[InstanceConfig]:
    return list(DEFAULT_INSTANCES)


def resolve_instance_by_id(instance_id: str) -> InstanceConfig | None:
    for instance in build_default_instances():
        if instance.id == str(instance_id):
            return instance
    return None


def override_instance_config(instance: InstanceConfig, args: argparse.Namespace) -> InstanceConfig:
    instance_name = args.instance if getattr(args, "instance", None) else instance.instance_name
    adb_serial = args.adb_serial if getattr(args, "adb_serial", None) else instance.adb_serial
    return InstanceConfig(
        id=instance.id,
        label=instance.label,
        instance_name=instance_name,
        adb_serial=adb_serial,
        emulator_type=instance.emulator_type,
        expected_port=instance.expected_port,
        enabled=instance.enabled,
    )


def resolve_adb_path(cli_path: str | None = None) -> str | None:
    candidates: list[str] = []
    if cli_path:
        candidates.append(cli_path)

    env_adb = os.environ.get("ADB_PATH")
    if env_adb:
        candidates.append(env_adb)

    which_adb = shutil.which("adb")
    if which_adb:
        candidates.append(which_adb)

    local_platform_tools = Path("platform-tools") / "adb.exe"
    if local_platform_tools.exists():
        candidates.append(str(local_platform_tools.resolve()))

    sdk_root = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if sdk_root:
        candidates.append(str(Path(sdk_root) / "platform-tools" / "adb.exe"))

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def resolve_bluestacks_player_path(cli_path: str | None = None) -> str | None:
    candidates: list[str] = []
    if cli_path:
        candidates.append(cli_path)

    env_player = os.environ.get("BLUESTACKS_PLAYER_PATH")
    if env_player:
        candidates.append(env_player)

    candidates.extend(
        [
            r"C:\Program Files\BlueStacks_nxt\HD-Player.exe",
            r"D:\Program Files\BlueStacks_nxt\HD-Player.exe",
            r"C:\Program Files\BlueStacks\HD-Player.exe",
            r"D:\Program Files\BlueStacks\HD-Player.exe",
        ]
    )

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def parse_adb_devices_output(stdout: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0].strip()
            state = parts[1].strip()
            devices[serial] = state
    return devices


def get_connected_adb_devices(adb_path: str | None) -> tuple[dict[str, str], str | None]:
    if not adb_path:
        return {}, "未找到 adb，可用 --adb 指定路径，或设置 ADB_PATH 环境变量"

    result = run_list_cmd([adb_path, "devices"], timeout=20)
    if not result.ok:
        error_message = result.stderr or result.stdout or "adb devices 执行失败"
        return {}, error_message
    return parse_adb_devices_output(result.stdout), None


def resolve_adb_serial_from_map(
    instance: InstanceConfig, adb_map: dict[str, str]
) -> tuple[str | None, str | None]:
    """从 ADB 设备映射中查找实例对应的设备状态。"""
    if instance.adb_serial in adb_map:
        return instance.adb_serial, adb_map[instance.adb_serial]

    if instance.expected_port:
        ip_port = f"127.0.0.1:{instance.expected_port + 1}"
        if ip_port in adb_map:
            return ip_port, adb_map[ip_port]

    return None, None


def collect_instance_status(
    instance: InstanceConfig, adb_map: dict[str, str], adb_error: str | None = None
) -> InstanceRuntimeStatus:
    # 优化：通过缓存查找该实例的 PID
    instance_pids = ProcessCache.find_instance_pids(instance.instance_name)
    player_running = len(instance_pids) > 0
    pid_count = len(instance_pids)

    # 优化：快速检测端口
    port_open = False
    if instance.expected_port:
        port_open = is_port_open(instance.expected_port + 1)

    matched_serial, device_state = resolve_adb_serial_from_map(instance, adb_map)
    
    # 关键修正：如果进程已经没了，无论端口通不通，都认为模拟器已经停止
    if not player_running:
        status = "stopped"
        adb_connected = False
        device_state = None
    else:
        adb_connected = device_state is not None or port_open
        if device_state == "device" or port_open:
            status = "running"
        elif device_state == "offline":
            status = "starting"
        elif device_state == "unauthorized":
            status = "error"
        elif adb_error:
            status = "error"
        else:
            status = "starting"

    last_error = None
    if adb_error and status == "error":
        last_error = adb_error

    return InstanceRuntimeStatus(
        id=instance.id,
        label=instance.label,
        instance_name=instance.instance_name,
        adb_serial=instance.adb_serial,
        emulator_type=instance.emulator_type,
        player_running=player_running,
        adb_connected=adb_connected,
        device_state=device_state,
        status=status,
        pid_count=pid_count,
        last_error=last_error,
    )


def wait_for_instance_status(
    instance: InstanceConfig,
    adb_path: str | None,
    timeout_sec: int,
    desired_statuses: set[str],
) -> tuple[InstanceRuntimeStatus, bool]:
    deadline = time.time() + max(timeout_sec, 0)
    
    while True:
        # 强制刷新进程缓存
        ProcessCache.get_all_processes(force_refresh=True)
        adb_map, adb_error = get_connected_adb_devices(adb_path)
        last_status = collect_instance_status(instance, adb_map, adb_error)
        
        if last_status.status in desired_statuses:
            return last_status, True
        if time.time() >= deadline:
            return last_status, False
        time.sleep(POLL_INTERVAL_SECONDS)


def instance_status_to_dict(status: InstanceRuntimeStatus) -> dict[str, Any]:
    return asdict(status)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("没有可显示的数据")
        return

    headers = [
        "id",
        "label",
        "instance_name",
        "adb_serial",
        "player_running",
        "adb_connected",
        "device_state",
        "status",
    ]
    widths: dict[str, int] = {}
    for header in headers:
        max_width = len(header)
        for row in rows:
            max_width = max(max_width, len(str(row.get(header, ""))))
        widths[header] = max_width

    header_line = "  ".join(header.ljust(widths[header]) for header in headers)
    separator = "  ".join("-" * widths[header] for header in headers)
    print(header_line)
    print(separator)
    for row in rows:
        print("  ".join(str(row.get(header, "")).ljust(widths[header]) for header in headers))


def emit_result(
    args: argparse.Namespace, payload: dict[str, Any], rows: list[dict[str, Any]] | None = None
) -> None:
    if args.format == "json":
        print_json(payload)
        return

    if rows is not None:
        print_table(rows)

    message = payload.get("message")
    if message:
        print(f"\n{message}")


def build_base_payload(command: str, ok: bool, message: str) -> dict[str, Any]:
    return {
        "ok": ok,
        "command": command,
        "timestamp": iso_now(),
        "message": message,
    }


def get_target_instance(args: argparse.Namespace) -> InstanceConfig | None:
    if not getattr(args, "id", None):
        return None
    instance = resolve_instance_by_id(str(args.id))
    if not instance:
        return None
    return override_instance_config(instance, args)


def cmd_list(args: argparse.Namespace) -> int:
    adb_path = resolve_adb_path(args.adb)
    adb_map, adb_error = get_connected_adb_devices(adb_path)
    # 预先获取一次进程信息
    ProcessCache.get_all_processes(force_refresh=True)
    
    statuses = [
        collect_instance_status(instance, adb_map, adb_error)
        for instance in build_default_instances()
    ]
    rows = [instance_status_to_dict(status) for status in statuses]

    payload = build_base_payload("list", True, "已列出所有实例")
    payload["instances"] = rows
    payload["adb_path"] = adb_path
    if adb_error:
        payload["warning"] = adb_error

    emit_result(args, payload, rows)
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    adb_path = resolve_adb_path(args.adb)
    adb_map, adb_error = get_connected_adb_devices(adb_path)
    # 预先获取一次进程信息
    ProcessCache.get_all_processes(force_refresh=True)

    if args.id:
        instance = get_target_instance(args)
        if not instance:
            payload = build_base_payload("status", False, f"未知实例 id: {args.id}")
            emit_result(args, payload)
            return EXIT_UNKNOWN_INSTANCE

        status = collect_instance_status(instance, adb_map, adb_error)
        row = instance_status_to_dict(status)
        payload = build_base_payload(
            "status", status.status == "running", f"实例 {instance.id} 当前状态: {status.status}"
        )
        payload["instance"] = row
        payload["adb_path"] = adb_path
        if adb_error:
            payload["warning"] = adb_error
        emit_result(args, payload, [row])
        return EXIT_OK if status.status == "running" else EXIT_STATE_MISMATCH

    statuses = [
        collect_instance_status(instance, adb_map, adb_error)
        for instance in build_default_instances()
    ]
    rows = [instance_status_to_dict(status) for status in statuses]
    summary = {
        "total": len(statuses),
        "running": sum(1 for s in statuses if s.status == "running"),
        "starting": sum(1 for s in statuses if s.status == "starting"),
        "stopped": sum(1 for s in statuses if s.status == "stopped"),
        "error": sum(1 for s in statuses if s.status == "error"),
        "unknown": sum(1 for s in statuses if s.status == "unknown"),
    }
    payload = build_base_payload("status", True, "已查询全部实例状态")
    payload["instances"] = rows
    payload["summary"] = summary
    payload["adb_path"] = adb_path
    if adb_error:
        payload["warning"] = adb_error
    emit_result(args, payload, rows)
    return EXIT_OK


def start_bluestacks_instance(
    instance: InstanceConfig, player_path: str, no_wait: bool = False
) -> CommandResult:
    """启动 BlueStacks 实例。"""
    command = [player_path, "--instance", instance.instance_name]
    del no_wait
    return launch_instance_no_wait(command)


def cmd_start(args: argparse.Namespace) -> int:
    """执行 start 子命令。"""
    instance = get_target_instance(args)
    if not instance:
        payload = build_base_payload("start", False, f"未知实例 id: {args.id}")
        emit_result(args, payload)
        return EXIT_UNKNOWN_INSTANCE

    player_path = resolve_bluestacks_player_path(args.player)
    if not player_path:
        payload = build_base_payload(
            "start", False, "未找到 BlueStacks 可执行文件，可用 --player 指定路径"
        )
        emit_result(args, payload)
        return EXIT_ENVIRONMENT_ERROR

    adb_path = resolve_adb_path(args.adb)
    # 刷新缓存
    ProcessCache.get_all_processes(force_refresh=True)
    adb_map, adb_error = get_connected_adb_devices(adb_path)
    before_status = collect_instance_status(instance, adb_map, adb_error)
    if before_status.status == "running":
        row = instance_status_to_dict(before_status)
        payload = build_base_payload("start", True, f"实例 {instance.id} 已在运行，无需重复启动")
        payload["instance"] = row
        payload["already_running"] = True
        payload["player_path"] = player_path
        payload["adb_path"] = adb_path
        emit_result(args, payload, [row])
        return EXIT_OK

    result = start_bluestacks_instance(instance, player_path, args.no_wait)
    if not result.ok:
        payload = build_base_payload("start", False, f"启动实例 {instance.id} 失败")
        payload["player_path"] = player_path
        payload["adb_path"] = adb_path
        payload["launch_command"] = result.command
        payload["stderr"] = result.stderr
        payload["stdout"] = result.stdout
        emit_result(args, payload)
        return EXIT_OPERATION_FAILED

    if args.no_wait:
        # 发送启动命令后快速检测一次
        ProcessCache.get_all_processes(force_refresh=True)
        after_adb_map, after_adb_error = get_connected_adb_devices(adb_path)
        after_status = collect_instance_status(instance, after_adb_map, after_adb_error)
        after_row = instance_status_to_dict(after_status)
        started_successfully = after_status.status == "running"

        payload = build_base_payload(
            "start",
            True,
            f"已发送启动命令到实例 {instance.id}"
            + ("" if started_successfully else "，请等待启动完成"),
        )
        payload["instance"] = after_row
        payload["waited"] = False
        payload["already_running"] = started_successfully
        emit_result(args, payload, [after_row])
        return EXIT_OK

    started_at = time.time()
    final_status, reached = wait_for_instance_status(instance, adb_path, args.timeout, {"running"})
    elapsed_seconds = round(time.time() - started_at, 1)
    row = instance_status_to_dict(final_status)
    payload = build_base_payload(
        "start",
        reached,
        f"实例 {instance.id} 启动{'成功' if reached else '超时，未进入 running 状态'}",
    )
    payload["instance"] = row
    payload["elapsed_seconds"] = elapsed_seconds
    payload["waited"] = True
    emit_result(args, payload, [row])
    return EXIT_OK if reached else EXIT_STATE_MISMATCH


def stop_instance_via_adb(
    instance: InstanceConfig, adb_path: str, matched_serial: str | None = None
) -> CommandResult:
    """使用 ADB 停止模拟器。"""
    serial = matched_serial if matched_serial else instance.adb_serial
    return run_list_cmd([adb_path, "-s", serial, "emu", "kill"], timeout=20, allow_failure=True)


def disconnect_instance(
    instance: InstanceConfig, adb_path: str, matched_serial: str | None = None
) -> CommandResult:
    """断开 ADB 连接。"""
    serial = matched_serial if matched_serial else instance.adb_serial
    return run_list_cmd([adb_path, "disconnect", serial], timeout=20, allow_failure=True)


def run_powershell_script(script_path: Path, script_args: list[str]) -> CommandResult:
    """执行 PowerShell 脚本并返回标准化结果。"""
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *script_args,
    ]
    return run_list_cmd(command, timeout=30)


def find_and_kill_bluestacks_instance(instance: InstanceConfig) -> CommandResult:
    """杀死指定实例的 BlueStacks 进程。"""
    # 1. 尝试按实例名通过缓存找到 PID
    pids = ProcessCache.find_instance_pids(instance.instance_name)
    
    # 2. 如果没找到，尝试按端口查找 PID (兜底)
    if not pids and instance.expected_port:
        port = instance.expected_port + 1
        # 借用 netstat 查找监听端口的 PID
        try:
            res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            pids.append(int(parts[-1]))
        except Exception:
            pass

    if not pids:
        return CommandResult(ok=False, returncode=1, stdout="", stderr="未找到匹配的进程", command=[])

    success_count = 0
    errors = []
    for pid in set(pids):
        res = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
        if res.returncode == 0:
            success_count += 1
        else:
            errors.append(res.stderr.strip())

    if success_count > 0:
        return CommandResult(
            ok=True, 
            returncode=0, 
            stdout=f"成功终止 {success_count} 个进程", 
            stderr=" | ".join(errors), 
            command=[]
        )
    
    return CommandResult(ok=False, returncode=1, stdout="", stderr="终止进程失败: " + " | ".join(errors), command=[])


def cmd_stop(args: argparse.Namespace) -> int:
    """执行 stop 子命令。"""
    instance = get_target_instance(args)
    if not instance:
        payload = build_base_payload("stop", False, f"未知实例 id: {args.id}")
        emit_result(args, payload)
        return EXIT_UNKNOWN_INSTANCE

    adb_path = resolve_adb_path(args.adb)
    if not adb_path:
        payload = build_base_payload("stop", False, "未找到 adb，可用 --adb 指定路径")
        emit_result(args, payload)
        return EXIT_ENVIRONMENT_ERROR

    # 预检查状态
    ProcessCache.get_all_processes(force_refresh=True)
    adb_map, adb_error = get_connected_adb_devices(adb_path)
    before_status = collect_instance_status(instance, adb_map, adb_error)
    if before_status.status == "stopped":
        row = instance_status_to_dict(before_status)
        payload = build_base_payload("stop", True, f"实例 {instance.id} 已停止，无需重复关闭")
        payload["instance"] = row
        emit_result(args, payload, [row])
        return EXIT_OK

    matched_serial, _ = resolve_adb_serial_from_map(instance, adb_map)
    stop_methods_used: list[str] = []

    # 1. 尝试通过 PowerShell 精准杀死进程
    kill_result = find_and_kill_bluestacks_instance(instance)
    if kill_result.ok:
        stop_methods_used.append("kill by pid/port")
    
    # 2. ADB 停止 (无论强杀是否成功都尝试一次)
    emu_kill_result = stop_instance_via_adb(instance, adb_path, matched_serial)
    if emu_kill_result.ok:
        stop_methods_used.append("adb emu kill")
    
    disconnect_instance(instance, adb_path, matched_serial)
    stop_methods_used.append("adb disconnect")

    # 3. 极速等待停止完成
    started_at = time.time()
    final_status, reached = wait_for_instance_status(instance, adb_path, args.timeout, {"stopped"})
    elapsed_seconds = round(time.time() - started_at, 1)
    
    row = instance_status_to_dict(final_status)
    payload = build_base_payload(
        "stop",
        reached,
        f"实例 {instance.id} {'已停止' if reached else '停止超时'}",
    )
    payload["instance"] = row
    payload["stop_method"] = " + ".join(stop_methods_used)
    payload["elapsed_seconds"] = elapsed_seconds
    
    emit_result(args, payload, [row])
    return EXIT_OK if reached else EXIT_STATE_MISMATCH


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format", choices=("table", "json"), default="table", help="输出格式（默认: table）"
    )
    parser.add_argument("--adb", help="adb 可执行文件路径")
    parser.add_argument("--player", help="BlueStacks HD-Player.exe 路径")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"等待超时秒数（默认: {DEFAULT_TIMEOUT}）",
    )


def build_parser() -> argparse.ArgumentParser:
    default_mapping = "\n".join(
        f"  {instance.id} -> {instance.instance_name} / {instance.adb_serial}"
        for instance in DEFAULT_INSTANCES
    )

    epilog = f"""
默认实例映射:
{default_mapping}

说明:
  - list/status 命令已优化进程和端口探测，响应速度大幅提升。
  - stop 命令结合了精准 PID 强杀和 ADB 指令，实现秒级关闭。
"""

    parser = argparse.ArgumentParser(
        description="BlueStacks 控制工具 (优化版)：支持快速状态检测与停止。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出所有已知实例及当前状态")
    add_common_arguments(list_parser)
    list_parser.set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser("status", help="查询一个或全部实例状态")
    add_common_arguments(status_parser)
    status_parser.add_argument("--id", help="实例 id")
    status_parser.add_argument("--instance", help="覆盖实例名")
    status_parser.add_argument("--adb-serial", help="覆盖 adb serial")
    status_parser.set_defaults(func=cmd_status)

    start_parser = subparsers.add_parser("start", help="启动指定实例")
    add_common_arguments(start_parser)
    start_parser.add_argument("--id", required=True, help="实例 id")
    start_parser.add_argument("--instance", help="覆盖实例名")
    start_parser.add_argument("--adb-serial", help="覆盖 adb serial")
    start_parser.add_argument("--no-wait", action="store_true", help="不等待启动完成")
    start_parser.set_defaults(func=cmd_start)

    stop_parser = subparsers.add_parser("stop", help="停止指定实例")
    add_common_arguments(stop_parser)
    stop_parser.add_argument("--id", required=True, help="实例 id")
    stop_parser.add_argument("--instance", help="覆盖实例名")
    stop_parser.add_argument("--adb-serial", help="覆盖 adb serial")
    stop_parser.set_defaults(func=cmd_stop)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "timeout", DEFAULT_TIMEOUT) < 0:
        return EXIT_INVALID_ARGUMENT

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
