"""回归测试：``auto_combat`` 战斗超时必须有「画面证据」。

背景（2026-10-26 06:05 那轮真机故障）：
    法师配置的「深渊圣所」（06:10:56 起）与「迷雾林地」（06:21:54 起）两次把战斗循环
    跑满 180 秒超时，各自触发一次「超时重启 1/3」「2/3」，白耗约 1.6 分钟并误发 2 条
    Pushover。业务结果无损（mage 11/11、warrior 11/11），但**脚本侧零画面信息**：

    * 超时日志只有一句「自动战斗超时（180秒），抛出异常」，没有实等秒数、
      没有前台应用、没有内置自动战斗状态；
    * ``log/error_*.png`` 一张都没有（``fd '^error_' log`` 为空）；
    * ``auto_dungeon_core`` 虽然调了 ``airtest_log(..., snapshot=True)``，
      但项目没有生成 airtest 报告，快照并不落盘 —— ``find log`` 在同一时间窗内零新增文件。

    结果只能靠 ``Player.log`` 反推（游戏进程全程存活、当天无 guest 重启、无应用宝抢前台），
    无法回答「那 180 秒屏幕上到底是什么」，根因至今未确证。

    姊妹路径 ``wait_for_main``（2026-10-07 ``4437f9d``）与 ``is_on_character_selection``
    （2026-10-08 ``42b0994``）早已补上「超时落错误截图 + 记录超时瞬间前台应用」，
    ``auto_combat`` 是**同一族缺陷里被漏掉的第三处**。

本文件锁死的不变量：

1. 抛 ``TimeoutError`` **之前**必须落一张 ``error_auto_combat_timeout_*.png``；
2. 超时 ERROR 日志必须同时带上「实等秒数」与「超时瞬间前台应用」；
3. 命中主界面时**不**产生截图 / 前台探测（避免每场战斗都落噪声）；
4. 异常文案里的「自动战斗超时（180秒）」保持可 grep —— ``auto_dungeon_core`` 的
   ``❌ 检测到超时错误: {e}`` 直接把它打进日志，改文案会让历史 grep 断掉。
"""

from __future__ import annotations

import logging
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon_combat  # noqa: E402
from auto_dungeon_combat import auto_combat  # noqa: E402

#: 伪造的前台应用，用来证明它确实被写进了超时日志。
FAKE_FOREGROUND = "com.ms.ysjyzr/org.cocos2dx.javascript.AppActivity"

#: 伪造的「实等秒数」。大于 ``COMBAT_TIMEOUT_SECONDS`` 才会进超时分支。
FAKE_ELAPSED = 200.0


def _fake_monotonic_factory():
    """构造一个「第一次返回 0、之后一直返回 ``FAKE_ELAPSED``」的 monotonic。

    第一次调用于 ``combat_start = time.monotonic()``，之后每次都是循环里的超时判定，
    于是 ``elapsed == FAKE_ELAPSED`` 稳定可控，不必真的等 180 秒。

    Returns:
        Callable[[], float]: 供 ``monkeypatch`` 挂到 ``auto_dungeon_combat.time.monotonic``。
    """
    calls = {"count": 0}

    def _fake_monotonic() -> float:
        calls["count"] += 1
        return 0.0 if calls["count"] == 1 else FAKE_ELAPSED

    return _fake_monotonic


def _patch_combat_environment(monkeypatch, *, main_world_reached: bool) -> None:
    """把 ``auto_combat`` 的外部依赖全部打桩，只留超时/诊断逻辑真实执行。

    Args:
        monkeypatch: pytest 的 monkeypatch fixture。
        main_world_reached: True 时第一次就判定已回主界面（走成功分支）。
    """
    monkeypatch.setattr(auto_dungeon_combat, "find_text_and_click_safe", lambda *a, **k: None)
    monkeypatch.setattr(auto_dungeon_combat, "wait", lambda *a, **k: True)
    monkeypatch.setattr(auto_dungeon_combat, "check_stop_signal", lambda: False)
    monkeypatch.setattr(auto_dungeon_combat, "is_main_world", lambda: main_world_reached)
    monkeypatch.setattr(auto_dungeon_combat, "touch", lambda *a, **k: None)
    monkeypatch.setattr(auto_dungeon_combat, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(auto_dungeon_combat, "SKILL_POSITIONS", [(0, 0)] * 5)
    monkeypatch.setattr(auto_dungeon_combat.time, "monotonic", _fake_monotonic_factory())
    monkeypatch.setattr(auto_dungeon_combat.time, "time", lambda: 1_700_000_000.0)


def test_combat_timeout_saves_error_screenshot(monkeypatch):
    """超时抛出 ``TimeoutError`` 之前必须落一张错误截图。

    改前：超时分支只 ``logger.error`` + ``raise TimeoutError``，从不截图 ——
    2026-10-26 那两次故障因此没有任何画面可查。

    注意 ``create=True``：它让本用例在**尚未引入** ``save_error_screenshot`` 调用
    （甚至该名字还不存在）的旧代码上也能跑起来，于是失败会落在**行为断言**
    （「一次都没调用」）而不是「打桩目标不存在」这类机械错误上 —— 后者虽然也算
    改前失败，但证明不了「行为确实缺失」，正是"假反证"的温床。
    """
    _patch_combat_environment(monkeypatch, main_world_reached=False)

    with patch.object(auto_dungeon_combat, "save_error_screenshot", create=True) as shot:
        shot.return_value = "/tmp/error_auto_combat_timeout.png"
        with pytest.raises(TimeoutError):
            auto_combat()

    shot.assert_called_once()
    operation = shot.call_args.args[0] if shot.call_args.args else ""
    assert (
        "auto_combat" in operation
    ), f"错误截图的 operation 名应可定位到本次失败，实际为 {operation!r}"


def test_combat_timeout_logs_foreground_and_elapsed(monkeypatch, caplog):
    """超时 ERROR 日志必须写明实等秒数与超时瞬间的前台应用。

    改前：日志只有固定的「自动战斗超时（180秒），抛出异常」，既看不出到底等了多久，
    也看不出游戏是不是被切走了 —— 这次只能靠 Player.log 反推，绕了一大圈。

    同样用 ``create=True``，让改前的失败体现为**日志里没有前台信息 / 没有实等秒数**
    （行为缺失），而不是打桩目标不存在。
    """
    _patch_combat_environment(monkeypatch, main_world_reached=False)

    with patch.object(auto_dungeon_combat, "save_error_screenshot", create=True, return_value=""):
        with patch.object(
            auto_dungeon_combat, "describe_foreground", create=True, return_value=FAKE_FOREGROUND
        ) as foreground:
            with caplog.at_level(logging.ERROR, logger="auto_dungeon_combat"):
                with pytest.raises(TimeoutError):
                    auto_combat()

    foreground.assert_called_once()
    error_lines = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(
        FAKE_FOREGROUND in line for line in error_lines
    ), f"超时日志里没有前台应用信息，实际 ERROR 日志: {error_lines!r}"
    assert any(
        f"{FAKE_ELAPSED:.1f}" in line for line in error_lines
    ), f"超时日志里没有实等秒数（应为 {FAKE_ELAPSED:.1f}），实际 ERROR 日志: {error_lines!r}"


def test_combat_success_produces_no_evidence(monkeypatch, caplog):
    """命中主界面时立即返回，且**不**产生错误截图或前台探测（避免每天数百条噪声）。"""
    _patch_combat_environment(monkeypatch, main_world_reached=True)

    with patch.object(auto_dungeon_combat, "save_error_screenshot", create=True) as shot:
        with patch.object(auto_dungeon_combat, "describe_foreground", create=True) as foreground:
            with caplog.at_level(logging.ERROR, logger="auto_dungeon_combat"):
                auto_combat()

    shot.assert_not_called()
    foreground.assert_not_called()
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], "成功路径不应有 ERROR"


def test_combat_timeout_message_stays_greppable(monkeypatch):
    """异常文案必须保留「自动战斗超时（180秒）」形态。

    ``auto_dungeon_core`` 会把它原样写进 ``❌ 检测到超时错误: {e}`` —— 改文案会让
    「按超时关键词统计历史故障」的检索断掉（本项目已有多份体检记录依赖这条 grep）。
    同时锁定：阈值改动必须同步到文案，不许再出现「常量改了、消息还写 180」。
    """
    _patch_combat_environment(monkeypatch, main_world_reached=False)

    with patch.object(auto_dungeon_combat, "save_error_screenshot", create=True, return_value=""):
        with patch.object(
            auto_dungeon_combat, "describe_foreground", create=True, return_value="unknown"
        ):
            with pytest.raises(TimeoutError) as excinfo:
                auto_combat()

    expected = f"自动战斗超时（{getattr(auto_dungeon_combat, 'COMBAT_TIMEOUT_SECONDS', 180)}秒）"
    assert (
        str(excinfo.value) == expected
    ), f"超时文案应与常量保持同步，期望 {expected!r}，实际 {str(excinfo.value)!r}"
