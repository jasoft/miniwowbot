"""临时脚本：以常驻父进程启动 levelup，避免子进程被 Agent 沙箱回收。

2026-10-14 修复后重启实例用。uv -> python -> 引擎循环，父进程必须长期存活。

用法（在 Agent 终端里，需 dangerouslyDisableSandbox）：
    python keep_levelup_alive.py [保持秒数]
"""

from __future__ import annotations

import subprocess
import sys
import time

UV = r"C:\Users\11885\.local\bin\uv.exe"
CWD = r"E:\Projects\miniwowbot\levelup.air"
CONSOLE_LOG = r"E:\Projects\miniwowbot\levelup.air\output\temp\levelup_console.log"
DETACHED = 0x00000008 | 0x00000200 | 0x08000000

HOLD_SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 86400


def _levelup_python_pid() -> int:
    """返回正在跑 levelup.py 的 python 进程 PID，没有时返回 0。"""
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
    ).stdout
    pids = [
        int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"python.exe"')
    ]
    if not pids:
        return 0
    query = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
        "| Where-Object { $_.CommandLine -like '*levelup*' } "
        "| Select-Object -ExpandProperty ProcessId"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", query],
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
    )
    return int(result.stdout.strip() or 0) if result.stdout.strip().isdigit() else 0


if __name__ == "__main__":
    if _levelup_python_pid():
        print("[keep] levelup 已在运行，保持器退出", flush=True)
        sys.exit(0)
    log_handle = open(CONSOLE_LOG, "a", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [UV, "run", "./levelup.py"],
        cwd=CWD,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=DETACHED,
        close_fds=True,
        stdin=subprocess.DEVNULL,
    )
    print(f"[keep] launched uv pid={proc.pid}", flush=True)
    deadline = time.time() + HOLD_SECONDS
    while time.time() < deadline:
        time.sleep(30)
        if proc.poll() is not None:
            print(f"[keep] uv 已退出 code={proc.returncode}，保持器结束", flush=True)
            break
    else:
        print(f"[keep] 保持 {HOLD_SECONDS}s 到期，父进程退出（子进程独立运行）", flush=True)
