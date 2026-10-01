"""回归测试：等待类函数必须产生心跳日志，且上限低于看门狗阈值。

背景（2026-09-30 06:05 那轮真机故障）：
    ``wait_for_main`` 直接调用 airtest 的 ``wait()`` 阻塞最长 300 秒且中途不打任何
    日志。而编排器 ``cron_run_all_dungeons`` 把会话日志的 ``(mtime, size)`` 当作
    「会话是否还活着」的唯一信号，超过 ``LOG_IDLE_TIMEOUT_SECONDS``(180 秒) 无更新
    就判定僵死，杀掉会话并重启模拟器。于是 **timeout(300) > 阈值(180)** 这个组合
    必然误杀：mage_alt 在 06:06:57 进入等待，06:09:58 被看门狗杀掉重启，白扔约
    4 分钟。同一时刻 main 只等了 23 秒就命中，故未触发。

本测试锁死两条不变量：
    1. 等待期间按心跳间隔持续写日志（否则看门狗看到的是"零增长文件"）；
    2. 默认超时严格小于看门狗阈值（否则"真卡住"时先被外部杀掉，代价更重）。

补充（2026-10-01 06:05 那轮真机故障）：
    ``is_on_character_selection`` 虽然"加了心跳"，但心跳代码写在了**不可达位置** ——
    它把整段超时一次性交给 ``wait(timeout=remaining)``，而 airtest 的 ``wait`` 在整段
    内找不到目标时抛的是 **``airtest.core.error.TargetNotFoundError``**，代码里
    ``except TargetNotFoundError: break`` 直接跳出循环，心跳永远执行不到。
    实测 06:06:22.264 → 06:09:22.335 静默 **180.07 秒**，与看门狗阈值 180s 擦边
    （侥幸未触发）；当天会话日志里 ``等待角色选择界面中...`` 出现 **0 次**。

    09-30 那版测试之所以"通过"，是因为测试桩抛的是**自定义内部异常**
    （落进 ``except Exception`` 分支，能走到心跳），而生产抛的是 airtest 的真异常。
    ⇒ **桩的异常类型必须与生产一致，否则测出来的是假绿。** 本文件据此改用真异常。
"""

from __future__ import annotations

import logging
import os
import sys
import time
from unittest.mock import patch

import pytest
from airtest.core.error import TargetNotFoundError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_dungeon_account import wait_for_main  # noqa: E402
from auto_dungeon_navigation import is_on_character_selection  # noqa: E402

import auto_dungeon_account  # noqa: E402
import auto_dungeon_navigation  # noqa: E402

# 与编排器保持一致；手动复制是为了让本测试在常量被误改时立刻失败（引入导入反而会
# 跟着一起漂移，测不出问题）。
WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS = 180


class _TimeoutAtEnd:
    """伪造 airtest 的 ``wait``：永远找不到目标，但每次调用只消耗极短时间。

    真实 ``wait`` 在整段 ``timeout`` 内找不到目标时抛的是 **airtest 自己的**
    ``TargetNotFoundError``（``airtest.core.error``）。这里必须抛**同一个类型** ——
    2026-09-30 那版桩抛的是自定义内部类，落进 ``except Exception`` 分支，把
    "心跳有效"错误地验证成了真的；真机上走的是 ``except TargetNotFoundError: break``，
    心跳从未执行。**桩的异常类型和生产不一致，就是一个假测试。**

    每次调用压缩到 ~0.05 秒，从而在一秒钟内模拟出"长时间等待"。
    """

    def __init__(self) -> None:
        self.calls = 0
        self.timeouts: list[float | None] = []

    def __call__(self, *_args, **kwargs):
        self.calls += 1
        self.timeouts.append(kwargs.get("timeout"))
        time.sleep(0.05)
        raise TargetNotFoundError("模拟：目标模板未命中")


def _heartbeat_lines(records: list[str], keyword: str) -> list[str]:
    """筛出心跳日志行。"""
    return [line for line in records if keyword in line and "已等待" in line]


def test_wait_for_main_emits_heartbeat_while_waiting(caplog: pytest.LogCaptureFixture):
    """等待期间必须持续输出心跳日志（改前：0 条，静默阻塞）。"""
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_account.wait", fake_wait):
        with caplog.at_level(logging.INFO, logger="auto_dungeon_account"):
            with pytest.raises(TimeoutError):
                # 超时设短，靠缩小心跳间隔把"应产生多条心跳"压缩进测试时间。
                with patch("auto_dungeon_account.WAIT_FOR_MAIN_HEARTBEAT_SECONDS", 0.1):
                    wait_for_main(timeout=1)

    heartbeats = _heartbeat_lines([r.getMessage() for r in caplog.records], "等待主界面中")
    assert heartbeats, (
        "等待期间没有任何心跳日志 —— 看门狗会把会话日志 180 秒不动判成僵死并杀掉重启。"
        f"（wait 被调用 {fake_wait.calls} 次）"
    )


def test_wait_for_main_default_timeout_below_watchdog_threshold():
    """默认超时必须严格小于看门狗阈值，否则真卡住时会先被外部杀掉。"""
    default_timeout = getattr(auto_dungeon_account, "WAIT_FOR_MAIN_DEFAULT_TIMEOUT", None)
    assert (
        default_timeout is not None
    ), "缺少 WAIT_FOR_MAIN_DEFAULT_TIMEOUT 常量 —— 无法证明超时已收敛到看门狗阈值以下。"
    heartbeat = getattr(auto_dungeon_account, "WAIT_FOR_MAIN_HEARTBEAT_SECONDS", None)
    assert heartbeat is not None, "缺少 WAIT_FOR_MAIN_HEARTBEAT_SECONDS 常量。"
    assert default_timeout < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"wait_for_main 默认超时 {default_timeout}s 必须小于看门狗"
        f"阈值 {WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s，否则卡满时会先被误杀（并重启模拟器）。"
    )
    assert heartbeat < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"心跳间隔 {heartbeat}s 必须小于看门狗阈值 "
        f"{WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s，否则心跳还没打就被判僵死。"
    )


def test_wait_for_main_default_param_below_watchdog_threshold():
    """``wait_for_main`` 的默认形参本身也必须小于看门狗阈值。

    改前默认形参是 ``timeout: int = 300``，直接违反该不变量。
    """
    import inspect

    sig = inspect.signature(auto_dungeon_account.wait_for_main)
    default = sig.parameters["timeout"].default
    assert isinstance(default, int), f"timeout 默认值应为 int，实际 {default!r}"
    assert default < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"wait_for_main 默认 timeout={default}s 不小于看门狗阈值 "
        f"{WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s —— 卡满时必然被看门狗误杀。"
    )


def test_wait_for_main_returns_immediately_when_found():
    """命中模板时应立即返回，且不产生超时。"""
    with patch("auto_dungeon_account.wait", return_value=True):
        wait_for_main(timeout=5)


def test_character_selection_heartbeat_below_watchdog_threshold():
    """角色选择界面的心跳间隔同样必须小于看门狗阈值。"""
    heartbeat = getattr(auto_dungeon_navigation, "CHARACTER_SELECTION_HEARTBEAT_SECONDS", None)
    assert heartbeat is not None, "缺少 CHARACTER_SELECTION_HEARTBEAT_SECONDS 常量。"
    assert heartbeat < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"心跳间隔 {heartbeat}s 必须小于看门狗阈值 " f"{WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s。"
    )


def test_character_selection_emits_heartbeat_while_waiting(caplog: pytest.LogCaptureFixture):
    """等待角色选择界面期间也必须持续输出心跳日志。

    改前（2026-10-01 之前）：桩抛真 ``TargetNotFoundError`` → 代码 ``break`` 跳出循环
    → 心跳 0 条 → 本用例 FAIL。改后（分段轮询）：心跳按时落盘 → PASS。
    """
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_navigation.wait", fake_wait):
        with patch("auto_dungeon_navigation.save_error_screenshot", return_value=""):
            with caplog.at_level(logging.INFO, logger="auto_dungeon_navigation"):
                with patch("auto_dungeon_navigation.CHARACTER_SELECTION_HEARTBEAT_SECONDS", 0.1):
                    result = is_on_character_selection(timeout=1)

    assert result is False, "始终未命中模板时应返回 False"
    heartbeats = _heartbeat_lines([r.getMessage() for r in caplog.records], "等待角色选择界面中")
    assert heartbeats, (
        "等待角色选择界面期间没有任何心跳日志 —— 看门狗会把日志 180 秒不动的会话判成僵死。"
        f"（wait 被调用 {fake_wait.calls} 次）"
    )


def test_character_selection_polls_in_slices_not_one_blocking_wait():
    """单次 ``wait`` 不得阻塞整段超时 —— 否则它中途没有机会打心跳。

    这是一条**机制层面**的守护：只要有人把实现改回
    ``wait(timeout=remaining)``（一次调用吃满整个超时），本用例立刻失败。
    """
    slice_seconds = getattr(auto_dungeon_navigation, "CHARACTER_SELECTION_POLL_SLICE_SECONDS", None)
    assert slice_seconds is not None, (
        "缺少 CHARACTER_SELECTION_POLL_SLICE_SECONDS 常量 —— "
        "无法证明等待已被切成小片以让心跳落盘。"
    )
    assert slice_seconds < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"轮询切片 {slice_seconds}s 必须小于看门狗阈值 "
        f"{WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s，否则单片就足以被判僵死。"
    )

    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_navigation.wait", fake_wait):
        with patch("auto_dungeon_navigation.save_error_screenshot", return_value=""):
            is_on_character_selection(timeout=1)

    assert fake_wait.calls > 1, (
        f"整段超时只调用了一次 wait（timeout={fake_wait.timeouts}）——"
        "说明仍是整段阻塞，等待期间不可能有心跳。"
    )
    for called_timeout in fake_wait.timeouts:
        assert called_timeout is not None, "wait 必须以关键字 timeout 传入单次切片时长。"
        assert called_timeout <= slice_seconds + 1e-6, (
            f"单次 wait 的 timeout={called_timeout}s 超过轮询切片 {slice_seconds}s —— "
            "阻塞上限一旦逼近看门狗阈值，正常等待就会被误杀。"
        )


def test_character_selection_saves_screenshot_on_timeout():
    """超时未进界面时必须留下画面证据。

    2026-10-01 那次故障因为"没有任何截图"，只能靠模拟器日志反推，无法直接看到
    游戏卡在哪个画面。此后超时一律落一张 error 截图。
    """
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_navigation.wait", fake_wait):
        with patch(
            "auto_dungeon_navigation.save_error_screenshot", return_value="/tmp/fake.png"
        ) as shot:
            result = is_on_character_selection(timeout=1)

    assert result is False
    shot.assert_called_once()
    operation = shot.call_args.args[0] if shot.call_args.args else ""
    assert (
        "character_selection" in operation
    ), f"错误截图的 operation 名应可定位到本次失败，实际为 {operation!r}"


def test_character_selection_returns_true_without_screenshot_when_found():
    """命中模板时立即返回 True，且不产生错误截图。"""
    with patch("auto_dungeon_navigation.wait", return_value=True):
        with patch("auto_dungeon_navigation.save_error_screenshot") as shot:
            assert is_on_character_selection(timeout=5) is True
    shot.assert_not_called()
