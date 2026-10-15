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
        configs=[name],
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
        configs=["main"],
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


def test_filter_pending_session_tasks_skips_completed_session(monkeypatch) -> None:
    """已完成的会话不应进入启动列表。"""
    logger = logging.getLogger("test_filter_pending_session_tasks")
    task = cron.SessionTask(
        name="main",
        emulator="127.0.0.1:5555",
        logfile=Path("log") / "main.log",
        configs=["warrior"],
        cmd="echo warrior",
    )

    monkeypatch.setattr(cron, "filter_pending_configs", lambda _configs, _logger: [])

    pending_tasks = cron.filter_pending_session_tasks([task], logger)

    assert pending_tasks == []


def test_filter_pending_session_tasks_rebuilds_trimmed_command(monkeypatch) -> None:
    """部分完成时应只保留剩余配置并重建命令。"""
    logger = logging.getLogger("test_filter_pending_session_tasks_trim")
    task = cron.SessionTask(
        name="main",
        emulator="127.0.0.1:5555",
        logfile=Path("log") / "main.log",
        configs=["mage", "warrior"],
        cmd="old command",
    )

    monkeypatch.setattr(cron, "filter_pending_configs", lambda _configs, _logger: ["warrior"])

    pending_tasks = cron.filter_pending_session_tasks([task], logger)

    assert len(pending_tasks) == 1
    assert pending_tasks[0].configs == ["warrior"]
    assert "--config warrior" in pending_tasks[0].cmd
    assert "--config mage" not in pending_tasks[0].cmd


def test_main_only_runs_stats_when_all_sessions_filtered(monkeypatch) -> None:
    """全部会话被过滤时只应执行一次 stats 校验。"""
    logger = logging.getLogger("test_main_all_filtered")
    task = cron.SessionTask(
        name="main",
        emulator="127.0.0.1:5555",
        logfile=Path("log") / "main.log",
        configs=["main"],
        cmd="echo test",
    )
    calls: list[str] = []

    monkeypatch.setattr(cron, "setup_logger", lambda **_kwargs: logger)
    monkeypatch.setattr(cron, "ensure_log_dir", lambda: calls.append("ensure_log_dir"))
    monkeypatch.setattr(cron, "load_sessions_from_json", lambda _path: [{"name": "main"}])
    monkeypatch.setattr(cron, "parse_session_tasks", lambda _sessions, _logger: [task])
    monkeypatch.setattr(cron, "filter_pending_session_tasks", lambda _tasks, _logger: [])
    monkeypatch.setattr(cron, "prepare_ocr_service", lambda _logger: calls.append("prepare_ocr_service"))
    monkeypatch.setattr(cron, "run_single_flow", lambda _tasks, _logger: calls.append("run_single_flow") or True)
    monkeypatch.setattr(cron, "run_poe_stats", lambda _logger: calls.append("run_poe_stats") or True)

    assert cron.main() == 0
    assert "prepare_ocr_service" not in calls
    assert "run_single_flow" not in calls
    assert calls.count("run_poe_stats") == 1


def test_main_refilters_sessions_on_each_retry(monkeypatch) -> None:
    """重试轮必须先重新过滤：已无待执行会话时不应再空跑一轮。

    2026-10-15 实测：第 1 轮跑完后剩余会话已全部完成，但主循环仍拿着最初的
    ``pending_tasks`` 重跑 4 轮，每轮都是「启模拟器 → 会话立即退出 → 关模拟器」。
    修复后第 2 轮即由 ``poe stats`` 判定并收尾，不再重复启动会话。
    """
    logger = logging.getLogger("test_main_refilter")
    task = cron.SessionTask(
        name="main",
        emulator="127.0.0.1:5555",
        logfile=Path("log") / "main.log",
        configs=["warrior"],
        cmd="echo test",
    )
    calls: list[str] = []
    filter_results: list[list] = [[task], [task], []]

    def fake_filter(_tasks, _logger):
        calls.append("filter")
        return filter_results.pop(0) if filter_results else []

    monkeypatch.setattr(cron, "setup_logger", lambda **_kwargs: logger)
    monkeypatch.setattr(cron, "ensure_log_dir", lambda: None)
    monkeypatch.setattr(cron, "archive_console_log", lambda: None)
    monkeypatch.setattr(cron, "attach_cron_file_logger", lambda: None)
    monkeypatch.setattr(cron, "cleanup_temp_dir", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cron, "load_sessions_from_json", lambda _path: [{"name": "main"}])
    monkeypatch.setattr(cron, "parse_session_tasks", lambda _sessions, _logger: [task])
    monkeypatch.setattr(cron, "filter_pending_session_tasks", fake_filter)
    monkeypatch.setattr(cron, "prepare_ocr_service", lambda _logger: True)
    monkeypatch.setattr(
        cron, "run_single_flow", lambda _tasks, _logger: calls.append("flow") or False
    )
    monkeypatch.setattr(cron, "run_poe_stats", lambda _logger: calls.append("stats") or False)

    assert cron.main() == 1
    # 关键断言：第 2 轮起不再启动会话（改前会跑满 5 轮，即 flow == 5）
    assert calls.count("flow") == 1, f"重试轮不应重复启动会话: {calls}"
    assert calls.count("filter") == 3, f"每轮重试都应重新过滤: {calls}"
    assert calls.count("stats") == 1
