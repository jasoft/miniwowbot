# -*- encoding=utf8 -*-
"""子进程管道死锁回归测试。

背景（真机实测，2026-09-27 06:05）：

Windows 上 ``subprocess.run(..., capture_output=True, timeout=N)`` 超时后，
CPython 会在 ``_mswindows`` 分支里**再次调用无超时的** ``communicate()``。
若子进程派生出的孙进程继承了本次调用那对 stdout/stderr 管道句柄的写端，
``communicate()`` 永远等不到 EOF —— ``timeout`` 形同虚设，调用方被无限期挂住。

当时会话 mage_alt 卡在 ``adb devices`` 上 **194 秒零日志**：adb 客户端在
没有 server 时拉起的常驻 ``adb server`` 继承了管道句柄；而 0.8 秒后启动的 main
会话复用了已存在的 server，1.6 秒就返回 —— 只有「需要派生 server 的那一次」死锁。
后果是编排器看门狗按「180 秒无日志」判它为僵死，杀掉会话并重启了模拟器。

本文件只依赖**改动前就存在**的入口（``emulator_control._run_list_cmd``），
因此可以在修复前后分别运行，真实体现「改前失败、改后通过」。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

import emulator_control

#: 等待工作线程结束的上限（秒）。必须显著大于被测命令的 timeout，
#: 又要小到不会拖慢测试 —— 死锁时线程会永远活着，靠它把「挂死」变成「断言失败」。
WATCHDOG_JOIN_TIMEOUT = 12.0

#: 孙进程保持存活的时长（秒），足以覆盖整个断言窗口。
_GRANDCHILD_LIFETIME = 30

_STUB_SOURCE = '''
"""测试桩：模拟 adb 派生一个持有调用者管道句柄的常驻孙进程。

`child_lifetime=0` 时本进程立即退出（等价于 adb client 交给 server 后退出）。
"""

import subprocess
import sys
import time

if len(sys.argv) > 1 and sys.argv[1] == "start-server":
    sys.exit(0)

# close_fds=False → bInheritHandles=TRUE：孙进程拿到调用者的 stdout/stderr 管道写端。
# 这正是 adb（C 实现）拉起常驻 adb server 时发生的事，也是死锁的成因。
subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep({lifetime})"],
    close_fds=False,
)

if {child_lifetime}:
    time.sleep({child_lifetime})

print("stub: 已派生持有管道的孙进程")
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
            _STUB_SOURCE.format(lifetime=_GRANDCHILD_LIFETIME, child_lifetime=child_lifetime)
        ).strip(),
        encoding="utf-8",
    )
    return str(stub)


def _run_with_watchdog(target) -> tuple[bool, float]:
    """在守护线程里执行 ``target``，返回它是否在限期内结束。

    死锁时工作线程会永远活着，靠 join 超时把「挂死」转换成一次干净的断言失败，
    而不是让整个 pytest 卡住。

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


@pytest.mark.skipif(os.name != "nt", reason="管道句柄继承导致的死锁是 Windows 特有行为")
class TestRunListCmdDoesNotHang:
    """``emulator_control._run_list_cmd`` 必须真的守时。"""

    def test_returns_even_if_child_spawns_pipe_holding_grandchild(self, tmp_path: Path):
        """子进程派生的孙进程抢走管道句柄时，命令仍须正常返回。"""
        stub = _write_pipe_holding_stub(tmp_path)
        logger = logging.getLogger("tests.test_adb_pipe_deadlock")
        result: dict = {}

        def call() -> None:
            result["ok"] = emulator_control._run_list_cmd(
                [sys.executable, stub],
                logger,
                "假 adb 命令",
                timeout=2,
                allow_failure=True,
            )

        finished, elapsed = _run_with_watchdog(call)

        assert finished, (
            f"命令被孙进程继承的管道句柄挂住（>{WATCHDOG_JOIN_TIMEOUT:.0f}s 未返回）—— "
            "超时保护失效，这正是 2026-09-27 06:05 mage_alt 卡死 194 秒的成因"
        )
        assert elapsed < WATCHDOG_JOIN_TIMEOUT
        assert result["ok"] is True, "命令正常退出应判定为成功（输出仍要能拿到）"

    def test_legacy_subprocess_run_pattern_still_hangs(self, tmp_path: Path):
        """反证：旧的 ``subprocess.run`` 写法在同一构造下确实不守时。

        这条断言如果哪天失败，说明平台行为已变（``subprocess.run`` 不再二次阻塞），
        届时可以简化 ``process_utils.run_command`` 的封装。
        """
        stub = _write_pipe_holding_stub(tmp_path)
        state: dict = {}

        def legacy_call() -> None:
            try:
                subprocess.run([sys.executable, stub], capture_output=True, timeout=2)
                state["result"] = "returned"
            except subprocess.TimeoutExpired:
                state["result"] = "timeout"
            except BaseException as exc:  # noqa: BLE001 - 仅用于记录，避免线程静默死亡
                state["result"] = f"exc:{type(exc).__name__}"

        finished, _ = _run_with_watchdog(legacy_call)

        assert not finished and not state, (
            "本机未复现旧的管道死锁（subprocess.run 已守时）；"
            "若平台行为改变，可移除 process_utils 中的超时兜底封装"
        )
