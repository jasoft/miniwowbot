"""Docker 引擎恢复动作 / 中止告警的回归测试。

背景（2026-11-11 06:05 那轮，整天 0 产出）
------------------------------------------
机器 05:58:15 从低功耗状态恢复，Docker Desktop 随即尝试拉起 linux/wsl 引擎，
06:58:30 因 ``wsl.exe --version failed`` 直接 ``starting -> stopping``。7 分钟后
计划任务启动，``docker info`` 连续 13 次超时（每次 20s + 5s 轮询），06:11:01
编排器判定「Docker 守护进程等待超时」→ OCR 不可用 → ``return 3`` 中止整轮。

两处代码缺陷：

1. **恢复动作无效**：``ensure_docker_daemon`` 只 ``Popen`` 一个 GUI，但
   Docker Desktop 进程自 10-30 起一直在跑（PID 未变），再拉起是**空操作**；
   引擎停在 ``stopped`` 不会自愈，300 秒注定白等。
   ⇒ 必须先区分「没启动」与「在跑但引擎无响应」，后者只能重启引擎。
2. **中止静默**：``main()`` 直接 ``return 3``，``log/notifications``
   当天一条记录都没有 —— 整天 22 个副本静默归零，没人知道。

本文件锁四件事：
1. 进程在跑但引擎无响应时**必须**下发 ``docker desktop restart``，且**不再** Popen；
2. 进程不在时**仍然**只 Popen，且**不得**误重启（避免无谓打断别人的容器）；
3. 等待超时必须落 ``docker desktop status`` / ``wsl --version`` 诊断快照；
4. OCR 不可用中止时必须推送告警，且**不带** ``[config | emulator]`` 前缀
   （全局结论套会话前缀只会显示成 ``[unknown | unknown]``，误导收件人）。
"""

from __future__ import annotations

import logging
import sys
import types

import auto_dungeon_notification as notify
import cron_run_all_dungeons as cron
import pytest
from process_utils import CommandResult


def _result(
    command: tuple[str, ...] = ("cmd",),
    *,
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
    timed_out: bool = False,
) -> CommandResult:
    """构造一个假的命令执行结果。

    Args:
        command: 假命令行。
        returncode: 假退出码。
        stdout: 假标准输出（字节）。
        stderr: 假标准错误（字节）。
        timed_out: 是否模拟「超时被强制终止」。

    Returns:
        对应的 :class:`process_utils.CommandResult`。
    """
    return CommandResult(
        command=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
    )


class _FakeClock:
    """把 ``time.time`` / ``time.sleep`` 换成可控计数器，避免测试真等 300 秒。"""

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_restarts_engine_when_process_running_but_not_ready(monkeypatch):
    """进程在跑、引擎无响应时必须重启引擎，而不是再启动一次 GUI。"""
    monkeypatch.setattr(cron, "time", _FakeClock())
    # 初次检查 False；重启后第一轮轮询即就绪
    states = [False, True]

    def fake_ready() -> bool:
        return states.pop(0) if states else True

    monkeypatch.setattr(cron, "is_docker_daemon_ready", fake_ready)
    monkeypatch.setattr(cron, "docker_desktop_process_running", lambda: True, raising=False)

    restarted: list[int] = []
    monkeypatch.setattr(
        cron,
        "restart_docker_engine",
        lambda logger: restarted.append(1) or True,
        raising=False,
    )

    popen_calls: list[tuple] = []
    monkeypatch.setattr(cron.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append(args))

    assert cron.ensure_docker_daemon(logging.getLogger("test")) is True
    assert restarted == [1], "进程已在运行时必须重启引擎，否则 300 秒注定白等"
    assert popen_calls == [], "进程已在运行时不应再 Popen 一个 GUI（那是空操作）"


def test_launches_gui_and_skips_restart_when_process_absent(monkeypatch):
    """进程不在时走启动 GUI 的老路径，且不得误触发重启。"""
    monkeypatch.setattr(cron, "time", _FakeClock())
    states = [False, True]

    def fake_ready() -> bool:
        return states.pop(0) if states else True

    monkeypatch.setattr(cron, "is_docker_daemon_ready", fake_ready)
    monkeypatch.setattr(cron, "docker_desktop_process_running", lambda: False, raising=False)

    restarted: list[int] = []
    monkeypatch.setattr(
        cron,
        "restart_docker_engine",
        lambda logger: restarted.append(1) or True,
        raising=False,
    )

    popen_calls: list[tuple] = []
    monkeypatch.setattr(cron.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append(args))

    assert cron.ensure_docker_daemon(logging.getLogger("test")) is True
    assert len(popen_calls) == 1, "未启动时应拉起 Docker Desktop"
    assert restarted == [], "进程没在跑就不该重启，重启会打断别人正在用的容器"


def test_timeout_logs_wsl_and_engine_diagnostics(monkeypatch):
    """等待超时必须落 WSL / 引擎状态快照，别让人再翻 Docker 自己的日志。"""
    monkeypatch.setattr(cron, "time", _FakeClock())
    monkeypatch.setattr(cron, "is_docker_daemon_ready", lambda: False)
    monkeypatch.setattr(cron, "docker_desktop_process_running", lambda: True, raising=False)
    monkeypatch.setattr(cron, "restart_docker_engine", lambda logger: True, raising=False)
    monkeypatch.setattr(cron.subprocess, "Popen", lambda *args, **kwargs: None)

    commands: list[tuple] = []

    def fake_run_command(cmd, timeout, shell=False, cwd=None):
        commands.append(tuple(cmd))
        return _result(tuple(cmd))

    monkeypatch.setattr(cron, "run_command", fake_run_command)

    assert cron.ensure_docker_daemon(logging.getLogger("test")) is False
    flattened = [" ".join(cmd) for cmd in commands]
    assert any("wsl" in cmd for cmd in flattened), "超时后必须记录 `wsl --version` 结果"
    assert any("desktop status" in cmd for cmd in flattened), "超时后必须记录引擎状态"


def test_ocr_unavailable_notifies_without_context_prefix(monkeypatch):
    """OCR 不可用导致中止时必须告警，且不能套会话上下文前缀。"""
    recorded: list[tuple] = []

    def fake_send(title, message, **kwargs):
        recorded.append((title, message, kwargs))
        return True

    monkeypatch.setattr(notify, "send_notification", fake_send, raising=False)

    func = getattr(cron, "notify_ocr_unavailable", None)
    assert func is not None, "旧代码在 OCR 不可用时直接 return 3，整天静默归零"

    assert func(logging.getLogger("test")) is True
    assert len(recorded) == 1, "中止必须推送一条告警"
    title, _message, kwargs = recorded[0]
    assert kwargs.get("enrich_context") is False, "全局结论不能套 [config | emulator]"
    assert kwargs.get("level") == "timeSensitive"
    assert "中止" in title


@pytest.mark.allow_real_notifications
def test_pushover_respects_enrich_context_false(monkeypatch):
    """``enrich_context=False`` 时 Pushover 标题不得带 ``[unknown | unknown]``。

    标 ``allow_real_notifications`` 是为了让 ``send_pushover_notification``
    真正跑到拼装标题那一步；API 与审计都被替换成假对象，不会有任何出网/落盘。
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(notify, "_audit_notification", lambda *a, **k: None)
    monkeypatch.setattr(
        notify, "_get_pushover_config", lambda: {"app_key": "app", "user_key": "user"}
    )

    sent: dict = {}

    class _FakeAPI:
        def __init__(self, app_key: str) -> None:
            self.app_key = app_key

        def send_message(self, **params):
            sent.update(params)
            return {"status": 1}

    monkeypatch.setitem(
        sys.modules, "pushover_complete", types.SimpleNamespace(PushoverAPI=_FakeAPI)
    )

    assert notify.send_pushover_notification("🛑 中止", "正文", enrich_context=False) is True
    assert sent["title"] == "🛑 中止"
    assert "[unknown" not in sent["title"]
    assert sent["message"] == "正文"
    assert "enrich_context" not in sent, "该参数只控制本地拼装，不能进 API 载荷"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
