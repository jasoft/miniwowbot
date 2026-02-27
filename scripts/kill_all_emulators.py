#!/usr/bin/env python3
"""一键紧急停机脚本。

用途：
1. 结束副本相关脚本进程（run_dungeons/cron/auto_dungeon）。
2. 关闭全部模拟器（优先 MuMuManager，再回退 ADB）。
3. 强制清理模拟器进程，避免反复拉起。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from emulator_control import (
    DEFAULT_EMULATOR_PROCESS_NAMES,
    decode_process_output,
    force_kill_processes,
    shutdown_all_emulators,
)
from logger_config import setup_logger

SCRIPT_DIR = Path(__file__).resolve().parent.parent


def load_emulators(config_path: Path) -> list[str]:
    """加载 emulators.json 中的模拟器地址列表。

    Args:
        config_path: emulators.json 路径。

    Returns:
        模拟器地址列表；读取失败时返回空列表。
    """
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    sessions_raw = payload.get("sessions", []) if isinstance(payload, dict) else payload
    if not isinstance(sessions_raw, list):
        return []

    emulators: list[str] = []
    for item in sessions_raw:
        if not isinstance(item, dict):
            continue
        emulator = str(item.get("emulator", "")).strip()
        if emulator:
            emulators.append(emulator)
    return emulators


def collect_process_keywords() -> list[str]:
    """收集需要清理的脚本关键字。

    环境变量 ``PANIC_STOP_PROCESS_KEYWORDS`` 可额外补充，使用逗号分隔。

    Returns:
        脚本命令行关键字列表。
    """
    keywords = [
        "run_dungeons.py",
        "cron_run_all_dungeons.py",
        "auto_dungeon.py",
    ]

    extra = os.getenv("PANIC_STOP_PROCESS_KEYWORDS", "")
    if extra.strip():
        keywords.extend([item.strip() for item in extra.split(",") if item.strip()])

    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        key = keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(keyword)
    return deduped


def list_target_pids(keywords: Sequence[str]) -> list[int]:
    """按命令行关键字查找待终止 PID。

    Args:
        keywords: 命令行关键字列表。

    Returns:
        命中的 PID 列表。
    """
    if not keywords:
        return []

    if os.name == "nt":
        return _list_target_pids_windows(keywords)
    return _list_target_pids_posix(keywords)


def kill_pid_tree(pid: int) -> bool:
    """强制结束 PID 对应的进程树。

    Args:
        pid: 目标进程 PID。

    Returns:
        终止成功返回 ``True``，否则返回 ``False``。
    """
    if pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=False,
            timeout=20,
        )
        return result.returncode == 0

    try:
        os.killpg(pid, signal.SIGKILL)
        return True
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
            return True
        except Exception:
            return False


def load_force_kill_process_names() -> list[str]:
    """加载需要强杀的模拟器进程名。

    环境变量 ``EMULATOR_FORCE_KILL_PROCESS_NAMES`` 可覆盖追加，使用逗号分隔。

    Returns:
        进程名列表。
    """
    names = list(DEFAULT_EMULATOR_PROCESS_NAMES)
    extra = os.getenv("EMULATOR_FORCE_KILL_PROCESS_NAMES", "")
    if extra.strip():
        names.extend([item.strip() for item in extra.split(",") if item.strip()])

    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(name)
    return deduped


def _list_target_pids_windows(keywords: Sequence[str]) -> list[int]:
    """Windows 下查询匹配关键字的进程 PID。

    Args:
        keywords: 命令行关键字列表。

    Returns:
        命中的 PID 列表。
    """
    escaped_keywords: list[str] = []
    for keyword in keywords:
        candidate = keyword.strip()
        if not candidate:
            continue
        escaped_keywords.append("'" + candidate.replace("'", "''") + "'")

    keyword_items = ", ".join(escaped_keywords)
    script = (
        f"$targets = @({keyword_items}); "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        "$cmd = $_.CommandLine; "
        "if (-not $cmd) { return $false } "
        "foreach ($target in $targets) { if ($cmd -like \"*$target*\") { return $true } } "
        "return $false "
        "} | Select-Object -ExpandProperty ProcessId | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["pwsh", "-NoLogo", "-NoProfile", "-Command", script],
        capture_output=True,
        text=False,
        timeout=30,
    )
    if result.returncode != 0:
        return []
    return _parse_pid_json(decode_process_output(result.stdout))


def _list_target_pids_posix(keywords: Sequence[str]) -> list[int]:
    """POSIX 下查询匹配关键字的进程 PID。

    Args:
        keywords: 命令行关键字列表。

    Returns:
        命中的 PID 列表。
    """
    pids: set[int] = set()
    for keyword in keywords:
        result = subprocess.run(
            ["pgrep", "-f", keyword],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            try:
                pids.add(int(line.strip()))
            except ValueError:
                continue
    return sorted(pids)


def _parse_pid_json(raw_text: str) -> list[int]:
    """解析 PowerShell JSON 输出中的 PID 列表。

    Args:
        raw_text: PowerShell 输出文本。

    Returns:
        PID 列表。
    """
    text = raw_text.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, int):
        return [payload]
    if isinstance(payload, list):
        result: list[int] = []
        for item in payload:
            if isinstance(item, int):
                result.append(item)
            elif isinstance(item, str):
                try:
                    result.append(int(item))
                except ValueError:
                    continue
        return result
    return []


def main() -> int:
    """脚本入口。

    Returns:
        进程退出码。
    """
    logger = setup_logger(name="panic_stop", level="INFO", use_color=True)
    logger.info("🚨 开始执行一键停机：结束脚本进程 + 关闭模拟器 + 清理进程")

    emulators = load_emulators(SCRIPT_DIR / "emulators.json")
    if emulators:
        logger.info(f"📱 从 emulators.json 读取到 {len(emulators)} 个模拟器配置")
    else:
        logger.warning("⚠️ 未读取到模拟器配置，将仅执行进程清理")

    keywords = collect_process_keywords()
    pids = list_target_pids(keywords)
    current_pid = os.getpid()
    cleaned_pids = sorted({pid for pid in pids if pid != current_pid})

    for pid in cleaned_pids:
        if kill_pid_tree(pid):
            logger.info(f"✅ 已终止进程树 PID={pid}")
        else:
            logger.warning(f"⚠️ 终止进程树失败 PID={pid}")

    shutdown_all_emulators(emulators, logger)
    force_kill_processes(load_force_kill_process_names(), logger)

    logger.info("🛑 一键停机执行完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
