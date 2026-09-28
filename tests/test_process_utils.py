# -*- encoding=utf8 -*-
"""``process_utils`` / ``adb_runner`` 的单元测试。

关注三件事：
1. ``run_command`` 的超时保护是否真实生效（含「孙进程抢走管道句柄」的极端构造）；
2. ``adb_runner`` 是否在首个 adb 命令前**无管道**地预热 server，
   并在 ``kill-server`` 之后重新预热；
3. 正常命令的输出与退出码仍能被正确取回。

平台背景见 ``process_utils`` 模块 docstring 与 ``tests/test_adb_pipe_deadlock.py``。
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

import adb_runner
import process_utils

#: 等待工作线程结束的上限（秒），用于把「挂死」变成断言失败而不是卡住 pytest。
WATCHDOG_JOIN_TIMEOUT = 12.0

_GRANDCHILD_LIFETIME = 30

_STUB_SOURCE = '''
"""测试桩：派生出继承调用者 stdout/stderr 管道句柄的常驻孙进程。"""

import subprocess
import sys
import time

subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep({grandchild})"],
    close_fds=False,
)

if {child_lifetime}:
    time.sleep({child_lifetime})

sys.exit(0)
'''


def _write_pipe_holding_stub(directory: Path, child_lifetime: int = 0) -> str:
    """写一个「派生持有管道句柄的孙进程」的桩脚本。

    Args:
        directory: 桩脚本存放目录（通常为 pytest 的 ``tmp_path``）。
        child_lifetime: 桩进程自身存活秒数；0 表示派生出孙进程后立即退出。

    Returns:
        桩脚本的绝对路径。
    """
    stub = directory / "fake_pipe_holding_child.py"
    stub.write_text(
        textwrap.dedent(
            _STUB_SOURCE.format(grandchild=_GRANDCHILD_LIFETIME, child_lifetime=child_lifetime)
        ).strip(),
        encoding="utf-8",
    )
    return str(stub)


def _run_with_watchdog(target) -> tuple[bool, float]:
    """在守护线程里执行 ``target``，返回它是否在限期内结束。

    Args:
        target: 无参可调用对象。

    Returns:
        二元组 ``(finished, elapsed)``。
    """
    worker = threading.Thread(target=target, daemon=True)
    started = time.monotonic()
    worker.start()
    worker.join(timeout=WATCHDOG_JOIN_TIMEOUT)
    return (not worker.is_alive()), time.monotonic() - started


class TestRunCommand:
    """``process_utils.run_command`` 的基础行为。"""

    def test_captures_stdout_and_returncode(self):
        """正常命令应返回退出码与解码后的输出。"""
        result = process_utils.run_command([sys.executable, "-c", "print('hello-adb')"], timeout=30)

        assert result.timed_out is False
        assert result.ok is True
        assert "hello-adb" in result.stdout_text()

    def test_marks_timeout_instead_of_raising(self):
        """超时应返回 ``timed_out=True`` 而不是抛异常。"""
        result = process_utils.run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"], timeout=1
        )

        assert result.timed_out is True
        assert result.ok is False

    def test_supports_shell_command_string(self):
        """``shell=True`` 时接受命令字符串。"""
        result = process_utils.run_command("echo shell-mode", timeout=30, shell=True)

        assert result.timed_out is False
        assert "shell-mode" in result.stdout_text()


@pytest.mark.skipif(os.name != "nt", reason="管道句柄继承导致的死锁是 Windows 特有行为")
class TestRunCommandPipeHazard:
    """孙进程持有管道句柄时，``run_command`` 仍须守时。"""

    def test_returns_output_when_child_exits_but_grandchild_holds_pipe(self, tmp_path: Path):
        """子进程已退出、管道被孙进程占着：应正常返回并拿到输出。"""
        stub = _write_pipe_holding_stub(tmp_path)
        outcome: dict = {}

        def call() -> None:
            outcome["result"] = process_utils.run_command([sys.executable, stub], timeout=5)

        finished, elapsed = _run_with_watchdog(call)

        assert finished, f"命令被管道句柄挂住（>{WATCHDOG_JOIN_TIMEOUT:.0f}s 未返回）"
        assert elapsed < WATCHDOG_JOIN_TIMEOUT
        assert outcome["result"].ok is True

    def test_timeout_still_enforced_when_grandchild_holds_pipe(self, tmp_path: Path):
        """子进程自身也不退出时，超时必须照常生效。"""
        stub = _write_pipe_holding_stub(tmp_path, child_lifetime=_GRANDCHILD_LIFETIME)
        outcome: dict = {}

        def call() -> None:
            outcome["result"] = process_utils.run_command([sys.executable, stub], timeout=2)

        finished, elapsed = _run_with_watchdog(call)

        assert finished, f"超时保护失效：命令挂住 >{WATCHDOG_JOIN_TIMEOUT:.0f}s"
        assert outcome["result"].timed_out is True
        assert elapsed < WATCHDOG_JOIN_TIMEOUT


class TestDecodeOutput:
    """输出解码的兜底策略。"""

    def test_handles_none_and_utf8(self):
        assert process_utils.decode_output(None) == ""
        assert process_utils.decode_output("中文".encode("utf-8")) == "中文"


class TestIsAdbCommand:
    """adb 命令识别。"""

    @pytest.mark.parametrize(
        "cmd",
        [
            ["adb", "devices"],
            ["C:\\ProgramData\\chocolatey\\bin\\adb.exe", "devices"],
            ["/usr/local/bin/adb", "connect", "127.0.0.1:5555"],
        ],
    )
    def test_matches_adb(self, cmd):
        assert adb_runner.is_adb_command(cmd) is True

    @pytest.mark.parametrize(
        "cmd",
        [
            [],
            [sys.executable, "script.py"],
            ["tasklist", "/FO", "CSV"],
            ["MuMuManager.exe", "info"],
        ],
    )
    def test_rejects_non_adb(self, cmd):
        assert adb_runner.is_adb_command(cmd) is False


class _FakePopen:
    """记录调用参数的假 ``Popen``。"""

    def __init__(self):
        self.returncode = 0

    def wait(self, timeout=None):  # noqa: D401 - 与 Popen 接口保持一致
        return 0

    def kill(self):  # noqa: D401 - 与 Popen 接口保持一致
        self.returncode = -9


class TestEnsureAdbServer:
    """adb server 预热必须使用 DEVNULL（无管道 → 无法被孙进程卡住）。"""

    def test_uses_devnull_without_pipes(self, monkeypatch):
        captured: dict = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return _FakePopen()

        monkeypatch.setattr(adb_runner.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(adb_runner, "_server_ready", False)

        assert adb_runner.ensure_adb_server("C:/fake/adb.exe") is True

        assert captured["cmd"] == ["C:/fake/adb.exe", "start-server"]
        assert captured["kwargs"]["stdout"] is subprocess.DEVNULL
        assert captured["kwargs"]["stderr"] is subprocess.DEVNULL
        assert captured["kwargs"]["stdin"] is subprocess.DEVNULL


class TestRunAdbCommandPrewarm:
    """预热时机与缓存失效。"""

    def _patch(self, monkeypatch, warmed: list, commands: list) -> None:
        """把预热与真正执行都替换成记录器。

        Args:
            monkeypatch: pytest 打桩工具。
            warmed: 接收预热时 adb 路径的列表。
            commands: 接收实际命令的列表。

        Returns:
            None
        """

        def fake_ensure(adb_path, timeout=adb_runner.ADB_SERVER_START_TIMEOUT):
            warmed.append(adb_path)
            return True

        def fake_run(cmd, timeout=adb_runner.DEFAULT_ADB_TIMEOUT):
            commands.append(tuple(cmd))
            return process_utils.CommandResult(
                command=tuple(cmd), returncode=0, stdout=b"", stderr=b""
            )

        monkeypatch.setattr(adb_runner, "_server_ready", False)
        monkeypatch.setattr(adb_runner, "ensure_adb_server", fake_ensure)
        monkeypatch.setattr(adb_runner, "run_command", fake_run)

    def test_warms_server_once_before_first_command(self, monkeypatch):
        """连续两条 adb 命令只预热一次。"""
        warmed: list = []
        commands: list = []
        self._patch(monkeypatch, warmed, commands)
        adb = "C:/fake/adb.exe"

        adb_runner.run_adb_command([adb, "devices"])
        adb_runner.run_adb_command([adb, "connect", "127.0.0.1:5555"])

        assert warmed == [adb], "server 只应在首个 adb 命令前预热一次"
        assert commands == [(adb, "devices"), (adb, "connect", "127.0.0.1:5555")]

    def test_kill_server_invalidates_prewarm_cache(self, monkeypatch):
        """执行过 ``kill-server`` 之后必须重新预热。"""
        warmed: list = []
        commands: list = []
        self._patch(monkeypatch, warmed, commands)
        adb = "C:/fake/adb.exe"

        adb_runner.run_adb_command([adb, "devices"])
        adb_runner.run_adb_command([adb, "kill-server"])
        adb_runner.run_adb_command([adb, "devices"])

        assert warmed == [adb, adb], "kill-server 后下一次 adb 调用必须重新预热"
