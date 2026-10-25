"""`poe stats` 的 stderr 里只有 poe 自己的任务横幅时，不应记成 WARNING。

背景（2026-10-20 体检）：编排器每天都在 ``log/cron_*.log`` 里留下这样一条

    WARNING cron_run_all_dungeons.py:868 `poe stats` 错误输出:
    Poe => uv run check_progress.py

而紧随其后的就是「`poe stats` 返回 0，判定全部完成」。``Poe => ...`` 是 poe 自己
写到 stderr 的任务横幅（成功时同样会写），把它当错误输出等于**每天误报一次告警**；
10-15 那天跑了 5 轮，误报 6 条。WARNING 一旦天天有，真故障就没人看了。

真错误（例如 uv 解析依赖失败）仍必须照常以 WARNING 记录，正文不能被吞掉。
"""

import logging

import cron_run_all_dungeons as cron
from process_utils import CommandResult


def _fake_result(returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> CommandResult:
    """构造一个与 ``process_utils.run_command`` 返回值结构相同的假结果。

    Args:
        returncode: 假退出码。
        stdout: 假标准输出（字节）。
        stderr: 假标准错误（字节）。

    Returns:
        未被判定超时的 :class:`CommandResult`。
    """
    return CommandResult(
        command=("poe", "stats"),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
    )


def _warnings(caplog) -> list[str]:
    """取出 caplog 里所有 WARNING 及以上级别的日志正文。

    Args:
        caplog: pytest 的日志捕获夹具。

    Returns:
        日志正文列表。
    """
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]


def test_poe_banner_only_does_not_warn(monkeypatch, caplog) -> None:
    """stderr 只有 poe 横幅且退出码为 0 时，不应产生任何 WARNING。"""
    monkeypatch.setattr(
        cron,
        "run_command",
        lambda *args, **kwargs: _fake_result(0, b"PASS\n", b"Poe => uv run check_progress.py\n"),
    )
    logger = logging.getLogger("test_poe_banner_only")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.run_poe_stats(logger) is True
    assert _warnings(caplog) == []


def test_poe_banner_only_with_failure_still_warns_returncode(monkeypatch, caplog) -> None:
    """失败但 stderr 只有横幅时，只保留「返回 N」这条告警，不额外报「错误输出」。"""
    monkeypatch.setattr(
        cron,
        "run_command",
        lambda *args, **kwargs: _fake_result(1, b"", b"Poe => uv run check_progress.py\n\n"),
    )
    logger = logging.getLogger("test_poe_banner_only_failure")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.run_poe_stats(logger) is False
    messages = _warnings(caplog)
    assert len(messages) == 1, messages
    assert "返回 1" in messages[0]
    assert "错误输出" not in messages[0]


def test_real_stderr_error_is_still_reported(monkeypatch, caplog) -> None:
    """stderr 里除横幅外还有真实错误时必须保留 WARNING，并带上错误正文。"""
    monkeypatch.setattr(
        cron,
        "run_command",
        lambda *args, **kwargs: _fake_result(
            1,
            b"",
            b"Poe => uv run check_progress.py\nERROR: uv failed to resolve dependencies\n",
        ),
    )
    logger = logging.getLogger("test_poe_real_error")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.run_poe_stats(logger) is False
    messages = _warnings(caplog)
    assert any(
        "错误输出" in message and "uv failed to resolve dependencies" in message
        for message in messages
    ), messages


def test_stderr_error_is_reported_even_when_exit_code_is_zero(monkeypatch, caplog) -> None:
    """退出码为 0 但 stderr 有真实告警（如 uv 警告）时仍应记录，不能静默丢弃。"""
    monkeypatch.setattr(
        cron,
        "run_command",
        lambda *args, **kwargs: _fake_result(
            0, b"PASS\n", b"Poe => uv run check_progress.py\nwarning: deprecated flag\n"
        ),
    )
    logger = logging.getLogger("test_poe_stderr_with_zero_code")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.run_poe_stats(logger) is True
    messages = _warnings(caplog)
    assert any("deprecated flag" in message for message in messages), messages
