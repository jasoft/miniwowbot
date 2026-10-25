"""编排器内部的子进程调用必须走「不用管道」的统一入口。

背景（2026-09-27 → 2026-10-25）
--------------------------------
2026-09-27 06:05 那轮，法师会话卡在 ``adb devices`` 上 **194 秒零日志**，编排器
看门狗按「180 秒无日志」判它僵死，杀掉会话并重启了模拟器。根因是 Windows 上
``subprocess.run(capture_output=True, timeout=N)`` 超时后，CPython 会再调一次
**没有超时**的 ``communicate()``；孙进程（常驻 adb server）持有管道写端 ⇒ 永久挂死。

当天的修复（``e0cadd6``）新增了 ``process_utils.run_command``，但**只改了
``emulator_control`` / ``emulator_manager`` / ``adb_runner`` 三条链路**，
``cron_run_all_dungeons.py`` 整个文件被漏掉：

- ``docker info``（Docker Desktop 冷启动时烧满 20 秒 —— 2026-10-25 06:05:53
  的 ``TimeoutExpired`` 就是它）
- ``docker inspect``
- ``poe stats``、OCR 启动脚本、tmux 三条、自定义模拟器关闭命令、adb 兜底
  —— 其中前两条**连 timeout 都没有**

危害不对称：**编排器自己没有看门狗**（看门狗只监控会话日志），一旦挂死只能等
计划任务的 72 小时上限 —— 那天整轮副本连同后续每一天的体检都会静默消失。

本文件锁三件事：
1. 源码里不许再出现 ``subprocess.run(``（管道收集输出的形态）；
2. 超时必须由 ``CommandResult.timed_out`` 表达，并落到「判失败 + 记日志」，
   而不是向上抛异常或直接当成功；
3. 有界：每条命令的 timeout 都是显式常量。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import cron_run_all_dungeons as cron
from process_utils import CommandResult

SOURCE_PATH = Path(__file__).resolve().parent.parent / "cron_run_all_dungeons.py"


def _result(
    *,
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
    timed_out: bool = False,
) -> CommandResult:
    """构造一个假的命令执行结果。

    Args:
        returncode: 假退出码。
        stdout: 假标准输出（字节）。
        stderr: 假标准错误（字节）。
        timed_out: 是否模拟「超时被强制终止」。

    Returns:
        对应的 :class:`process_utils.CommandResult`。
    """
    return CommandResult(
        command=("fake",),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
    )


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """取出 caplog 里 WARNING 及以上级别的日志正文。

    Args:
        caplog: pytest 的日志捕获夹具。

    Returns:
        日志正文列表。
    """
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]


def _errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    """取出 caplog 里 ERROR 及以上级别的日志正文。

    Args:
        caplog: pytest 的日志捕获夹具。

    Returns:
        日志正文列表。
    """
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


def _pipe_logging(monkeypatch: pytest.MonkeyPatch, logger: logging.Logger) -> None:
    """保证具名 logger 的日志能被子进程外的 caplog 捕获。

    ``vibe_logger.configure_logger`` 会把具名 logger 的 ``propagate`` 置为 False，
    同进程内跑过日志相关测试后本测试可能收不到日志，这里显式打开。

    Args:
        monkeypatch: pytest 打桩工具。
        logger: 需要捕获日志的 logger。
    """
    monkeypatch.setattr(logger, "propagate", True)


def test_orchestrator_has_no_pipe_subprocess_run() -> None:
    """编排器源码里不许再出现 `subprocess.run(`（管道收集输出的形态）。"""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    offenders = [
        f"{line_no}: {line.strip()}"
        for line_no, line in enumerate(source.splitlines(), 1)
        if "subprocess.run(" in line
    ]
    assert offenders == [], (
        "编排器仍在使用 subprocess.run(…)，Windows 上超时后会被持管道写端的孙进程"
        f"永久挂住，且编排器自身没有看门狗。请改用 process_utils.run_command：{offenders}"
    )


def test_poe_stats_timeout_is_reported_not_swallowed(monkeypatch, caplog) -> None:
    """`poe stats` 超时须判失败并记 ERROR，不能当成「全部完成」。"""
    monkeypatch.setattr(cron, "run_command", lambda *a, **k: _result(timed_out=True), raising=False)
    # 旧实现走 subprocess.run 且没有 timeout；桩成「立刻成功」以免真跑命令，
    # 同时让反证落在行为断言上（旧代码会返回 True）。
    monkeypatch.setattr(
        cron.subprocess, "run", lambda *a, **k: _result(returncode=0), raising=False
    )
    logger = logging.getLogger("test_poe_stats_timeout")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.run_poe_stats(logger) is False
    assert any("超时" in message for message in _errors(caplog)), _errors(caplog)


def test_docker_info_timeout_is_not_ready(monkeypatch, caplog) -> None:
    """`docker info` 超时须判「守护进程未就绪」，并说明是超时而非返回码。"""
    logger = logging.getLogger(cron.ORCHESTRATOR_LOGGER_NAME)
    _pipe_logging(monkeypatch, logger)
    caplog.set_level(logging.DEBUG, logger=logger.name)
    monkeypatch.setattr(cron, "run_command", lambda *a, **k: _result(timed_out=True), raising=False)
    monkeypatch.setattr(
        cron.subprocess, "run", lambda *a, **k: _result(returncode=0), raising=False
    )

    assert cron.is_docker_daemon_ready() is False
    assert any("docker info 超时" in message for message in _warnings(caplog)), _warnings(caplog)


def test_docker_inspect_timeout_returns_false(monkeypatch, caplog) -> None:
    """`docker inspect` 超时须判「查不到容器」，不能假设容器存在。"""
    monkeypatch.setattr(cron, "run_command", lambda *a, **k: _result(timed_out=True), raising=False)
    monkeypatch.setattr(
        cron.subprocess, "run", lambda *a, **k: _result(returncode=0), raising=False
    )
    logger = logging.getLogger("test_docker_inspect_timeout")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.ocr_container_exists(logger) is False
    assert any("查询容器状态超时" in message for message in _errors(caplog)), _errors(caplog)


def test_launch_ocr_service_script_timeout_returns_false(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """OCR 启动脚本超时须判失败，而不是无限等脚本退出。"""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "start_ocr_docker.ps1").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(cron, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(cron, "check_ocr_health", lambda logger: False)
    monkeypatch.setattr(cron, "run_command", lambda *a, **k: _result(timed_out=True), raising=False)
    monkeypatch.setattr(
        cron.subprocess, "run", lambda *a, **k: _result(returncode=0), raising=False
    )
    logger = logging.getLogger("test_ocr_script_timeout")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    assert cron.launch_ocr_service(logger) is False
    assert any("启动脚本超时" in message for message in _errors(caplog)), _errors(caplog)


def test_all_command_timeouts_are_bounded_constants() -> None:
    """每条命令的超时必须是显式常量，不能是「无超时」。"""
    for name in (
        "POE_STATS_TIMEOUT_SECONDS",
        "DOCKER_INFO_TIMEOUT_SECONDS",
        "DOCKER_INSPECT_TIMEOUT_SECONDS",
        "OCR_START_SCRIPT_TIMEOUT_SECONDS",
        "TMUX_COMMAND_TIMEOUT_SECONDS",
        "EMULATOR_SHUTDOWN_TIMEOUT_SECONDS",
    ):
        value = getattr(cron, name, None)
        assert isinstance(value, (int, float)), f"{name} 缺失或不是数值"
        assert 0 < value <= 600, f"{name}={value} 不在合理区间 (0, 600]"
