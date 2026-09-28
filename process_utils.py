# -*- encoding=utf8 -*-
"""子进程执行工具：让「超时保护必须真实生效」这件事不再依赖平台默认行为。

平台背景（Windows 真机实测，2026-09-27 06:05）
--------------------------------------------
``subprocess.run(cmd, capture_output=True, timeout=N)`` 在 Windows 上超时后，
CPython 的 ``subprocess.run`` 会在 ``_mswindows`` 分支里**再次调用无超时的**
``communicate()`` 去收集残留输出::

    except TimeoutExpired as exc:
        process.kill()
        if _mswindows:
            exc.stdout, exc.stderr = process.communicate()   # ← 没有 timeout

若被杀子进程派生出的孙进程继承了这对 stdout/stderr 管道的写端（adb client 在
没有 server 时拉起的常驻 adb server 正是如此，C 实现用可继承句柄），
``communicate()`` 永远等不到 EOF —— 调用方被无限期挂住，``timeout`` 形同虚设。

真实后果：会话 mage_alt 卡在 ``adb devices`` 上 **194 秒零日志**，编排器看门狗
按「180 秒无日志」判它僵死，杀掉会话并重启了模拟器。

本模块的对策：**不使用管道**。把子进程的 stdout/stderr 重定向到临时文件，于是：

1. 进程正常退出时，``wait()`` 立即返回，读文件即可拿到完整输出；
2. 超时时，``wait(timeout)`` 抛 ``TimeoutExpired``，终止进程树后照旧读文件 ——
   文件不具备「EOF 依赖写端关闭」的语义，读操作不会被孙进程拖住。

因此无论孙进程如何继承句柄，调用方都能守时返回。相关回归测试见
``tests/test_adb_pipe_deadlock.py`` 与 ``tests/test_process_utils.py``。
"""

from __future__ import annotations

import locale
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional, Sequence, Union

#: 允许的命令行形态：参数序列，或 ``shell=True`` 时的整条命令字符串。
CommandArg = Union[str, Sequence[str]]


@dataclass(frozen=True)
class CommandResult:
    """一条命令的执行结果。

    Attributes:
        command: 实际执行的命令行（元组形式，便于打日志与断言）。
        returncode: 退出码；进程被强制终止时可能为负值。
        stdout: 子进程标准输出的原始字节。
        stderr: 子进程标准错误的原始字节。
        timed_out: 是否因超时被强制终止。为 ``True`` 时 ``returncode`` 不可信。
    """

    command: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        """命令是否既未超时、又正常退出（退出码为 0）。"""
        return not self.timed_out and self.returncode == 0

    def stdout_text(self) -> str:
        """以项目约定编码解码标准输出。

        Returns:
            解码后的标准输出文本。
        """
        return decode_output(self.stdout)

    def stderr_text(self) -> str:
        """以项目约定编码解码标准错误。

        Returns:
            解码后的标准错误文本。
        """
        return decode_output(self.stderr)


def decode_output(raw_output: Optional[bytes]) -> str:
    """把子进程输出的原始字节解码成文本。

    依次尝试 UTF-8、系统首选编码、GBK，全部失败时用替换字符兜底，行为与
    ``emulator_control.decode_process_output`` 保持一致。

    Args:
        raw_output: 子进程输出；允许为 ``None``。

    Returns:
        解码后的文本。若无法准确匹配编码则使用替换字符兜底。
    """
    if raw_output is None:
        return ""

    candidate_encodings = (
        "utf-8",
        locale.getpreferredencoding(False) or "utf-8",
        "gbk",
    )
    for encoding in candidate_encodings:
        try:
            return raw_output.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_output.decode("utf-8", errors="replace")


def terminate_process_tree(process: subprocess.Popen) -> None:
    """尽力终止一个进程及其派生出的子进程。

    超时后只 ``kill()`` 直接子进程是不够的：它很可能已经派生出仍在运行的孙进程。
    在 Windows 上用 ``taskkill /T`` 连根拔起，其它平台退回 ``kill()``。

    Args:
        process: 需要终止的进程。

    Returns:
        None
    """
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except Exception:  # noqa: BLE001 - 尽力而为，失败则退回 kill()
            pass

    try:
        process.kill()
    except Exception:  # noqa: BLE001 - 进程可能已退出
        pass


def run_command(
    cmd: CommandArg,
    timeout: float,
    shell: bool = False,
) -> CommandResult:
    """执行一条命令，保证在 ``timeout`` 秒内返回（超时则终止进程树）。

    输出经临时文件而非管道收集，因此免疫「孙进程持有管道句柄 → 调用方挂死」
    的问题；超时以返回值 ``timed_out`` 表达，不向调用方抛异常。

    Args:
        cmd: 参数序列；``shell=True`` 时也可传整条命令字符串。
        timeout: 超时秒数。
        shell: 是否通过系统 shell 执行 ``cmd``。

    Returns:
        命令执行结果。
    """
    command = (cmd,) if isinstance(cmd, str) else tuple(cmd)

    with tempfile.TemporaryFile() as out_file, tempfile.TemporaryFile() as err_file:
        process = subprocess.Popen(
            cmd,
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=out_file,
            stderr=err_file,
        )
        try:
            process.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            terminate_process_tree(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            timed_out = True

        out_file.seek(0)
        err_file.seek(0)
        stdout = out_file.read()
        stderr = err_file.read()

    return CommandResult(
        command=command,
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
    )
