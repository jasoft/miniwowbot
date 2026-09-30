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
"""

from __future__ import annotations

import logging
import os
import sys
import time
from unittest.mock import patch

import pytest

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

    真实 ``wait`` 会一次性阻塞 ``timeout`` 秒；这里把每次调用压缩到 ~0.05 秒并抛
    ``TargetNotFoundError`` 的等价异常，从而在一秒钟内模拟出"长时间等待"。
    """

    class TargetNotFoundError(Exception):
        """airtest ``TargetNotFoundError`` 的替身。"""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        time.sleep(0.05)
        raise self.TargetNotFoundError("模拟：目标模板未命中")


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
    """等待角色选择界面期间也必须持续输出心跳日志。"""
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_navigation.wait", fake_wait):
        with caplog.at_level(logging.INFO, logger="auto_dungeon_navigation"):
            with patch("auto_dungeon_navigation.CHARACTER_SELECTION_HEARTBEAT_SECONDS", 0.1):
                result = is_on_character_selection(timeout=1)

    assert result is False, "始终未命中模板时应返回 False"
    heartbeats = _heartbeat_lines([r.getMessage() for r in caplog.records], "等待角色选择界面中")
    assert heartbeats, (
        "等待角色选择界面期间没有任何心跳日志 —— 看门狗会误判僵死。"
        f"（wait 被调用 {fake_wait.calls} 次）"
    )
