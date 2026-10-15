"""dryrun 模式不得推送真实通知。

背景：``run_configs`` 在结尾无条件调用 ``_notify_and_log(..., "副本运行汇总", ...)``。
dryrun 并没有真实执行任何副本，这条汇总里的「成功 1/1、耗时 0s」是模拟值，
推给用户纯属噪音；更麻烦的是它**会写进 ``log/notifications*`` 审计**，
且运行上下文是 ``unknown``（手动/冒烟调用没有注入 config 上下文），
容易被后续排查误读成「真实故障」。

2026-10-15 实测：当天审计里两条 ``[unknown | 192.168.1.150:5555] 副本运行汇总``
全部来自 07:33 的修复冒烟与本轮体检冒烟，而不是 06:05 的自动化轮次。

本测试同时锁住反向不变量：**非 dryrun 必须照常推送**，
防止「为了消音」把真实汇总也一并屏蔽掉。
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

import run_dungeons


def _patch_common(monkeypatch, tmp_path, notified: list) -> logging.Logger:
    """打桩 ``run_configs`` 的外部依赖，只保留通知路径可观测。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        tmp_path: pytest 的临时目录夹具，避免触碰真实运行时目录。
        notified: 收集被推送的标题。

    Returns:
        logging.Logger: 传给被测函数的日志对象。
    """
    logger = logging.getLogger("test_dryrun_notification")
    monkeypatch.setattr(run_dungeons, "update_log_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        run_dungeons,
        "attach_session_file_loggers",
        lambda *_args, **_kwargs: tmp_path / "session.log",
    )
    monkeypatch.setattr(run_dungeons, "setup_logger", lambda **_kwargs: logger)
    monkeypatch.setattr(
        run_dungeons,
        "filter_pending_configs",
        lambda configs, _logger: list(configs),
    )
    monkeypatch.setattr(
        run_dungeons,
        "prevent_system_sleep",
        lambda _logger: contextlib.nullcontext(),
    )
    monkeypatch.setattr(run_dungeons, "_ensure_emulator_ready", lambda _emu, _logger: True)
    monkeypatch.setattr(
        run_dungeons,
        "send_notification",
        lambda title, *_args, **_kwargs: notified.append(title) or True,
    )
    return logger


def test_dryrun_does_not_notify(monkeypatch, tmp_path: Path) -> None:
    """dryrun 不应推送任何通知（否则制造噪音并污染通知审计）。"""
    notified: list = []
    _patch_common(monkeypatch, tmp_path, notified)

    rc = run_dungeons.run_configs(
        configs=["warrior"],
        emulator="127.0.0.1:5555",
        session="main",
        logfile=tmp_path / "main.log",
        dryrun=True,
    )

    assert rc == 0
    assert notified == [], f"dryrun 不应推送任何通知，实际推送了 {notified}"


def test_non_dryrun_still_notifies(monkeypatch, tmp_path: Path) -> None:
    """非 dryrun 必须照常推送「副本运行汇总」（防止修复过度消音）。"""
    notified: list = []
    _patch_common(monkeypatch, tmp_path, notified)
    monkeypatch.setattr(
        run_dungeons,
        "_invoke_auto_dungeon_once",
        lambda _cfg, _emu, _session: 0,
    )

    rc = run_dungeons.run_configs(
        configs=["warrior"],
        emulator="127.0.0.1:5555",
        session="main",
        logfile=tmp_path / "main.log",
        dryrun=False,
    )

    assert rc == 0
    assert "副本运行汇总" in notified, f"真实运行必须推送汇总，实际 {notified}"
