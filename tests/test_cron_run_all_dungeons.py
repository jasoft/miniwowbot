"""`cron_run_all_dungeons.py` 的会话恢复逻辑测试。"""

from __future__ import annotations

import logging
from pathlib import Path

import cron_run_all_dungeons as cron


def _build_runtime(name: str = "main") -> cron.SessionRuntime:
    """构造用于测试的会话运行态对象。

    Args:
        name: 会话名称。

    Returns:
        `SessionRuntime` 测试对象。
    """
    task = cron.SessionTask(
        name=name,
        emulator="127.0.0.1:5555",
        logfile=Path("log") / f"{name}.log",
        cmd="echo test",
    )
    return cron.SessionRuntime(task=task)


def test_restart_session_stops_shell_and_emulator_before_start(monkeypatch) -> None:
    """重启会话前应先关闭 shell 与模拟器。"""
    runtime = _build_runtime()
    logger = logging.getLogger("test_restart_session")
    calls: list[str] = []

    monkeypatch.setattr(
        cron,
        "stop_session",
        lambda _runtime, _logger: calls.append("stop_session"),
    )
    monkeypatch.setattr(
        cron,
        "stop_emulator",
        lambda _emulator, _logger: calls.append("stop_emulator"),
    )
    monkeypatch.setattr(
        cron,
        "start_session",
        lambda _runtime, _logger: calls.append("start_session") or True,
    )

    assert cron.restart_session(runtime, logger) is True
    assert runtime.restart_count == 1
    assert calls == ["stop_session", "stop_emulator", "start_session"]


def test_restart_session_respects_max_idle_restarts(monkeypatch) -> None:
    """达到日志停滞重启上限后应直接失败。"""
    runtime = _build_runtime()
    runtime.restart_count = cron.SESSION_MAX_IDLE_RESTARTS
    logger = logging.getLogger("test_restart_limit")
    calls: list[str] = []

    monkeypatch.setattr(
        cron,
        "stop_session",
        lambda _runtime, _logger: calls.append("stop_session"),
    )
    monkeypatch.setattr(
        cron,
        "stop_emulator",
        lambda _emulator, _logger: calls.append("stop_emulator"),
    )
    monkeypatch.setattr(
        cron,
        "start_session",
        lambda _runtime, _logger: calls.append("start_session") or True,
    )

    assert cron.restart_session(runtime, logger) is False
    assert calls == []


def test_monitor_sessions_returns_false_on_nonzero_exit(monkeypatch) -> None:
    """子 shell 非 0 退出时应中止本轮流程。"""
    runtime = _build_runtime()
    logger = logging.getLogger("test_monitor_nonzero_exit")
    recover_reasons: list[str] = []
    stop_calls: list[str] = []

    monkeypatch.setattr(cron, "is_session_alive", lambda _runtime: False)
    monkeypatch.setattr(cron, "get_session_exit_code", lambda _runtime: 2)
    monkeypatch.setattr(
        cron,
        "recover_failed_runtime",
        lambda _runtime, reason, _logger: recover_reasons.append(reason),
    )
    monkeypatch.setattr(
        cron,
        "stop_other_alive_sessions",
        lambda _runtimes, _failed_runtime, _logger: stop_calls.append("stop"),
    )

    assert cron.monitor_sessions([runtime], logger) is False
    assert recover_reasons == ["子 shell 非 0 退出"]
    assert stop_calls == ["stop"]


def test_monitor_sessions_returns_true_when_all_finished(monkeypatch) -> None:
    """所有会话正常结束时应返回成功。"""
    runtime = _build_runtime()
    logger = logging.getLogger("test_monitor_success")

    monkeypatch.setattr(cron, "is_session_alive", lambda _runtime: False)
    monkeypatch.setattr(cron, "get_session_exit_code", lambda _runtime: 0)

    assert cron.monitor_sessions([runtime], logger) is True


def test_run_single_flow_skips_stats_when_monitor_failed(monkeypatch) -> None:
    """监控失败时不应继续执行 `poe stats`。"""
    logger = logging.getLogger("test_run_single_flow")
    task = cron.SessionTask(
        name="main",
        emulator="127.0.0.1:5555",
        logfile=Path("log") / "main.log",
        cmd="echo test",
    )
    run_stats_calls: list[str] = []

    monkeypatch.setattr(cron, "start_session", lambda _runtime, _logger: True)
    monkeypatch.setattr(cron, "monitor_sessions", lambda _runtimes, _logger: False)
    monkeypatch.setattr(
        cron,
        "run_poe_stats",
        lambda _logger: run_stats_calls.append("run") or True,
    )
    monkeypatch.setattr(cron.time, "sleep", lambda _seconds: None)

    assert cron.run_single_flow([task], logger) is False
    assert run_stats_calls == []
