"""回归测试：``wait_for_main`` 超时必须有「画面证据」。

背景（2026-10-07 06:05 那轮真机故障）：
    mage_alt 在 06:07:16 选完角色、点「进入游戏」后，``wait_for_main`` 一路等到
    150.3 秒超时（06:09:49），上层 ``main_wrapper`` 走「超时重启 1/3」，重开游戏后
    3 秒就进了主界面，最终 9/9 完成 —— 业务无损，但**脚本侧零画面信息**。

    姊妹函数 ``is_on_character_selection`` 早在 2026-10-01 就补上了「超时落错误
    截图 + 记录超时瞬间前台应用」，``wait_for_main`` 却漏了。结果这次只能靠
    BlueStacks 的 ``Player.log`` 反推（游戏进程一直活着、音频持续、无 guest 重启），
    无法直接回答"当时屏幕上是什么"。

    本文件锁死两条不变量：

    1. 超时抛 ``TimeoutError`` **之前**必须落一张 ``error_*.png``；
    2. 超时日志必须带上超时瞬间的前台应用（包名/Activity）。

    另外保留一条机制守护：单次 ``wait`` 不得吃掉整段超时 —— 否则又回到
    「阻塞期间不打心跳」的老病根（看门狗 180 秒误杀）。
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

#: 伪造的前台应用，用来证明它确实被写进了超时日志。
FAKE_FOREGROUND = "com.ms.ysjyzr/org.cocos2dx.javascript.AppActivity"


class _TimeoutAtEnd:
    """伪造 airtest 的 ``wait``：永远找不到目标，但每次调用只消耗极短时间。

    必须抛**生产同款异常类型**（``airtest.core.error.TargetNotFoundError``）——
    测试桩抛自定义异常会让「心跳/兜底是否可达」被错误地验证成真的。
    """

    def __init__(self) -> None:
        self.calls = 0
        self.timeouts: list[float | None] = []

    def __call__(self, *_args, **kwargs):
        self.calls += 1
        self.timeouts.append(kwargs.get("timeout"))
        time.sleep(0.02)
        raise TargetNotFoundError("模拟：主界面模板未命中")


def test_wait_for_main_timeout_saves_error_screenshot():
    """超时未回到主界面时必须留下画面证据。

    改前：超时分支只 ``logger.error`` + ``raise TimeoutError``，从不截图 ——
    2026-10-07 那次故障因此没有任何画面可查。改后：落一张错误截图。

    注意 ``create=True``：它让本用例在**尚未引入** ``save_error_screenshot`` 调用
    （甚至尚未引入该名字）的旧代码上也能跑起来，于是失败会落在**行为断言**
    （"一次都没调用"）而不是「打桩目标不存在」这类机械错误上 —— 后者虽然也算
    改前失败，但证明不了「行为确实缺失」，正是"假反证"的温床。
    """
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_account.wait", fake_wait):
        with patch("auto_dungeon_account.save_error_screenshot", create=True) as shot:
            with pytest.raises(TimeoutError):
                wait_for_main(timeout=1)

    shot.assert_called_once()
    operation = shot.call_args.args[0] if shot.call_args.args else ""
    assert (
        "main_screen" in operation
    ), f"错误截图的 operation 名应可定位到本次失败，实际为 {operation!r}"


def test_wait_for_main_timeout_logs_foreground_app(caplog: pytest.LogCaptureFixture):
    """超时日志必须写明超时瞬间的前台应用（包名/Activity）。

    改前：``describe_foreground()`` 根本没被调用，日志里只有一句
    「等待主界面超时（已等待 X 秒）」，无法判断是"画面没推进"还是"游戏被切走了"。

    同样用 ``create=True``，让改前的失败体现为**日志里没有前台信息**（行为缺失），
    而不是打桩目标不存在。
    """
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_account.wait", fake_wait):
        with patch("auto_dungeon_account.save_error_screenshot", return_value="", create=True):
            with patch(
                "auto_dungeon_account.describe_foreground",
                return_value=FAKE_FOREGROUND,
                create=True,
            ) as foreground:
                with caplog.at_level(logging.ERROR, logger="auto_dungeon_account"):
                    with pytest.raises(TimeoutError):
                        wait_for_main(timeout=1)

    foreground.assert_called_once()
    error_lines = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(
        FAKE_FOREGROUND in line for line in error_lines
    ), f"超时日志里没有前台应用信息，实际 ERROR 日志: {error_lines!r}"


def test_wait_for_main_success_produces_no_evidence(caplog: pytest.LogCaptureFixture):
    """命中主界面时立即返回，且**不**产生错误截图或前台探测（避免噪声）。"""
    with patch("auto_dungeon_account.wait", return_value=True):
        with patch("auto_dungeon_account.save_error_screenshot", create=True) as shot:
            with patch("auto_dungeon_account.describe_foreground", create=True) as foreground:
                wait_for_main(timeout=5)

    shot.assert_not_called()
    foreground.assert_not_called()


def test_wait_for_main_polls_in_slices_not_one_blocking_wait():
    """单次 ``wait`` 不得阻塞整段超时 —— 否则它中途没有机会打心跳。

    这是一条**机制层面**的守护：只要有人把实现改回
    ``wait(GIFTS_TEMPLATE, timeout=remaining)``（一次调用吃满整个超时），
    本用例立刻失败。
    """
    slice_seconds = 1.0  # 生产实现里每次轮询固定等 0.5 秒，取 1.0 作上界
    fake_wait = _TimeoutAtEnd()
    with patch("auto_dungeon_account.wait", fake_wait):
        with patch("auto_dungeon_account.save_error_screenshot", return_value=""):
            with pytest.raises(TimeoutError):
                wait_for_main(timeout=1)

    assert fake_wait.calls > 1, (
        f"整段超时只调用了一次 wait（timeout={fake_wait.timeouts}）——"
        "说明仍是整段阻塞，等待期间不可能有心跳。"
    )
    for called_timeout in fake_wait.timeouts:
        assert called_timeout is not None, "wait 必须以关键字 timeout 传入单次切片时长。"
        assert called_timeout <= slice_seconds, (
            f"单次 wait 的 timeout={called_timeout}s 超过轮询切片 {slice_seconds}s —— "
            "阻塞上限一旦逼近看门狗阈值（180s），正常等待就会被误杀。"
        )
