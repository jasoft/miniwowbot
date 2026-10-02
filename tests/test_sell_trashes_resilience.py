"""卖垃圾失败的韧性测试。

真机背景：`sell_trashes` 偶发点不到「整理售卖」，约三周一次
（2026-07-13 / 08-30 / 09-18 / 10-02；2026-10-02 mage_alt 那次在 2 分钟后的
下一个卖垃圾周期就正常了）。旧实现直接 ``raise Exception`` →
``main_wrapper`` 判「脚本异常退出」→ 编排器停/重启模拟器重跑一轮（约 2 分钟）
+ 给大王推一条「程序发生错误」。

本文件锁住三条不变量：

1. 点不到时**有界重试**，而不是一次失败就放弃；
2. 重试仍失败时**返回 False 并落诊断信息**（截图 + 前台应用），
   绝不抛异常炸掉整个会话；
3. 成功路径行为不变（「装备」→「整理售卖」→ 确认坐标），
   免得为了「不崩」把正常功能改坏。
"""

from __future__ import annotations

import logging
from typing import Any

import auto_dungeon_navigation
import auto_dungeon_ui
import pytest


def _patch_ui(monkeypatch, *, equip_found: list[bool], sell_found: list[bool]):
    """打桩 UI 交互，按顺序返回「装备」「整理售卖」的查找结果。

    列表短于实际调用次数时，重复最后一个值 —— 这样测试只需声明
    「前 N 次失败、之后成功」，而不必预先算好精确次数。

    Args:
        monkeypatch: pytest 打桩工具。
        equip_found: 每次查找「装备」的结果。
        sell_found: 每次查找「整理售卖」的结果。

    Returns:
        tuple[list[int], list[int], list[Any], list[int]]:
            「装备」查找次数、「整理售卖」查找次数、点击坐标、返回按钮点击次数。
    """
    equip_calls: list[int] = []
    sell_calls: list[int] = []
    touched: list[Any] = []
    back_calls: list[int] = []

    def _pick(results: list[bool], calls: list[int]) -> bool:
        calls.append(1)
        return results[min(len(calls) - 1, len(results) - 1)]

    def _find(text: str, *args: Any, **kwargs: Any) -> bool:
        if text == "装备":
            return _pick(equip_found, equip_calls)
        if text == "整理售卖":
            return _pick(sell_found, sell_calls)
        pytest.fail(f"出现了预期之外的查找目标: {text}")

    monkeypatch.setattr(auto_dungeon_ui, "find_text_and_click_safe", _find)
    monkeypatch.setattr(auto_dungeon_ui, "click_back", lambda: back_calls.append(1) or True)
    monkeypatch.setattr(auto_dungeon_ui, "touch", lambda point: touched.append(point))
    monkeypatch.setattr(auto_dungeon_ui, "sleep", lambda *a, **k: None)
    return equip_calls, sell_calls, touched, back_calls


def _patch_diagnostics(monkeypatch, *, boom: bool = False) -> list[str]:
    """打桩失败诊断，避免测试写真实截图文件。

    Args:
        monkeypatch: pytest 打桩工具。
        boom: 为 True 时让截图函数抛异常，用于验证诊断失败不打断主流程。

    Returns:
        list[str]: 被请求保存的截图名。
    """
    saved: list[str] = []

    def _save(name: str) -> str:
        if boom:
            raise RuntimeError("截图失败")
        saved.append(name)
        return f"/tmp/{name}.png"

    monkeypatch.setattr(auto_dungeon_navigation, "save_error_screenshot", _save)
    monkeypatch.setattr(
        auto_dungeon_navigation,
        "describe_foreground",
        lambda: "com.ms.ysjyzr/org.cocos2dx.javascript.AppActivity",
    )
    return saved


def test_sell_trashes_succeeds_on_first_attempt(monkeypatch) -> None:
    """成功路径：点「装备」→「整理售卖」→ 确认坐标，并两次返回主界面。"""
    _patch_diagnostics(monkeypatch)
    equip_calls, sell_calls, touched, back_calls = _patch_ui(
        monkeypatch,
        equip_found=[True],
        sell_found=[True],
    )

    assert auto_dungeon_ui.sell_trashes() is True

    assert equip_calls == [1], "成功时不该重试"
    assert sell_calls == [1]
    assert touched == [(462, 958)]
    assert len(back_calls) == 3, "进入前 1 次 + 卖出后 2 次返回"


def test_sell_trashes_retries_when_sell_button_missing(monkeypatch) -> None:
    """第一次点不到「整理售卖」时重试，第二次点到了就算成功。"""
    _patch_diagnostics(monkeypatch)
    equip_calls, sell_calls, _touched, _back_calls = _patch_ui(
        monkeypatch,
        equip_found=[True],
        sell_found=[False, True],
    )

    assert auto_dungeon_ui.sell_trashes() is True

    assert sell_calls == [1, 1], "必须重试第二轮"
    assert equip_calls == [1, 1], "每轮都要重新点一次「装备」"


def test_sell_trashes_does_not_raise_and_reports_failure(monkeypatch, caplog) -> None:
    """重试用尽仍失败：返回 False + 落诊断信息，绝不抛异常。"""
    saved = _patch_diagnostics(monkeypatch)
    equip_calls, sell_calls, _touched, _back_calls = _patch_ui(
        monkeypatch,
        equip_found=[True],
        sell_found=[False],
    )

    with caplog.at_level(logging.ERROR, logger="auto_dungeon_ui"):
        result = auto_dungeon_ui.sell_trashes()

    assert result is False
    assert (
        len(sell_calls) == auto_dungeon_ui.SELL_TRASHES_MAX_ATTEMPTS
    ), "重试次数必须被 SELL_TRASHES_MAX_ATTEMPTS 限制住"
    assert len(equip_calls) == auto_dungeon_ui.SELL_TRASHES_MAX_ATTEMPTS
    assert saved == ["sell_trashes"], "失败时必须落一张诊断截图"
    assert "卖垃圾失败" in caplog.text
    assert "com.ms.ysjyzr" in caplog.text, "日志要带上失败瞬间的前台应用"


def test_sell_trashes_does_not_raise_when_equip_missing(monkeypatch) -> None:
    """连「装备」入口都点不到时同样只重试、不抛异常。"""
    _patch_diagnostics(monkeypatch)
    equip_calls, sell_calls, _touched, _back_calls = _patch_ui(
        monkeypatch,
        equip_found=[False],
        sell_found=[True],
    )

    assert auto_dungeon_ui.sell_trashes() is False

    assert len(equip_calls) == auto_dungeon_ui.SELL_TRASHES_MAX_ATTEMPTS
    assert sell_calls == [], "「装备」都没点到，不该去点「整理售卖」"


def test_sell_trashes_survives_diagnostic_failure(monkeypatch) -> None:
    """诊断信息收集本身失败（截图抛异常）也不能反过来打断主流程。"""
    _patch_diagnostics(monkeypatch, boom=True)
    _patch_ui(monkeypatch, equip_found=[True], sell_found=[False])

    assert auto_dungeon_ui.sell_trashes() is False
