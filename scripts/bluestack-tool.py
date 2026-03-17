#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BlueStacks 单文件控制工具 (增强识别版)。

优化方案：
- 多维识别：结合 CommandLine、MainWindowTitle 和端口反查，精准定位进程。
- 极速探测：利用原生 socket 进行端口开放状态检查。
- 鲁棒停止：支持 PID 直接强杀，解决 CommandLine 缺失导致的漏杀问题。
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
POLL_INTERVAL_SECONDS = 0.5
BLUESTACKS_PROCESS_NAMES = ("HD-Player.exe", "Bluestacks.exe")


@dataclass(frozen=True)
class InstanceConfig:
    id: str
    label: str
    instance_name: str
    adb_serial: str
    window_title: str | None = None  # 新增：用于匹配物理窗口标题
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
        window_title="主账号", # 匹配实际窗口标题
        expected_port=5554,
    ),
    InstanceConfig(
        id="2",
        label="多开 1",
        instance_name="Pie64_1",
        adb_serial="emulator-5564",
        window_title="金币法师号", # 匹配实际窗口标题
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


def build_default_instances() -> list[InstanceConfig]:
    return list(DEFAULT_INSTANCES)


def resolve_instance_by_id(instance_id: str) -> InstanceConfig | None:
    for inst in build_default_instances():
        if inst.id == str(instance_id): return inst
    return None


def resolve_adb_path(cli_path: str | None = None) -> str | None:
    for p in [cli_path, os.environ.get("ADB_PATH"), shutil.which("adb"), "platform-tools/adb.exe"]:
        if p and Path(p).exists(): return str(Path(p).resolve())
    return shutil.which("adb")


def resolve_bluestacks_player_path(cli_path: str | None = None) -> str | None:
    candidates = [cli_path, os.environ.get("BLUESTACKS_PLAYER_PATH"), r"C:\Program Files\BlueStacks_nxt\HD-Player.exe", r"D:\Program Files\BlueStacks_nxt\HD-Player.exe"]
    for c in candidates:
        if c and Path(c).exists(): return str(Path(c))
    return None


class ProcessCache:
    """增强版进程信息缓存。"""

    _cache: list[dict[str, Any]] | None = None
    _last_update: float = 0

    @classmethod
    def get_all_processes(cls, force_refresh: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        if cls._cache is not None and not force_refresh and (now - cls._last_update < 0.5):
            return cls._cache

        processes = []
        try:
            # 1. 获取 Win32_Process 信息 (含 CommandLine)
            ps_cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process | " +
                "Where-Object { $_.Name -match 'HD-Player|Bluestacks' } | " +
                "Select-Object ProcessId, Name, CommandLine | " +
                "ConvertTo-Json -Compress"
            ]
            result = subprocess.run(ps_cmd, capture_output=True, text=True, errors="replace")
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, dict): data = [data]
                    for item in data:
                        processes.append({
                            "ProcessId": item.get("ProcessId"),
                            "Name": item.get("Name"),
                            "CommandLine": item.get("CommandLine") or "",
                            "MainWindowTitle": ""
                        })
                except Exception:
                    pass
            
            # 2. 获取窗口标题 (Get-Process 的 MainWindowTitle)
            ps_title_cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-Process | Where-Object { $_.ProcessName -match 'HD-Player|Bluestacks' } | " +
                "Select-Object Id, MainWindowTitle | ConvertTo-Json -Compress"
            ]
            title_res = subprocess.run(ps_title_cmd, capture_output=True, text=True, errors="replace")
            if title_res.returncode == 0 and title_res.stdout.strip():
                try:
                    title_data = json.loads(title_res.stdout)
                    if isinstance(title_data, dict): title_data = [title_data]
                    title_map = {item.get("Id"): item.get("MainWindowTitle") or "" for item in title_data}
                    for p in processes:
                        p["MainWindowTitle"] = title_map.get(p["ProcessId"], "")
                except Exception:
                    pass

        except Exception:
            pass

        cls._cache = processes
        cls._last_update = now
        return processes

    @classmethod
    def find_instance_pids(cls, instance: InstanceConfig) -> list[int]:
        """通过多种方式定位实例 PID。"""
        all_procs = cls.get_all_processes()
        pids = set()
        
        target_name = instance.instance_name
        target_label = instance.label
        target_title = instance.window_title
        
        for proc in all_procs:
            pid = proc.get("ProcessId")
            if not pid: continue
            
            cmdline = proc.get("CommandLine", "")
            title = proc.get("MainWindowTitle", "")
            
            # A. 命令行精准匹配
            if f"--instance {target_name}" in cmdline or f"--instance={target_name}" in cmdline:
                pids.add(int(pid))
                continue
            
            # B. 明确的窗口标题匹配
            if target_title and target_title == title:
                pids.add(int(pid))
                continue

            # C. 标签包含匹配 (兼容之前的逻辑)
            if target_label and target_label in title:
                pids.add(int(pid))
                continue
            
            # D. 特殊处理 Pie64 默认标题
            if target_name == "Pie64" and not target_title and ("BlueStacks" in title or "蓝叠" in title):
                pids.add(int(pid))
                continue

        # E. 端口反查 (即便进程列表漏了，只要端口在监听，就必须抓到 PID)
        if instance.expected_port:
            port = instance.expected_port + 1
            try:
                res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
                for line in res.stdout.splitlines():
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            pids.add(int(parts[-1]))
            except Exception:
                pass

        return list(pids)


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def decode_process_output(output: bytes | str | None) -> str:
    if output is None: return ""
    if isinstance(output, str): return output
    for encoding in ("utf-8", "gbk", "cp936", sys.getdefaultencoding()):
        try: return output.decode(encoding)
        except UnicodeDecodeError: continue
    return output.decode("utf-8", errors="replace")


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False


def collect_instance_status(
    instance: InstanceConfig, adb_map: dict[str, str], adb_error: str | None = None
) -> InstanceRuntimeStatus:
    instance_pids = ProcessCache.find_instance_pids(instance)
    player_running = len(instance_pids) > 0
    pid_count = len(instance_pids)

    port_open = False
    if instance.expected_port:
        port_open = is_port_open(instance.expected_port + 1)

    matched_serial, device_state = resolve_adb_serial_from_map(instance, adb_map)
    
    # 彻底解决逻辑：进程不在即为停止
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
        else:
            status = "starting"

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
        last_error=adb_error if status == "error" else None,
    )


def wait_for_instance_status(
    instance: InstanceConfig,
    adb_path: str | None,
    timeout_sec: int,
    desired_statuses: set[str],
) -> tuple[InstanceRuntimeStatus, bool]:
    deadline = time.time() + max(timeout_sec, 0)
    while True:
        ProcessCache.get_all_processes(force_refresh=True)
        adb_map, adb_error = get_connected_adb_devices(adb_path)
        last_status = collect_instance_status(instance, adb_map, adb_error)
        if last_status.status in desired_statuses:
            return last_status, True
        if time.time() >= deadline:
            return last_status, False
        time.sleep(POLL_INTERVAL_SECONDS)


def find_and_kill_bluestacks_instance(instance: InstanceConfig) -> CommandResult:
    pids = ProcessCache.find_instance_pids(instance)
    if not pids:
        return CommandResult(ok=False, returncode=1, stdout="", stderr="未找到匹配的进程", command=[])

    success_count = 0
    errors = []
    for pid in set(pids):
        # 先试温柔的，再试强硬的
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
        time.sleep(0.5)
        res = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
        if res.returncode == 0 or "没有找到" in res.stderr:
            success_count += 1
        else:
            errors.append(f"PID {pid}: {res.stderr.strip()}")

    if success_count > 0:
        return CommandResult(ok=True, returncode=0, stdout=f"成功终止 {success_count} 个进程", stderr=" | ".join(errors), command=[])
    return CommandResult(ok=False, returncode=1, stdout="", stderr="终止进程失败: " + " | ".join(errors), command=[])


def run_list_cmd(command: list[str], timeout: int = 30, allow_failure: bool = False) -> CommandResult:
    try:
        completed = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        stdout = decode_process_output(completed.stdout).strip()
        stderr = decode_process_output(completed.stderr).strip()
        return CommandResult(ok=(completed.returncode == 0 or allow_failure), returncode=completed.returncode, stdout=stdout, stderr=stderr, command=command)
    except Exception as exc:
        return CommandResult(ok=False, returncode=1, stdout="", stderr=str(exc), command=command)


def get_connected_adb_devices(adb_path: str | None) -> tuple[dict[str, str], str | None]:
    if not adb_path: return {}, "未找到 adb"
    result = run_list_cmd([adb_path, "devices"], timeout=20)
    if not result.ok: return {}, result.stderr
    
    devices = {}
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("List of devices"): continue
        parts = line.split()
        if len(parts) >= 2: devices[parts[0].strip()] = parts[1].strip()
    return devices, None


def resolve_adb_serial_from_map(instance: InstanceConfig, adb_map: dict[str, str]) -> tuple[str | None, str | None]:
    if instance.adb_serial in adb_map: return instance.adb_serial, adb_map[instance.adb_serial]
    if instance.expected_port:
        ip_port = f"127.0.0.1:{instance.expected_port + 1}"
        if ip_port in adb_map: return ip_port, adb_map[ip_port]
    return None, None


def cmd_list(args: argparse.Namespace) -> int:
    ProcessCache.get_all_processes(force_refresh=True)
    adb_path = resolve_adb_path(args.adb)
    adb_map, adb_error = get_connected_adb_devices(adb_path)
    statuses = [collect_instance_status(inst, adb_map, adb_error) for inst in build_default_instances()]
    rows = [asdict(s) for s in statuses]
    if args.format == "json": print(json.dumps({"ok": True, "instances": rows}, ensure_ascii=False, indent=2))
    else: print_table(rows)
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    ProcessCache.get_all_processes(force_refresh=True)
    instance = resolve_instance_by_id(str(args.id)) if args.id else None
    adb_path = resolve_adb_path(args.adb)
    adb_map, adb_error = get_connected_adb_devices(adb_path)
    
    if instance:
        status = collect_instance_status(instance, adb_map, adb_error)
        row = asdict(status)
        if args.format == "json": print(json.dumps({"ok": status.status == "running", "instance": row}, ensure_ascii=False, indent=2))
        else: print_table([row]); print(f"\n当前状态: {status.status}")
        return EXIT_OK if status.status == "running" else EXIT_STATE_MISMATCH
    
    return cmd_list(args)


def cmd_stop(args: argparse.Namespace) -> int:
    instance = resolve_instance_by_id(str(args.id))
    if not instance: return EXIT_UNKNOWN_INSTANCE
    
    adb_path = resolve_adb_path(args.adb)
    ProcessCache.get_all_processes(force_refresh=True)
    before = collect_instance_status(instance, {}, None)
    if before.status == "stopped":
        print(f"实例 {args.id} 已停止")
        return EXIT_OK

    # 尝试多种停止方式
    find_and_kill_bluestacks_instance(instance)
    adb_map, _ = get_connected_adb_devices(adb_path)
    serial, _ = resolve_adb_serial_from_map(instance, adb_map)
    if serial:
        subprocess.run([adb_path, "-s", serial, "emu", "kill"], capture_output=True)
        subprocess.run([adb_path, "disconnect", serial], capture_output=True)

    final_status, reached = wait_for_instance_status(instance, adb_path, args.timeout, {"stopped"})
    row = asdict(final_status)
    if args.format == "json": print(json.dumps({"ok": reached, "instance": row}, ensure_ascii=False, indent=2))
    else: print_table([row]); print(f"\n结果: {'已停止' if reached else '停止超时'}")
    return EXIT_OK if reached else EXIT_STATE_MISMATCH


def cmd_start(args: argparse.Namespace) -> int:
    instance = resolve_instance_by_id(str(args.id))
    if not instance: return EXIT_UNKNOWN_INSTANCE
    player_path = resolve_bluestacks_player_path(args.player)
    if not player_path: return EXIT_ENVIRONMENT_ERROR
    
    adb_path = resolve_adb_path(args.adb)
    ProcessCache.get_all_processes(force_refresh=True)
    if collect_instance_status(instance, {}, None).status == "running":
        print("实例已在运行")
        return EXIT_OK

    subprocess.Popen([player_path, "--instance", instance.instance_name], start_new_session=True)
    if args.no_wait: return EXIT_OK

    final_status, reached = wait_for_instance_status(instance, adb_path, args.timeout, {"running"})
    if args.format == "json": print(json.dumps({"ok": reached, "instance": asdict(final_status)}, ensure_ascii=False, indent=2))
    else: print(f"启动{'成功' if reached else '超时'}")
    return EXIT_OK if reached else EXIT_STATE_MISMATCH


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows: return
    headers = ["id", "label", "instance_name", "status", "pid_count", "adb_connected"]
    widths = {h: max(len(h), max([len(str(r.get(h, ""))) for r in rows])) for h in headers}
    print("  ".join([h.ljust(widths[h]) for h in headers]))
    print("  ".join(["-" * widths[h] for h in headers]))
    for r in rows: print("  ".join([str(r.get(h, "")).ljust(widths[h]) for h in headers]))


def main() -> int:
    parser = argparse.ArgumentParser(description="BlueStacks 控制工具 (增强版)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for cmd in ["list", "status", "start", "stop"]:
        p = subparsers.add_parser(cmd)
        p.add_argument("--id", help="实例 id")
        p.add_argument("--format", choices=["table", "json"], default="table")
        p.add_argument("--adb")
        p.add_argument("--player")
        p.add_argument("--timeout", type=int, default=60)
        if cmd == "start": p.add_argument("--no-wait", action="store_true")
        p.set_defaults(func=eval(f"cmd_{cmd}"))
    args = parser.parse_args()
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
