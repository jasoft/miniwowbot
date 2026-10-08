"""回归测试：选角色时「画面全黑」不等于「画面上没有这个文字」。

背景（2026-10-08 06:05 那轮真机故障，mage_alt）：
    06:06:46 core 判定「已在角色选择界面」，06:06:47 ``select_character`` 内再次确认，
    但紧接着的 3 次「查找职业: 法师」全部返回未找到，06:06:58 抛
    ``RuntimeError: 无法找到职业: 法师`` → 整个配置被 ``SystemExit(1)`` 中断 →
    编排器停/重启游戏重跑一轮（约 1 分钟）才恢复，最终 9/9 完成（业务无损）。

    三条独立证据指向"画面当时全黑"：
    1. 脚本自己落下的 ``error_select_character_*.png`` 离线像素分析：除顶部调试条外
       **99.99% 的像素是 RGB(0,0,0)**，灰度均值 0.18；
    2. 同一时刻的 airtest 模板匹配（``is_on_character_selection``）**命中**了
       「进入游戏」按钮 —— 说明画面是**在这几秒内**才变黑的，不是一直黑；
    3. ``Player.log`` 里同一窗口出现 ``SplitAdsExitComplete``（06:06:50.023）→
       ``PlaybackStopped``（06:06:52.688）→ ``hcallOnOrientationChangedClbk``
       转屏（06:06:55.020），即游戏正在切换场景（这一条是**伴随现象**，
       两个实例当天都有广告退出，因此只作旁证、不当首因）。

    旧实现把"读不到文字"一律当成"文字不存在"：固定重试 3 次 × 2 秒后就放弃并
    炸掉整个会话。本文件锁死新行为：**画面全黑时等画面恢复**，且等待有上限。

改前反证要点：桩必须用 ``create=True`` 打 ``screenshot_is_blank`` ——
否则在旧代码上会以 AttributeError（打桩目标不存在）这种**机械失败**结束，
证明不了"行为确实缺失"，属于"假反证"。
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import ExitStack
from typing import Any, Callable, Optional
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_dungeon_account import select_character  # noqa: E402

import auto_dungeon_account as _account  # noqa: E402

# 用 getattr 读取（而不是 from ... import）：这些常量是随本次修复一起新增的，
# 直接 import 会让本文件在**旧代码**上以 ImportError 收集失败 —— 那是"打桩目标
# 不存在"式的**机械失败**，证明不了"行为确实缺失"，属于"假反证"。
# 走 getattr 后旧代码也能正常收集，失败会落在真正的**行为断言**上。
CHARACTER_FIND_RETRIES = getattr(_account, "CHARACTER_FIND_RETRIES", 3)
CHARACTER_BLANK_SCREEN_MAX_RETRIES = getattr(_account, "CHARACTER_BLANK_SCREEN_MAX_RETRIES", 15)
CHARACTER_RETRY_INTERVAL_SECONDS = getattr(_account, "CHARACTER_RETRY_INTERVAL_SECONDS", 2.0)

#: 编排器的会话日志停滞阈值（``cron_run_all_dungeons.LOG_IDLE_TIMEOUT_SECONDS``）。
#: 本文件不 import 它（会拉起整个编排器依赖），直接锁死这个业务常量。
WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS = 180


def _patched_environment(
    *,
    find_text_side_effect: Callable[..., Any],
    blank_side_effect: Callable[..., bool],
    is_on_selection: bool = True,
) -> ExitStack:
    """构造 ``select_character`` 的可控环境（全部外部副作用打桩）。

    Args:
        find_text_side_effect: ``find_text`` 的返回值/副作用。
        blank_side_effect: ``screenshot_is_blank`` 的返回值/副作用。
        is_on_selection: ``is_on_character_selection`` 的返回值。

    Returns:
        ExitStack: 已 enter 的上下文栈，调用方用 ``with`` 包住调用即可。
    """
    stack = ExitStack()
    container = stack.enter_context(patch("auto_dungeon_account.get_container")).return_value
    container.error_dialog_monitor = None

    stack.enter_context(
        patch("auto_dungeon_account.is_on_character_selection", return_value=is_on_selection)
    )
    stack.enter_context(patch("auto_dungeon_account.find_text", side_effect=find_text_side_effect))
    stack.enter_context(
        patch(
            "auto_dungeon_account.screenshot_is_blank", side_effect=blank_side_effect, create=True
        )
    )
    stack.enter_context(patch("auto_dungeon_account.sleep"))
    stack.enter_context(patch("auto_dungeon_account.touch"))
    stack.enter_context(patch("auto_dungeon_account.find_text_and_click"))
    stack.enter_context(patch("auto_dungeon_account.wait_for_main"))
    return stack


def test_select_character_recovers_after_blank_screen_window():
    """画面黑屏窗口过去后必须能选到角色，而不是炸掉整个配置。

    改前：``find_text`` 固定只重试 3 次（各等 2 秒），第 3 次失败即
    ``raise RuntimeError`` → 整个配置被中断重跑一轮。
    改后：识别出"截图全黑 = 画面还没渲染出来"，等画面恢复后继续查找。
    """
    find_calls = {"n": 0}
    blank_calls = {"n": 0}

    def fake_find_text(*_args, **_kwargs) -> Optional[dict]:
        find_calls["n"] += 1
        # 前 4 次：画面还在黑屏期，OCR 什么也读不到
        if find_calls["n"] <= 4:
            return None
        return {"found": True, "center": (360, 700)}

    def fake_screenshot_is_blank(*_args, **_kwargs) -> bool:
        blank_calls["n"] += 1
        return blank_calls["n"] <= 4  # 第 5 次探测时画面已恢复

    with _patched_environment(
        find_text_side_effect=fake_find_text,
        blank_side_effect=fake_screenshot_is_blank,
    ):
        select_character("法师")  # 不应抛异常

    assert find_calls["n"] >= 5, (
        f"画面恢复后应继续查找直到命中，实际只调用了 {find_calls['n']} 次 "
        f"—— 说明仍按「重试 {CHARACTER_FIND_RETRIES} 次就放弃」处理"
    )
    assert blank_calls["n"] >= 4, "黑屏期间应持续探测画面是否恢复"


def test_select_character_still_fails_fast_when_text_really_absent():
    """画面**正常**却找不到文字时，仍应在 3 次后放弃 —— 别把真故障拖成超长等待。

    这条守住"放宽"的边界：黑屏走独立预算，正常失败仍是 3 次。
    """
    find_calls = {"n": 0}

    def fake_find_text(*_args, **_kwargs) -> Optional[dict]:
        find_calls["n"] += 1
        return None

    with _patched_environment(
        find_text_side_effect=fake_find_text,
        blank_side_effect=lambda *_a, **_k: False,
    ):
        with pytest.raises(RuntimeError, match="无法找到职业"):
            select_character("法师")

    assert (
        find_calls["n"] == CHARACTER_FIND_RETRIES
    ), f"画面正常时应在 {CHARACTER_FIND_RETRIES} 次后放弃，实际调用 {find_calls['n']} 次"


def test_blank_screen_waiting_is_bounded():
    """画面一直全黑也不能无限等：必须有上限并最终放弃。"""
    find_calls = {"n": 0}

    def fake_find_text(*_args, **_kwargs):
        find_calls["n"] += 1
        return None

    with _patched_environment(
        find_text_side_effect=fake_find_text,
        blank_side_effect=lambda *_a, **_k: True,
    ):
        with pytest.raises(RuntimeError, match="无法找到职业"):
            select_character("法师")

    assert (
        find_calls["n"] <= CHARACTER_BLANK_SCREEN_MAX_RETRIES + 1
    ), f"全黑等待次数超过上限（实际 {find_calls['n']} 次）"
    assert (
        find_calls["n"] > CHARACTER_FIND_RETRIES
    ), "全黑时应当比普通失败多等若干次，实际没有延长等待"


def test_blank_screen_waiting_budget_below_watchdog_threshold(caplog: pytest.LogCaptureFixture):
    """全黑等待的总时长必须显著小于看门狗阈值，且期间日志不能静默。

    编排器把会话日志 ``(mtime, size)`` 当作"会话是否还活着"的唯一信号，
    超过 180 秒无更新就判定僵死、杀会话并重启模拟器（代价远大于本函数自己放弃）。
    """
    total_seconds = (CHARACTER_BLANK_SCREEN_MAX_RETRIES + CHARACTER_FIND_RETRIES) * (
        CHARACTER_RETRY_INTERVAL_SECONDS
    )
    assert total_seconds < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"选角色最坏耗时 {total_seconds}s 逼近/超过看门狗阈值 "
        f"{WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s —— 必然被误杀"
    )

    with _patched_environment(
        find_text_side_effect=lambda *_a, **_k: None,
        blank_side_effect=lambda *_a, **_k: True,
    ):
        with caplog.at_level(logging.WARNING, logger="auto_dungeon_account"):
            with pytest.raises(RuntimeError):
                select_character("法师")

    blank_warnings = [r.getMessage() for r in caplog.records if "全黑" in r.getMessage()]
    assert blank_warnings, "黑屏等待期间必须有可读的 WARNING 日志（否则就是静默阻塞）"
