# -*- encoding=utf8 -*-
"""adb 命令的统一入口：首次调用前用**无管道**方式预热 adb server。

为什么需要预热
--------------
Windows 上 ``adb`` 客户端在没有 server 时会**派生出一个常驻 adb server**。
若这次调用带了 stdout/stderr 管道，新生的 server 会继承管道写端并一直持有，
调用方的 ``communicate()`` 就永远等不到 EOF —— 完整机理见 ``process_utils``
的模块 docstring 与 ``tests/test_adb_pipe_deadlock.py``。

对策：在「需要派生 server 的那一次」之前，先用 ``adb start-server`` 以
``DEVNULL``（无管道）把 server 拉起来并记下缓存标记。之后的 adb 命令都只是
「连到已存在的 server」，不会再派生新进程，也就不会再触发管道死锁。

``kill-server`` 之后 server 消失，必须让缓存失效，下一次调用重新预热。
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Sequence

from process_utils import CommandResult, terminate_process_tree
from process_utils import run_command as run_command  # 显式再导出，便于测试打桩

#: 单条 adb 命令的超时（秒）。冷启动期间 adb 客户端可能要先拉起 server，
#: 但超时保护必须真实生效 —— 见模块 docstring 的死锁说明。
DEFAULT_ADB_TIMEOUT = 20.0

#: 预热 ``adb start-server`` 的等待上限（秒），需覆盖冷启动最坏情况。
ADB_SERVER_START_TIMEOUT = 30.0

#: 视为 adb 可执行文件的文件名（不区分大小写）。
_ADB_EXECUTABLE_NAMES = ("adb", "adb.exe")

logger = logging.getLogger(__name__)

#: server 是否已预热。模块级标记，``kill-server`` 后置回 ``False``。
_server_ready = False


def is_adb_command(cmd: Sequence[str]) -> bool:
    """判断一条命令是不是 adb 调用。

    Args:
        cmd: 命令行序列，可能为空。

    Returns:
        若首个参数的可执行文件名（去掉目录、统一分隔符后）是 adb 则为 ``True``。
    """
    if not cmd:
        return False
    executable = os.path.basename(str(cmd[0]).replace("\\", "/")).lower()
    return executable in _ADB_EXECUTABLE_NAMES


def ensure_adb_server(adb_path: str, timeout: float = ADB_SERVER_START_TIMEOUT) -> bool:
    """以「无管道」方式预热 adb server。

    使用 ``DEVNULL`` 而非管道，因此即使 ``start-server`` 派生出常驻 server，
    也不存在「调用方等待管道 EOF」这一环，天然免疫管道死锁。

    Args:
        adb_path: adb 可执行文件路径。
        timeout: 等待 ``start-server`` 结束的秒数上限。

    Returns:
        预热是否成功（命令正常退出）。
    """
    logger.debug("预热 adb server: %s", adb_path)
    process = subprocess.Popen(
        [adb_path, "start-server"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("⚠️ adb start-server 超时（>%.0fs），按未就绪处理", timeout)
        terminate_process_tree(process)
        return False
    return process.returncode == 0


def _is_kill_server(cmd: Sequence[str]) -> bool:
    """判断命令是否为 ``adb kill-server``。

    Args:
        cmd: 完整的 adb 命令行。

    Returns:
        子命令为 ``kill-server`` 时为 ``True``。
    """
    return any(str(part).lower() == "kill-server" for part in cmd[1:])


def run_adb_command(
    cmd: Sequence[str],
    timeout: float = DEFAULT_ADB_TIMEOUT,
) -> CommandResult:
    """执行一条 adb 命令，必要时先预热 server。

    Args:
        cmd: 完整的 adb 命令行，例如 ``["adb", "devices"]``。
        timeout: 单条命令的超时秒数。

    Returns:
        命令执行结果；超时以 ``CommandResult.timed_out`` 表达，不抛异常。
    """
    global _server_ready

    cmd = list(cmd)
    adb_path = str(cmd[0]) if cmd else ""

    if adb_path and not _server_ready:
        if ensure_adb_server(adb_path):
            _server_ready = True
        else:
            # 预热失败不阻断本次调用：放行原命令，让它自己报出真实错误。
            logger.debug("adb server 预热未成功，继续执行原命令")

    result = run_command(cmd, timeout=timeout)

    if _is_kill_server(cmd):
        # server 已被显式杀掉，缓存必须失效，下一次调用重新预热。
        _server_ready = False

    return result
