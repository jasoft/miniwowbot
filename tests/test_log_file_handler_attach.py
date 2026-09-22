"""文件日志挂载：**具名 logger 的日志必须真的进文件**。

背景（2026-09-22 实测）：昨天的「编排器日志落盘」上线后，``log/cron_YYYY-MM-DD.log``
里只有 ``config_loader`` / ``dungeon_db`` 这类子模块的日志，编排器自己的
「🚀 准备启动」「🔁 开始第 N/5 次全流程执行」「🎉 所有副本已完成」**一行都没有** ——
而它们恰恰是判断「为什么重试了 5 轮」的唯一线索。

根因：vibe_logger 的 ``configure_logger`` 会把**具名** logger 的
``propagate`` 置为 ``False``（避免控制台重复输出），而文件 handler 挂在 root 上，
两条 propagate 链互不相通。``cron_run_all_dungeons`` 与 ``run_dungeons`` 都中招。

这个文件守护两条约定：

1. ``attach_file_handler_to_loggers`` 必须让 root 与具名 logger 的日志**都**落盘；
2. 同一条记录只能出现一次（不能因为挂了两处就写两遍）。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import cron_run_all_dungeons as cron
from logger_config import (
    LoggerConfig,
    attach_file_handler_to_loggers,
    setup_logger,
)

NAMED_LOGGER = "file_handler_probe"
MODULE_LOGGER = "file_handler_probe.module"

# 需要清理的 logger：root + 探针具名 logger + 编排器具名 logger
_TOUCHED_LOGGERS = (None, NAMED_LOGGER, cron.ORCHESTRATOR_LOGGER_NAME)


@pytest.fixture(autouse=True)
def _isolate_logging_state():
    """隔离并恢复 root / 具名 logger 的 handlers、level 与 propagate。

    挂上的 FileHandler 会一直留着并指向临时目录，不清掉会污染后续测试的日志输出；
    root 默认级别是 WARNING，不压到 INFO 就看不到子模块日志。

    Yields:
        None
    """
    snapshots = []
    for name in _TOUCHED_LOGGERS:
        logger = logging.getLogger(name)
        snapshots.append((logger, list(logger.handlers), logger.level, logger.propagate))

    # vibe_logger 用类级集合记住「已配置过的 logger」，第二次 configure 会走
    # 早退分支、不再重设 propagate；不还原它，后续测试拿到的 propagate 就是脏状态。
    configured_snapshot = set(LoggerConfig._configured_loggers)

    logging.getLogger().setLevel(logging.INFO)

    yield

    for logger, handlers, level, propagate in snapshots:
        for handler in list(logger.handlers):
            if handler not in handlers:
                logger.removeHandler(handler)
                handler.close()
        logger.setLevel(level)
        logger.propagate = propagate

    LoggerConfig._configured_loggers.clear()
    LoggerConfig._configured_loggers.update(configured_snapshot)


def test_named_and_root_loggers_both_land_in_file(tmp_path: Path) -> None:
    """root 与具名 logger 的记录都要落盘，且同一条记录只写一次。"""
    setup_logger(name=NAMED_LOGGER, level="INFO", use_color=False)
    assert logging.getLogger(NAMED_LOGGER).propagate is False, "前提：具名 logger 不向 root 传播"

    log_file = attach_file_handler_to_loggers(
        filename="probe.log",
        log_dir=str(tmp_path),
        level="INFO",
        logger_names=(None, NAMED_LOGGER),
    )

    logging.getLogger(NAMED_LOGGER).info("MARKER-具名")
    logging.getLogger(MODULE_LOGGER).info("MARKER-子模块")

    content = Path(log_file).read_text(encoding="utf-8")
    assert "MARKER-具名" in content, "具名 logger 的日志没有落盘（propagate 链断了）"
    assert "MARKER-子模块" in content, "root 链路的子模块日志没有落盘"
    assert content.count("MARKER-具名") == 1, "同一条记录被写了两遍"


def test_attach_file_handler_to_loggers_is_idempotent(tmp_path: Path) -> None:
    """重复挂载同一文件不会产生重复 handler，也就不会重复写。"""
    setup_logger(name=NAMED_LOGGER, level="INFO", use_color=False)

    for _ in range(2):
        attach_file_handler_to_loggers(
            filename="idempotent.log",
            log_dir=str(tmp_path),
            level="INFO",
            logger_names=(None, NAMED_LOGGER),
        )

    logging.getLogger(NAMED_LOGGER).info("MARKER-重复挂载")
    content = (tmp_path / "idempotent.log").read_text(encoding="utf-8")
    assert content.count("MARKER-重复挂载") == 1


def test_cron_orchestrator_logs_land_in_cron_file(tmp_path: Path, monkeypatch) -> None:
    """回归：编排器自己的日志必须写进 ``log/cron_YYYY-MM-DD.log``。

    这就是 2026-09-22 线上暴露的缺陷 —— 文件里只剩子模块日志，
    编排器的重试/汇总线索全部丢失。
    """
    monkeypatch.setattr(cron, "SCRIPT_DIR", tmp_path)

    # 复现线上条件：编排器自己的 logger 已经 setup_logger 过（propagate=False），
    # 此时只把 handler 挂在 root 上，编排器日志就是写不进文件。
    setup_logger(name=cron.ORCHESTRATOR_LOGGER_NAME, level="INFO", use_color=False)
    assert (
        logging.getLogger(cron.ORCHESTRATOR_LOGGER_NAME).propagate is False
    ), "前提：编排器具名 logger 不向 root 传播"

    log_path = cron.attach_cron_file_logger()
    assert log_path, "编排器文件日志没挂上"

    logging.getLogger(cron.ORCHESTRATOR_LOGGER_NAME).info("MARKER-编排器 第 3/5 次全流程执行")
    logging.getLogger(MODULE_LOGGER).info("MARKER-子模块")

    content = Path(log_path).read_text(encoding="utf-8")
    assert "MARKER-编排器 第 3/5 次全流程执行" in content, "编排器日志没有落盘"
    assert "MARKER-子模块" in content, "子模块日志没有落盘"
