"""回归测试：``auto_dungeon_utils.sleep`` 未显式传 reason 时的日志文案。

历史问题：``sleep`` 的 ``reason`` 默认值是开发期占位符 ``[需要填写原因]``，
生产日志里每天约 150 条（累计 1.8 万条）都是这一句话，既没有信息量，
看着还像"有人漏填了 bug 报告"，严重干扰按日志排查。

修复后：未传 reason 时自动取调用方函数名（``未注明（调用 <函数名>）``）。
"""

import inspect
import logging

import auto_dungeon_utils


def _fake_airtest_sleep(seconds: float) -> None:
    """替身：避免测试真的等待。"""


def test_sleep_without_reason_logs_caller_name(monkeypatch, caplog):
    """不传 reason 时，日志应给出调用方函数名，而不是占位符。"""
    monkeypatch.setattr(auto_dungeon_utils, "airtest_sleep", _fake_airtest_sleep)

    def _open_exchange_tab() -> None:
        auto_dungeon_utils.sleep(0.0)

    with caplog.at_level(logging.INFO, logger="auto_dungeon_utils"):
        _open_exchange_tab()

    text = caplog.text
    assert "[需要填写原因]" not in text
    assert "未注明" in text
    # 关键：调用方函数名必须出现，否则这条日志依然没有排查价值
    assert "_open_exchange_tab" in text


def test_sleep_with_explicit_reason_keeps_reason(monkeypatch, caplog):
    """显式传入的 reason 必须原样保留。"""
    monkeypatch.setattr(auto_dungeon_utils, "airtest_sleep", _fake_airtest_sleep)

    with caplog.at_level(logging.INFO, logger="auto_dungeon_utils"):
        auto_dungeon_utils.sleep(1.5, "等待地图加载完毕")

    assert "等待 1.5 秒" in caplog.text
    assert "等待地图加载完毕" in caplog.text
    assert "[需要填写原因]" not in caplog.text


def test_reason_default_is_none():
    """``reason`` 的默认值必须是 None（而不是任何占位符字符串）。"""
    sig = inspect.signature(auto_dungeon_utils.sleep)
    assert sig.parameters["reason"].default is None
