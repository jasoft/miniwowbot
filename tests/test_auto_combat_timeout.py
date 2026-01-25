"""
测试 auto_combat 超时机制
"""

import pytest


def test_auto_combat_timeout(monkeypatch):
    """auto_combat 超过 3 分钟应抛出 TimeoutError"""
    import auto_dungeon_core as core

    monkeypatch.setattr(core, "find_text_and_click_safe", lambda *args, **kwargs: None)
    monkeypatch.setattr(core, "wait", lambda *args, **kwargs: False)
    monkeypatch.setattr(core, "check_stop_signal", lambda: False)
    monkeypatch.setattr(core, "is_main_world", lambda: False)
    monkeypatch.setattr(core, "touch", lambda *args, **kwargs: None)
    monkeypatch.setattr(core, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(core, "SKILL_POSITIONS", [(0, 0)] * 5)

    monotonic_values = iter([0.0, 181.0])

    def fake_monotonic():
        return next(monotonic_values, 181.0)

    time_values = iter([0.0, 0.6, 1.2])

    def fake_time():
        return next(time_values, 1.2)

    monkeypatch.setattr(core.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(core.time, "time", fake_time)

    with pytest.raises(TimeoutError, match="180"):
        core.auto_combat()
