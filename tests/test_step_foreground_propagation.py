"""日常任务各 step 不得把 ``GameNotForegroundError`` 降级成普通失败。

背景（2026-09-26 06:07:41 mage_alt 实测）：

实例里的「应用宝」(``com.tencent.android.qqdownloader``) 的
``GarbageCleanActivity`` 抢到前台，``back_to_main`` 的守卫正确探测到并抛出
``GameNotForegroundError``。``execute_task`` 已在 2026-09-25 放行这个异常
（见 ``test_back_to_main_foreground_guard.py``），但**各 step 方法内部的
``except Exception`` 会先一步把它捕获**，于是：

- 日志把它记成「未找到商店: back_to_main 中止…」，与真实原因无关；
- 还多调一次注定失败的 ``back_to_main()``（实测白等 0.7 秒）；
- ``_claim_event_rewards`` 更糟：它会据此发出「兑换碎片失败, 请立即检查」
  的**误报告警**，把「游戏被别的 app 顶掉了」说成「兑换失败」。

本文件锁定：``GameNotForegroundError`` 必须从 step 方法**直接冒泡**，
由 ``execute_task`` → ``main_wrapper`` 统一走「重启游戏」恢复路径。
"""

from __future__ import annotations

import pytest

import auto_dungeon_daily as daily
import auto_dungeon_navigation as nav


def _install_back_to_main_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_at: int = 2,
) -> list[int]:
    """替换 ``back_to_main``：第 ``fail_at`` 次调用抛前台异常，其余正常返回。

    各 step 方法都是「try 之前先回一次主界面，try 内再回一次」的结构，
    因此 ``fail_at=2`` 正好命中 **try 块内** 的那次调用 —— 这才是会被
    ``except Exception`` 吞掉的路径。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        fail_at: 第几次调用抛 ``GameNotForegroundError``（从 1 开始计数）。

    Returns:
        list[int]: 调用次数累加器，长度即调用次数。
    """
    calls: list[int] = []

    def _stub(*args: object, **kwargs: object) -> None:
        calls.append(len(calls) + 1)
        if len(calls) == fail_at:
            raise nav.GameNotForegroundError("游戏已不在前台")

    monkeypatch.setattr(daily, "back_to_main", _stub)
    return calls


def _stub_io(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    """把 step 方法用到的设备动作统统替换成无副作用的桩。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        **overrides: 需要覆盖默认桩的符号名 → 替代实现。
    """
    defaults: dict[str, object] = {
        "touch": lambda *a, **k: None,
        "sleep": lambda *a, **k: None,
        "find_text_and_click": lambda *a, **k: None,
        "find_text_and_click_safe": lambda *a, **k: False,
        "find_text": lambda *a, **k: None,
        "text_exists": lambda *a, **k: None,
        "switch_to": lambda *a, **k: None,
        "open_map": lambda *a, **k: None,
        "send_notification": lambda *a, **k: None,
    }
    defaults.update(overrides)
    for name, impl in defaults.items():
        monkeypatch.setattr(daily, name, impl)


# ====== 标准 step：try 块内的前台异常必须冒泡 ======


def test_demonhunter_exam_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """猎魔试炼：入口找不到时那次 ``back_to_main`` 抛异常，须原样上抛。"""
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)

    with pytest.raises(nav.GameNotForegroundError):
        manager._demonhunter_exam()

    assert len(calls) == 2, "异常后不该再补一次注定失败的 back_to_main"


def test_soul_tower_signin_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """灵魂之塔签到：面板打不开时那次 ``back_to_main`` 抛异常，须原样上抛。"""
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)
    monkeypatch.setattr(daily.DailyCollectManager, "_enter_soul_tower_panel", lambda self: False)

    with pytest.raises(nav.GameNotForegroundError):
        manager._soul_tower_signin()

    assert len(calls) == 2


def test_collect_idle_rewards_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """挂机奖励：找不到「战斗」入口时那次 ``back_to_main`` 抛异常，须原样上抛。"""
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)

    with pytest.raises(nav.GameNotForegroundError):
        manager._collect_idle_rewards()

    assert len(calls) == 2


def test_kill_world_boss_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """世界BOSS：未能切入「东部大陆」时那次 ``back_to_main`` 抛异常，须原样上抛。"""
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)

    with pytest.raises(nav.GameNotForegroundError):
        manager._kill_world_boss()

    assert len(calls) == 2


def test_buy_market_items_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """商店每日：未能进入「商店」时那次 ``back_to_main`` 抛异常，须原样上抛。

    这正是 2026-09-26 06:07 真机踩到的路径 —— 旧实现把它记成
    「未找到商店」，与「游戏被应用宝顶到后台」毫无关系。
    """
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)

    with pytest.raises(nav.GameNotForegroundError):
        manager._buy_market_items()

    assert len(calls) == 2


def test_open_chests_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开启宝箱：未能进入「宝库」时那次 ``back_to_main`` 抛异常，须原样上抛。"""
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)

    with pytest.raises(nav.GameNotForegroundError):
        manager._open_chests("亡灵宝箱")

    assert len(calls) == 2


def test_receive_mails_propagates_foreground_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """领取邮件：收尾那次 ``back_to_main`` 抛异常，须原样上抛。"""
    manager = daily.DailyCollectManager()
    calls = _install_back_to_main_stub(monkeypatch)
    _stub_io(monkeypatch)
    monkeypatch.setattr(
        daily.DailyCollectManager, "_locate_mail_claim_button", lambda self: (359, 879)
    )

    with pytest.raises(nav.GameNotForegroundError):
        manager._receive_mails()

    assert len(calls) == 2


# ====== _claim_event_rewards：前台异常 ≠ 兑换失败 ======


def test_claim_event_rewards_does_not_report_exchange_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """兑换环节遇到前台异常时不得发出「兑换碎片失败」误报告警。"""
    manager = daily.DailyCollectManager()
    notified: list[tuple] = []

    _install_back_to_main_stub(monkeypatch, fail_at=99)  # 本用例的 back_to_main 不是主角
    _stub_io(
        monkeypatch,
        find_text_and_click_safe=lambda *a, **k: True,
        text_exists=lambda *a, **k: {"center": (359, 879)},
        send_notification=lambda *a, **k: notified.append(a),
    )
    monkeypatch.setattr(
        daily.DailyCollectManager, "_summarize_match_result", lambda self, r: "stub"
    )
    monkeypatch.setattr(
        daily.DailyCollectManager, "_donate_event_materials", lambda self, center: True
    )
    monkeypatch.setattr(daily.DailyCollectManager, "_claim_event_chest_reward", lambda self: True)
    monkeypatch.setattr(daily.DailyCollectManager, "_open_exchange_tab", lambda self: {})

    def _boom(self, tab_states):
        raise nav.GameNotForegroundError("游戏已不在前台")

    monkeypatch.setattr(daily.DailyCollectManager, "_redeem_fire_tower_ticket_items", _boom)

    with pytest.raises(nav.GameNotForegroundError):
        manager._claim_event_rewards()

    assert notified == [], f"不该发出与真实原因无关的告警: {notified}"
