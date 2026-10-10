"""回归测试：等待角色选择界面时必须感知「游戏被顶到后台」并提前结束等待。

背景（2026-10-10 06:05~06:35 真机故障，mage_alt / Pie64_1）：
    游戏进程每次都被正常拉起（``Player.log`` 里 ``com.ms.ysjyzr`` 的 socket 一次不落），
    但顶层 Activity 反复被 BlueStacks launcher 夺回 —— 该实例当天 **20 次**前台切换
    （对照 main 实例仅 2 次）、**6 次** SystemUI 重启（对照 main 0 次），且每次 launcher
    前台的 ``callingPackage`` 都是预装的应用宝 ``com.tencent.android.qqdownloader``。

    而 ``is_on_character_selection`` 只会一路**盲等到 180 秒超时**：当天 9 次超时白耗
    约 27 分钟，并把一次**实例异常**放大成
    「3 次配置重试 × 3 次应用重启 = 9 条告警」，直到编排器重启该实例才在 1 分钟内恢复。

本测试锁死四条不变量（改前必然 FAIL）：
    1. **行为**：见过游戏在前台、之后连续 N 次明确不在前台 → 抛
       :class:`GameNotForegroundError`，并落错误截图；
    2. **安全（未见过游戏不算数）**：``start_app`` 后头几秒顶层 Activity 还是 launcher，
       此时判「不在前台」会误杀**正常启动** —— 必须等真正见过游戏在前台；
    3. **安全（探测失败不计数）**：``is_game_foreground()`` 返回 ``None``（无设备 /
       探测抖动）不得触发任何提前失败，宁可按老行为等满超时；
    4. **机制**：提前失败的预算（检查间隔 × 连续次数）必须远小于 180 秒的等待上限，
       否则「提前结束」没有意义。
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import List, Optional, Sequence, Tuple
from unittest.mock import patch

import pytest
from airtest.core.error import TargetNotFoundError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon_navigation  # noqa: E402
from auto_dungeon_navigation import (  # noqa: E402
    GameNotForegroundError,
    is_on_character_selection,
)

# 与 auto_dungeon_core.CHARACTER_SELECTION_WAIT_SECONDS 保持一致；手动复制是刻意的 ——
# 若常量被误改，本测试要能立刻失败，而不是跟着一起漂移。
CHARACTER_SELECTION_WAIT_SECONDS = 180

#: 压缩后的前台探测间隔，用来把"等 20 秒"缩进测试的毫秒级。
_TEST_CHECK_INTERVAL_SECONDS = 0.02


class _NeverFoundWait:
    """伪造 airtest 的 ``wait``：永远找不到目标，但每次只消耗极短时间。

    抛的必须是**生产同款异常类型** ``airtest.core.error.TargetNotFoundError``
    （2026-10-01 的教训：桩抛自定义异常会让"加了心跳"的假修复测成绿的）。
    """

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_args, **kwargs):
        self.calls += 1
        time.sleep(0.02)
        raise TargetNotFoundError("模拟：目标模板未命中")


def _run(
    states: Sequence[Optional[bool]],
    *,
    timeout: float,
) -> Tuple[_NeverFoundWait, object]:
    """跑一次 ``is_on_character_selection``，按序列伪造前台探测结果。

    Args:
        states: 依次返回的前台探测结果（``True``/``False``/``None``）；
            用尽后固定返回最后一个值。
        timeout: 传给被测函数的等待上限（配合缩小的检查间隔使用）。

    Returns:
        Tuple[_NeverFoundWait, object]: ``(伪造的 wait, save_error_screenshot 的 mock)``。
    """
    fake_wait = _NeverFoundWait()
    seq: List[Optional[bool]] = list(states)

    def _fake_foreground(*_args, **_kwargs):
        if len(seq) > 1:
            return seq.pop(0)
        return seq[0]

    with patch("auto_dungeon_navigation.wait", fake_wait):
        with patch("auto_dungeon_navigation.is_game_foreground", side_effect=_fake_foreground):
            with patch("auto_dungeon_navigation.describe_foreground", return_value="com.test/Home"):
                with patch(
                    "auto_dungeon_navigation.save_error_screenshot", return_value="/tmp/fake.png"
                ) as shot:
                    with patch(
                        "auto_dungeon_navigation.CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS",
                        _TEST_CHECK_INTERVAL_SECONDS,
                        create=True,
                    ):
                        with pytest.raises(GameNotForegroundError):
                            is_on_character_selection(timeout=timeout)
    return fake_wait, shot


def _run_expecting_return(
    states: Sequence[Optional[bool]],
    *,
    timeout: float,
) -> Tuple[_NeverFoundWait, object]:
    """同 :func:`_run`，但期望**正常返回**（不抛 GameNotForegroundError）。"""
    fake_wait = _NeverFoundWait()
    seq: List[Optional[bool]] = list(states)

    def _fake_foreground(*_args, **_kwargs):
        if len(seq) > 1:
            return seq.pop(0)
        return seq[0]

    with patch("auto_dungeon_navigation.wait", fake_wait):
        with patch("auto_dungeon_navigation.is_game_foreground", side_effect=_fake_foreground):
            with patch("auto_dungeon_navigation.describe_foreground", return_value="com.test/Home"):
                with patch(
                    "auto_dungeon_navigation.save_error_screenshot", return_value="/tmp/fake.png"
                ) as shot:
                    with patch(
                        "auto_dungeon_navigation.CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS",
                        _TEST_CHECK_INTERVAL_SECONDS,
                        create=True,
                    ):
                        result = is_on_character_selection(timeout=timeout)
    assert result is False, "始终未命中模板时应返回 False"
    return fake_wait, shot


def _screenshot_operation(shot) -> str:
    """取出 ``save_error_screenshot`` 被调用时传入的 operation 名。"""
    args = getattr(shot.call_args, "args", ())
    return args[0] if args else ""


def test_raises_when_game_seen_then_pushed_to_background():
    """见过游戏在前台、之后连续不在前台 → 提前抛 GameNotForegroundError（改前：等满超时）。"""
    start = time.time()
    fake_wait, shot = _run([True, False], timeout=5)
    elapsed = time.time() - start

    assert elapsed < 10, (
        f"提前失败应在数秒内完成，实际耗时 {elapsed:.1f} 秒 —— "
        "说明仍在盲等（改前本用例会因为不抛异常而 FAIL）。"
    )
    assert (
        fake_wait.calls < 100
    ), f"提前失败前 wait 被调用 {fake_wait.calls} 次 —— 次数过多说明没有提前退出。"
    shot.assert_called_once()
    operation = _screenshot_operation(shot)
    assert (
        "character_selection" in operation
    ), f"提前失败也应留下可定位的错误截图，实际 operation={operation!r}"


def test_early_failure_message_names_foreground():
    """提前失败的日志必须写清「游戏被顶到后台」和当前前台，便于事后定位。"""
    logger = logging.getLogger("auto_dungeon_navigation")
    records: List[str] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = _Collector(level=logging.INFO)
    logger.addHandler(handler)
    try:
        _run([True, False], timeout=5)
    finally:
        logger.removeHandler(handler)

    assert any("顶到后台" in message for message in records), (
        "提前失败必须打出「游戏已被顶到后台」的日志，否则事后无法区分"
        "「实例异常」与「就是没进界面」。"
    )


def test_no_early_failure_when_probe_is_unavailable():
    """探测返回 None（无设备 / get_top_activity 抖动）不得触发提前失败。"""
    fake_wait, shot = _run_expecting_return([None], timeout=1)

    assert fake_wait.calls > 1, "应正常轮询直到超时"
    operation = _screenshot_operation(shot)
    assert (
        operation == "character_selection_timeout"
    ), f"探测不可用时必须走原超时路径，实际 operation={operation!r}"


def test_no_early_failure_when_game_never_seen_in_foreground():
    """从没见游戏进过前台（如 start_app 后 launcher 仍在前台）不得提前失败。

    这是防止把「正常但较慢的冷启动」误杀的**安全闸门**：真机实测 start_app 后约
    5~6 秒游戏才把 Activity 显示到前台，期间顶层 Activity 就是 launcher。
    """
    fake_wait, shot = _run_expecting_return([False], timeout=1)

    assert fake_wait.calls > 1, "应正常轮询直到超时"
    operation = _screenshot_operation(shot)
    assert (
        operation == "character_selection_timeout"
    ), f"未见过游戏在前台时必须按老行为等满超时，实际 operation={operation!r}"


def test_returns_true_and_skips_probe_when_template_matches():
    """命中模板时立即返回 True，不产生错误截图、也不做前台探测。"""
    with patch("auto_dungeon_navigation.wait", return_value=True):
        with patch("auto_dungeon_navigation.is_game_foreground") as probe:
            with patch("auto_dungeon_navigation.save_error_screenshot") as shot:
                assert is_on_character_selection(timeout=5) is True
    probe.assert_not_called()
    shot.assert_not_called()


def test_early_failure_budget_is_far_below_wait_timeout():
    """提前失败的预算（检查间隔 × 连续次数）必须远小于 180 秒的等待上限。"""
    interval = getattr(
        auto_dungeon_navigation, "CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS", None
    )
    limit = getattr(auto_dungeon_navigation, "CHARACTER_SELECTION_FOREGROUND_LOST_LIMIT", None)

    assert interval is not None, "缺少 CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS 常量。"
    assert limit is not None, "缺少 CHARACTER_SELECTION_FOREGROUND_LOST_LIMIT 常量。"
    assert (
        isinstance(limit, int) and limit >= 2
    ), f"连续次数至少为 2（单次判定会被画面过渡误杀），实际 {limit!r}"

    budget = interval * limit
    assert budget <= 30, (
        f"提前失败预算 {interval}s × {limit} = {budget}s 偏大 —— "
        "必须远小于等待上限，否则「提前结束」没有意义。"
    )
    assert (
        budget < CHARACTER_SELECTION_WAIT_SECONDS
    ), f"提前失败预算 {budget}s 必须小于等待上限 {CHARACTER_SELECTION_WAIT_SECONDS}s。"
