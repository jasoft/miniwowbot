#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BlueStacks 单文件控制工具。

支持：
- list: 列出所有已知实例
- status: 查询一个或全部实例状态
- start: 启动指定实例
- stop: 停止指定实例

设计目标：
- 只依赖本文件，无需修改其他文件
- 支持 app/agent 通过稳定 id 控制实例
- 同时提供人类可读输出和 JSON 输出
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
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
POLL_INTERVAL_SECONDS = 2.0
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
    """启动实例进程，不等待进程退出。

    使用 Popen 启动进程后立即返回，适用于需要后台启动的场景。

    Args:
        command: 启动命令列表。

    Returns:
        CommandResult，启动命令是否成功发送（进程是否启动）。
    """
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


def count_processes(process_name: str) -> int:
    result = run_list_cmd(
        ["tasklist", "/FI", f"IMAGENAME eq {process_name}"], timeout=20, allow_failure=True
    )
    if not result.stdout:
        return 0

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    count = 0
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("映像名称") or lowered.startswith("image name"):
            continue
        if process_name.lower() in lowered:
            count += 1
    return count


def get_bluestacks_pid_count() -> int:
    return sum(count_processes(name) for name in BLUESTACKS_PROCESS_NAMES)


def is_any_bluestacks_process_running() -> tuple[bool, int]:
    pid_count = get_bluestacks_pid_count()
    return pid_count > 0, pid_count


def resolve_adb_serial_from_map(
    instance: InstanceConfig, adb_map: dict[str, str]
) -> tuple[str | None, str | None]:
    """从 ADB 设备映射中查找实例对应的设备状态。

    支持两种格式的 serial：
    - emulator-5554 (传统格式)
    - 127.0.0.1:5555 (IP:Port 格式)

    BlueStacks 端口映射规律：emulator-{port} -> 127.0.0.1:{port+1}
    例如：emulator-5554 -> 127.0.0.1:5555

    Args:
        instance: 实例配置。
        adb_map: ADB 设备映射，键为 serial，值为状态。

    Returns:
        (匹配的 serial, 设备状态) 元组，如果未找到则返回 (None, None)。
    """
    # 优先精确匹配
    if instance.adb_serial in adb_map:
        return instance.adb_serial, adb_map[instance.adb_serial]

    # 检查 IP:Port 格式 (BlueStacks 使用 expected_port + 1)
    if instance.expected_port:
        ip_port = f"127.0.0.1:{instance.expected_port + 1}"
        if ip_port in adb_map:
            return ip_port, adb_map[ip_port]

    return None, None


def collect_instance_status(
    instance: InstanceConfig, adb_map: dict[str, str], adb_error: str | None = None
) -> InstanceRuntimeStatus:
    player_running, pid_count = is_any_bluestacks_process_running()
    matched_serial, device_state = resolve_adb_serial_from_map(instance, adb_map)
    adb_connected = device_state is not None

    if device_state == "device":
        status = "running"
    elif device_state == "offline":
        status = "starting" if player_running else "unknown"
    elif device_state == "unauthorized":
        status = "error"
    elif adb_error:
        status = "error"
    elif player_running:
        status = "starting"
    else:
        status = "stopped"

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
    last_status = collect_instance_status(instance, {}, "未开始探测")

    while True:
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


# no_wait 模式下使用较短超时，因为不需要等待实例完全启动
LAUNCH_TIMEOUT_NO_WAIT = 10
LAUNCH_TIMEOUT_WAIT = 120


def start_bluestacks_instance(
    instance: InstanceConfig, player_path: str, no_wait: bool = False
) -> CommandResult:
    """启动 BlueStacks 实例。

    Args:
        instance: 实例配置。
        player_path: HD-Player.exe 路径。
        no_wait: 是否不等待实例启动完成。

    Returns:
        CommandResult，启动命令是否成功发送。
    """
    command = [player_path, "--instance", instance.instance_name]

    if no_wait:
        # 使用 Popen 启动后立即返回
        return launch_instance_no_wait(command)
    else:
        # 等待模式：启动后轮询状态直到 running 或超时
        return run_list_cmd(command, timeout=5)


def cmd_start(args: argparse.Namespace) -> int:
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

    no_wait = getattr(args, "no_wait", False)
    result = start_bluestacks_instance(instance, player_path, no_wait)
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
        after_adb_map, after_adb_error = get_connected_adb_devices(adb_path)
        after_status = collect_instance_status(instance, after_adb_map, after_adb_error)
        after_row = instance_status_to_dict(after_status)

        # 判断是否需要等待 - 如果已经启动成功就返回成功
        started_successfully = after_status.status == "running"

        payload = build_base_payload(
            "start",
            started_successfully,
            f"已发送启动命令到实例 {instance.id}"
            + ("" if started_successfully else "，请等待启动完成"),
        )
        payload["instance"] = after_row
        payload["player_path"] = player_path
        payload["adb_path"] = adb_path
        payload["launch_command"] = result.command
        payload["waited"] = False
        payload["already_running"] = started_successfully
        emit_result(args, payload, [after_row])
        return EXIT_OK if started_successfully else EXIT_OK

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
    payload["player_path"] = player_path
    payload["adb_path"] = adb_path
    payload["launch_command"] = result.command
    payload["elapsed_seconds"] = elapsed_seconds
    payload["waited"] = True
    if result.stderr:
        payload["stderr"] = result.stderr
    emit_result(args, payload, [row])
    return EXIT_OK if reached else EXIT_STATE_MISMATCH


def stop_instance_via_adb(
    instance: InstanceConfig, adb_path: str, matched_serial: str | None = None
) -> CommandResult:
    """使用 ADB 停止模拟器。

    Args:
        instance: 实例配置。
        adb_path: adb 可执行文件路径。
        matched_serial: 实际匹配的 ADB serial，如果为 None 则使用配置中的 adb_serial。
    """
    serial = matched_serial if matched_serial else instance.adb_serial
    return run_list_cmd([adb_path, "-s", serial, "emu", "kill"], timeout=20, allow_failure=True)


def disconnect_instance(
    instance: InstanceConfig, adb_path: str, matched_serial: str | None = None
) -> CommandResult:
    """断开 ADB 连接。

    Args:
        instance: 实例配置。
        adb_path: adb 可执行文件路径。
        matched_serial: 实际匹配的 ADB serial，如果为 None 则使用配置中的 adb_serial。
    """
    serial = matched_serial if matched_serial else instance.adb_serial
    return run_list_cmd([adb_path, "disconnect", serial], timeout=20, allow_failure=True)


def find_pid_by_port(port: int) -> int | None:
    """通过端口查找对应的进程 PID。

    Args:
        port: 端口号，例如 5555, 5565 等。

    Returns:
        进程的 PID，如果未找到则返回 None。
    """
    result = run_list_cmd(["netstat", "-ano"], timeout=10, allow_failure=True)
    if not result.ok:
        return None

    for line in result.stdout.split("\n"):
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    return int(parts[-1])
                except ValueError:
                    continue
    return None


def kill_process_by_pid(pid: int) -> CommandResult:
    """通过 PID 杀死进程。

    Args:
        pid: 进程 ID。
    """
    return run_list_cmd(["taskkill", "/F", "/PID", str(pid)], timeout=10, allow_failure=True)


def find_and_kill_bluestacks_instance(instance: InstanceConfig) -> CommandResult:
    """通过 WMI 查找并杀死指定实例的 BlueStacks 进程。

    调用 scripts/kill_bluestacks_instance.ps1 PowerShell 脚本来杀死进程。
    该脚本查找命令行中包含 "--instance <instance_name>" 的 HD-Player.exe 进程。

    Args:
        instance: 实例配置。

    Returns:
        CommandResult，命令执行结果。
    """
    ps_script_path = Path(__file__).parent / "kill_bluestacks_instance.ps1"

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps_script_path),
                "-InstanceName",
                instance.instance_name,
            ],
            capture_output=True,
            timeout=30,
            text=True,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        ok = result.returncode == 0
        return CommandResult(
            ok=ok,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            command=[
                "powershell",
                "-File",
                f"kill_bluestacks_instance.ps1 -InstanceName {instance.instance_name}",
            ],
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            ok=False,
            returncode=124,
            stdout="",
            stderr="命令执行超时",
            command=[
                "powershell",
                "-File",
                f"kill_bluestacks_instance.ps1 -InstanceName {instance.instance_name}",
            ],
        )
    except Exception as exc:
        return CommandResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr=f"命令执行失败: {exc}",
            command=[
                "powershell",
                "-File",
                f"kill_bluestacks_instance.ps1 -InstanceName {instance.instance_name}",
            ],
        )

    # 端口 = expected_port + 1
    port = instance.expected_port + 1

    # 使用 PowerShell 通过端口查找并杀死进程
    port = instance.expected_port + 1
    ps_script = f"""
$port = {port}
$connections = netstat -ano | Select-String ":{port}" | Where-Object {{ $_ -match 'LISTENING' }}
if ($connections) {{
    foreach ($conn in $connections) {{
        $line = $conn -split '\\s+' | Where-Object {{ $_ -ne '' }}
        $pid = $line[-1]
        if ($pid -match '^\\d+$') {{
            Write-Output "Killing PID: $pid (Port: $port)"
            taskkill /F /PID $pid
        }}
    }}
    exit 0
}} else {{
    Write-Output "No process listening on port $port"
    exit 1
}}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=30,
            text=True,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        ok = result.returncode == 0
        return CommandResult(
            ok=ok,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            command=["powershell", "-Command", f"kill by port {port}"],
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            ok=False,
            returncode=124,
            stdout="",
            stderr="命令执行超时",
            command=["powershell", "-Command", f"kill by port {port}"],
        )
    except Exception as exc:
        return CommandResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr=f"命令执行失败: {exc}",
            command=["powershell", "-Command", f"kill by port {port}"],
        )


def cmd_stop(args: argparse.Namespace) -> int:
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

    adb_map, adb_error = get_connected_adb_devices(adb_path)
    before_status = collect_instance_status(instance, adb_map, adb_error)
    if before_status.status == "stopped":
        row = instance_status_to_dict(before_status)
        payload = build_base_payload("stop", True, f"实例 {instance.id} 已停止，无需重复关闭")
        payload["instance"] = row
        payload["adb_path"] = adb_path
        emit_result(args, payload, [row])
        return EXIT_OK

    # 获取实际匹配的 serial (可能是 127.0.0.1:5555 格式)
    matched_serial, _ = resolve_adb_serial_from_map(instance, adb_map)

    stop_methods_used: list[str] = []

    # 首先尝试通过端口查找并杀死进程
    kill_by_port_result = find_and_kill_bluestacks_instance(instance)
    if kill_by_port_result.ok:
        stop_methods_used.append("kill by port")
        kill_result = kill_by_port_result
    else:
        # 端口方法失败，回退到 ADB 方法
        kill_result = stop_instance_via_adb(instance, adb_path, matched_serial)
        stop_methods_used.append("adb emu kill")

    disconnect_result = disconnect_instance(instance, adb_path, matched_serial)
    stop_methods_used.append("adb disconnect")

    started_at = time.time()
    final_status, reached = wait_for_instance_status(instance, adb_path, args.timeout, {"stopped"})
    elapsed_seconds = round(time.time() - started_at, 1)
    row = instance_status_to_dict(final_status)
    payload = build_base_payload(
        "stop",
        reached,
        f"实例 {instance.id} {'已停止' if reached else '停止超时，目标仍未进入 stopped 状态'}",
    )
    payload["instance"] = row
    payload["adb_path"] = adb_path
    payload["stop_method"] = " + ".join(stop_methods_used)
    payload["elapsed_seconds"] = elapsed_seconds
    payload["emu_kill"] = {
        "ok": kill_result.ok,
        "returncode": kill_result.returncode,
        "stdout": kill_result.stdout,
        "stderr": kill_result.stderr,
    }
    payload["disconnect"] = {
        "ok": disconnect_result.ok,
        "returncode": disconnect_result.returncode,
        "stdout": disconnect_result.stdout,
        "stderr": disconnect_result.stderr,
    }
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
概念说明:
  id            稳定实例编号，适合 app/agent 直接调用
  instance_name BlueStacks 多开管理器中的实例名
  adb_serial    该实例对应的 adb 设备序列号

默认实例映射:
{default_mapping}

输出格式:
  所有子命令都支持 --format table|json
  推荐 app/agent 使用 --format json

退出码:
  0  成功
  1  目标未达到期望状态（例如实例未运行，或启动/停止超时）
  2  参数错误
  3  环境错误（例如找不到 adb 或 HD-Player.exe）
  4  操作失败
  5  未知实例 id

常用示例:
  python scripts/bluestack-tool.py list
  python scripts/bluestack-tool.py list --format json
  python scripts/bluestack-tool.py status
  python scripts/bluestack-tool.py status --id 2
  python scripts/bluestack-tool.py status --id 2 --format json
  python scripts/bluestack-tool.py start --id 1
  python scripts/bluestack-tool.py start --id 2 --timeout 90
  python scripts/bluestack-tool.py start --id 2 --no-wait
  python scripts/bluestack-tool.py stop --id 2
  python scripts/bluestack-tool.py start --id 2 --player "C:\\Program Files\\BlueStacks_nxt\\HD-Player.exe"
  python scripts/bluestack-tool.py status --id 2 --adb "C:\\Android\\platform-tools\\adb.exe"

适合 agent 的典型调用流程:
  1) 先查询状态
     python scripts/bluestack-tool.py status --id 2 --format json
  2) 如果 status 不是 running，则启动实例
     python scripts/bluestack-tool.py start --id 2 --format json
  3) 再次确认状态
     python scripts/bluestack-tool.py status --id 2 --format json

说明:
  - start 只负责启动指定的 BlueStacks 实例。
  - stop 默认通过 adb -s <serial> emu kill 停止指定实例，不会默认强杀全部 BlueStacks 进程。
  - 当你知道实例名或 adb serial 与默认映射不一致时，可临时传入 --instance 或 --adb-serial 覆盖。
"""

    parser = argparse.ArgumentParser(
        description="BlueStacks 单文件控制工具：支持 list / status / start / stop，适合人工与 agent 调用。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出所有已知实例及当前状态")
    add_common_arguments(list_parser)
    list_parser.set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser("status", help="查询一个或全部实例状态")
    add_common_arguments(status_parser)
    status_parser.add_argument("--id", help="实例 id，例如 1 / 2 / 3 / 4")
    status_parser.add_argument("--instance", help="临时覆盖实例名，例如 Pie64_1")
    status_parser.add_argument("--adb-serial", help="临时覆盖 adb serial，例如 emulator-5564")
    status_parser.set_defaults(func=cmd_status)

    start_parser = subparsers.add_parser("start", help="启动指定实例")
    add_common_arguments(start_parser)
    start_parser.add_argument("--id", required=True, help="实例 id，例如 1 / 2 / 3 / 4")
    start_parser.add_argument("--instance", help="临时覆盖实例名，例如 Pie64_1")
    start_parser.add_argument("--adb-serial", help="临时覆盖 adb serial，例如 emulator-5564")
    start_parser.add_argument(
        "--no-wait", action="store_true", help="只发送启动命令，不等待实例进入 running"
    )
    start_parser.set_defaults(func=cmd_start)

    stop_parser = subparsers.add_parser("stop", help="停止指定实例")
    add_common_arguments(stop_parser)
    stop_parser.add_argument("--id", required=True, help="实例 id，例如 1 / 2 / 3 / 4")
    stop_parser.add_argument("--instance", help="临时覆盖实例名，例如 Pie64_1")
    stop_parser.add_argument("--adb-serial", help="临时覆盖 adb serial，例如 emulator-5564")
    stop_parser.set_defaults(func=cmd_stop)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "timeout", DEFAULT_TIMEOUT) < 0:
        payload = build_base_payload(
            args.command if getattr(args, "command", None) else "unknown",
            False,
            "--timeout 不能小于 0",
        )
        emit_result(args, payload)
        return EXIT_INVALID_ARGUMENT

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
