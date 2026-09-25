"""``back_to_main`` 的「游戏已不在前台」快速失败守卫回归测试。

背景（2026-09-25 06:07:40 ~ 06:10:07 实测）：

``back_to_main`` 靠「点返回按钮 + 按系统返回键」退回主界面。游戏一旦被退到
Android 桌面（系统返回键在游戏根界面就是「退出应用」），返回键**永远**回不到
主界面，于是：

- 单次调用空转满 15 秒才抛 ``TimeoutError``；
- 日常任务区 8 个任务各白等一次 → 约 2 分钟纯浪费；
- 18 次超时、8 条内容相同且与真实原因无关的告警；
- 直到状态机路径上的那一次 ``back_to_main`` 异常冒泡到 ``main_wrapper``，
  才触发「超时重启」恢复。

本文件锁定修复后的行为：**探测到游戏不在前台就立刻失败**，并且把这个状态
交给外层去重启游戏，而不是当成 8 个独立的任务失败。
"""

from __future__ import annotations

import pytest

import auto_dungeon_daily as daily
import auto_dungeon_navigation as nav


class _FakeTime:
    """可手动推进的假时钟，避免测试真的等 15 秒。"""

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        """返回当前假时间戳。

        Returns:
            float: 秒。
        """
        return self.now

    def advance(self, seconds: float) -> None:
        """推进假时钟。

        Args:
            seconds: 推进的秒数。
        """
        self.now += seconds


def _patch_back_to_main_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    on_main_world: bool,
    foreground: bool | None,
) -> _FakeTime:
    """把 ``back_to_main`` 依赖的设备动作全部替换成桩。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        on_main_world: ``is_main_world`` 的返回值。
        foreground: ``is_game_foreground`` 的返回值（``None`` 表示探测不出结论）。

    Returns:
        _FakeTime: 已接管 ``nav.time`` 的假时钟。
    """
    clock = _FakeTime()
    monkeypatch.setattr(nav, "time", clock)
    monkeypatch.setattr(nav, "sleep", lambda *a, **k: clock.advance(0.2))
    monkeypatch.setattr(nav, "touch", lambda *a, **k: None)
    monkeypatch.setattr(nav, "keyevent", lambda *a, **k: None)
    monkeypatch.setattr(nav, "is_main_world", lambda: on_main_world)
    monkeypatch.setattr(nav, "is_game_foreground", lambda *a, **k: foreground)
    return clock


# ====== GameNotForegroundError 的契约 ======


def test_game_not_foreground_error_is_timeout_error() -> None:
    """必须继承 TimeoutError，才能复用 main_wrapper 的「超时→重启游戏」路径。"""
    assert issubclass(nav.GameNotForegroundError, TimeoutError)


# ====== is_game_foreground 三态语义 ======


def test_is_game_foreground_true_when_game_on_top(monkeypatch: pytest.MonkeyPatch) -> None:
    """前台就是游戏包名时返回 True。"""

    class _Device:
        def get_top_activity(self):
            return (nav.GAME_PACKAGE, ".MainActivity")

    class _G:
        DEVICE = _Device()

    monkeypatch.setattr("airtest.core.api.G", _G)
    assert nav.is_game_foreground() is True


def test_is_game_foreground_false_when_other_app_on_top(monkeypatch: pytest.MonkeyPatch) -> None:
    """前台是别的应用时返回明确 False（这是唯一会触发中止的取值）。"""

    class _Device:
        def get_top_activity(self):
            return ("com.bluestacks.launcher", ".Home")

    class _G:
        DEVICE = _Device()

    monkeypatch.setattr("airtest.core.api.G", _G)
    assert nav.is_game_foreground() is False


def test_is_game_foreground_none_without_device(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有设备时返回 None，而不是 False —— 探测不出结论不该触发重启。"""

    class _G:
        DEVICE = None

    monkeypatch.setattr("airtest.core.api.G", _G)
    assert nav.is_game_foreground() is None


def test_is_game_foreground_none_on_probe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """探测本身抛异常时返回 None，把抖动和「真的不在前台」区分开。"""

    class _Device:
        def get_top_activity(self):
            raise RuntimeError("dumpsys 挂了")

    class _G:
        DEVICE = _Device()

    monkeypatch.setattr("airtest.core.api.G", _G)
    assert nav.is_game_foreground() is None


# ====== back_to_main 的行为 ======


def test_back_to_main_fails_fast_when_game_not_foreground(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """游戏不在前台时立刻抛 GameNotForegroundError，不再空转满 15 秒。"""
    clock = _patch_back_to_main_env(monkeypatch, on_main_world=False, foreground=False)

    with pytest.raises(nav.GameNotForegroundError):
        nav.back_to_main(max_duration=15, backoff_interval=0.2)

    # 旧实现这里会一路等到 15 秒才抛 TimeoutError
    assert clock.now < 1.0


def test_back_to_main_still_times_out_when_probe_inconclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """探测不出结论（None）时退回原行为：等满 max_duration 再抛超时。"""
    clock = _patch_back_to_main_env(monkeypatch, on_main_world=False, foreground=None)

    with pytest.raises(TimeoutError) as exc:
        nav.back_to_main(max_duration=3, backoff_interval=0.2)

    assert not isinstance(exc.value, nav.GameNotForegroundError)
    assert clock.now >= 3


def test_back_to_main_does_not_abort_while_game_in_foreground(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """游戏还在前台时不能中止：多按几次返回键本来就可能是在关多层弹窗。"""
    clock = _patch_back_to_main_env(monkeypatch, on_main_world=False, foreground=True)

    with pytest.raises(TimeoutError) as exc:
        nav.back_to_main(max_duration=3, backoff_interval=0.2)

    assert not isinstance(exc.value, nav.GameNotForegroundError)
    assert clock.now >= 3


def test_back_to_main_returns_when_main_world_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """已经回到主界面时正常返回，不做任何探测。"""
    _patch_back_to_main_env(monkeypatch, on_main_world=True, foreground=False)

    nav.back_to_main(max_duration=15, backoff_interval=0.2)


def test_back_to_main_foreground_check_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """foreground_check_interval<=0 时关闭探测，行为回到纯超时。"""
    clock = _patch_back_to_main_env(monkeypatch, on_main_world=False, foreground=False)

    with pytest.raises(TimeoutError) as exc:
        nav.back_to_main(max_duration=2, backoff_interval=0.2, foreground_check_interval=0)

    assert not isinstance(exc.value, nav.GameNotForegroundError)
    assert clock.now >= 2


# ====== switch_to_zone：地图没打开时不要盲等 ======


def test_switch_to_zone_reopens_map_each_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """每次尝试前都确认地图已打开，不在地图界面就重开（旧实现一次都不重开）。"""
    opened: list[str] = []

    monkeypatch.setattr(nav, "is_on_map", lambda: False)
    monkeypatch.setattr(nav, "open_map", lambda: opened.append("open_map"))
    monkeypatch.setattr(nav, "find_text_and_click_safe", lambda *a, **k: False)
    monkeypatch.setattr(nav, "save_error_screenshot", lambda *a, **k: "")

    assert nav.switch_to_zone("亡灵之地", max_attempts=2) is False
    assert opened.count("open_map") == 2


def test_switch_to_zone_does_not_use_blind_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """重试前不再多等一次 10 秒的「切换区域」OCR，改为重开地图。"""
    probed: list[str] = []

    def _fake_find(text, *a, **k):
        probed.append(text)
        return False

    monkeypatch.setattr(nav, "is_on_map", lambda: True)
    monkeypatch.setattr(nav, "open_map", lambda: None)
    monkeypatch.setattr(nav, "find_text_and_click_safe", _fake_find)
    monkeypatch.setattr(nav, "save_error_screenshot", lambda *a, **k: "")

    assert nav.switch_to_zone("亡灵之地", max_attempts=3) is False
    # 旧实现是 5 次：3 次循环 + 2 次「关闭弹窗后重试」前的盲等
    assert probed.count("切换区域") == 3


def test_switch_to_zone_succeeds_without_extra_map_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """已在地图界面且切换成功时，正常返回 True。"""
    opened: list[str] = []

    monkeypatch.setattr(nav, "is_on_map", lambda: True)
    monkeypatch.setattr(nav, "open_map", lambda: opened.append("open_map"))
    monkeypatch.setattr(nav, "find_text_and_click_safe", lambda *a, **k: True)
    monkeypatch.setattr(nav, "touch", lambda *a, **k: None)

    assert nav.switch_to_zone("亡灵之地") is True
    assert opened == []


# ====== 日常任务层：放行而不是当成任务失败 ======


def test_execute_task_propagates_game_not_foreground(monkeypatch: pytest.MonkeyPatch) -> None:
    """游戏不在前台时不吞异常、不发「任务未完成」告警，直接交给外层重启。"""
    manager = daily.DailyCollectManager()
    manager.TASK_MAPPING = {"测试任务": (lambda: False, "test_step")}

    notified: list[tuple] = []
    screenshots: list[str] = []
    monkeypatch.setattr(
        daily.DailyCollectManager,
        "_notify_step_failure",
        lambda self, step, raw: notified.append((step, raw)),
    )
    monkeypatch.setattr(daily, "save_error_screenshot", lambda name: screenshots.append(name))

    def _boom(self, step_name, func, *a, **k):
        raise nav.GameNotForegroundError("游戏已不在前台")

    monkeypatch.setattr(daily.DailyCollectManager, "_run_step", _boom)

    with pytest.raises(nav.GameNotForegroundError):
        manager.execute_task("测试任务")

    assert notified == []
    assert screenshots == []
