"""adb 可执行文件不存在时必须立即中止，而不是空转重试。

背景（2026-11-16 实测）：体检冒烟在 PATH 里没有 ``adb`` 的 shell 中运行，
``EmulatorConnectionManager`` 把 ``[WinError 2]`` 当成「模拟器连不上」，
于是白转 6 轮 × 15 秒（75 秒），最后报一句「无法连接模拟器」——
真正的根因（PATH 里没有 adb）被这行结论完全掩盖，还顺带推了一条
``[unknown | 192.168.1.150:5555] 副本运行错误`` 的假告警。

修法要点：``FileNotFoundError`` / ``winerror=2`` / ``errno=ENOENT`` 这三类
「可执行文件不存在」的异常一旦出现就置 ``adb_missing``，后续立刻收手；
其余异常（解析失败、超时抖动）仍按原逻辑重试，不能被误判成致命错误。
"""

from __future__ import annotations

import pytest

import emulator_manager


class _ListLogger:
    """把日志收进列表的极简 logger，便于对文案做行为断言。"""

    def __init__(self) -> None:
        """初始化空记录列表。"""
        self.records: list[tuple[str, str]] = []

    def _add(self, level: str, msg: object) -> None:
        """记录一条日志。"""
        self.records.append((level, str(msg)))

    def debug(self, msg: object) -> None:
        """记录 DEBUG。"""
        self._add("DEBUG", msg)

    def info(self, msg: object) -> None:
        """记录 INFO。"""
        self._add("INFO", msg)

    def warning(self, msg: object) -> None:
        """记录 WARNING。"""
        self._add("WARNING", msg)

    def error(self, msg: object) -> None:
        """记录 ERROR。"""
        self._add("ERROR", msg)

    def texts(self, level: str | None = None) -> list[str]:
        """按级别取出日志文案。

        Args:
            level: 只取该级别；``None`` 表示全部。

        Returns:
            list[str]: 日志文案列表。
        """
        return [msg for lvl, msg in self.records if level is None or lvl == level]


def _make_manager(monkeypatch: pytest.MonkeyPatch) -> emulator_manager.EmulatorConnectionManager:
    """构造一个 logger 可观测、启动命令非空的连接管理器。

    Args:
        monkeypatch: pytest 的 monkeypatch 句柄。

    Returns:
        EmulatorConnectionManager: 测试用实例。
    """
    monkeypatch.setattr(emulator_manager, "which", lambda _name: "adb")
    manager = emulator_manager.EmulatorConnectionManager(
        start_cmd="pwsh -File c:\\tools\\scripts\\start_bluestacks.ps1 -Id 1"
    )
    manager.logger = _ListLogger()  # type: ignore[assignment]
    return manager


def test_ensure_connected_aborts_when_adb_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """adb 不存在时：不重试、不启动模拟器，并明确说根因在 PATH。"""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError(2, "系统找不到指定的文件", "adb")

    monkeypatch.setattr(emulator_manager.adb_runner, "run_adb_command", _boom)
    manager = _make_manager(monkeypatch)
    starts: list[int] = []
    monkeypatch.setattr(manager, "_run_start_cmd", lambda: starts.append(1) or True)

    ok = manager.ensure_connected("192.168.1.150:5555", max_retries=3, wait_base=0)

    assert ok is False
    assert starts == [], f"adb 不存在时不应尝试启动模拟器，实际执行了 {len(starts)} 次"
    logger = manager.logger
    assert isinstance(logger, _ListLogger)
    assert any("ADB 不可用" in text for text in logger.texts("ERROR")), logger.records


def test_transient_adb_error_still_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """非「找不到文件」的异常仍要按原逻辑重试，不能被误判成致命错误。"""

    def _flaky(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("adb 输出解析失败")

    monkeypatch.setattr(emulator_manager.adb_runner, "run_adb_command", _flaky)
    manager = _make_manager(monkeypatch)
    starts: list[int] = []
    monkeypatch.setattr(manager, "_run_start_cmd", lambda: starts.append(1) or True)

    ok = manager.ensure_connected("192.168.1.150:5555", max_retries=3, wait_base=0)

    assert ok is False
    assert len(starts) == 2, f"应完成 max_retries-1 次启动尝试，实际 {len(starts)} 次"
    logger = manager.logger
    assert isinstance(logger, _ListLogger)
    assert not any("ADB 不可用" in text for text in logger.texts()), logger.records


def test_is_missing_executable_classification() -> None:
    """三类「可执行文件不存在」都要认出来，普通异常不能误判。"""
    assert emulator_manager.is_missing_executable(FileNotFoundError(2, "not found", "adb"))
    assert emulator_manager.is_missing_executable(OSError(0, "boom", None, 2))
    assert not emulator_manager.is_missing_executable(RuntimeError("boom"))
    assert not emulator_manager.is_missing_executable(TimeoutError("adb timeout"))
