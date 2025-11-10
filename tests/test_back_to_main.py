#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
back_to_main 的超时与兜底逻辑测试
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon  # noqa: E402


class DummyLogger:
    """简化版 logger，避免测试依赖实际日志实现"""

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


class FakeTime:
    """可控的 time.time()，每次调用递增固定步长"""

    def __init__(self, step=0.1):
        self.current = 0.0
        self.step = step

    def time(self):
        self.current += self.step
        return self.current


@pytest.fixture
def patched_dependencies(monkeypatch):
    """为 back_to_main 打桩必要依赖"""

    dummy_logger = DummyLogger()
    monkeypatch.setattr(auto_dungeon, "logger", dummy_logger)
    monkeypatch.setattr(auto_dungeon, "touch", lambda *_, **__: None)
    monkeypatch.setattr(auto_dungeon, "keyevent", lambda *_, **__: None)
    monkeypatch.setattr(auto_dungeon, "shell", lambda *_, **__: None)
    monkeypatch.setattr(auto_dungeon, "sleep", lambda *_, **__: None)
    return dummy_logger


def test_back_to_main_triggers_manual_timeout(monkeypatch, patched_dependencies):
    """持续无法返回主界面时，应触发自定义 TimeoutError"""

    fake_time = FakeTime(step=0.3)
    monkeypatch.setattr(auto_dungeon, "time", fake_time)
    monkeypatch.setattr(auto_dungeon, "is_main_world", lambda: False)

    with pytest.raises(TimeoutError):
        auto_dungeon.back_to_main(max_duration=0.5, backoff_interval=0)


def test_back_to_main_returns_once_main_world_detected(monkeypatch, patched_dependencies):
    """检测到主界面后应立即退出"""

    fake_time = FakeTime(step=0.05)
    monkeypatch.setattr(auto_dungeon, "time", fake_time)

    state = {"calls": 0}

    def fake_is_main():
        state["calls"] += 1
        return state["calls"] > 2

    monkeypatch.setattr(auto_dungeon, "is_main_world", fake_is_main)

    # 不应抛出异常
    auto_dungeon.back_to_main(max_duration=5, backoff_interval=0)

    assert state["calls"] >= 3
