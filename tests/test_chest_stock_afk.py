"""领宝箱前「存量不足则挂机补充」的回归测试。

覆盖 2026-10-12 真机新增需求：宝箱存量只在**野外挂机**时增长，
而每日任务跑完就下线，存量长期不涨 → 连着几天就把存量领空，
每天开不满 30 个（面板底部「今日开启数量 30/30」即每日上限）。

本文件锁三件事：

1. **存量必须以宝箱名为锚点读**。宝库面板里 9 个宝箱各有一行形如
   「504/5」的存量，只按"第一个 x/y"会读到别的格子 —— 真机实测把
   军团宝箱的 422 当成了亡灵宝箱的存量。
2. **先补后领**：领之前补存量，顺序反了会把刚补的存量花掉。
3. **读不到存量时不盲挂**：挂半小时的代价远大于少领一次。

另锁一条硬约束：挂机的静默上限远大于编排器看门狗阈值
（``cron_run_all_dungeons.LOG_IDLE_TIMEOUT_SECONDS`` = 180），
因此等待必须分段+ 打心跳，否则半小时静默会被判僵死并连模拟器一起重启。
"""

from __future__ import annotations

from typing import Any

import pytest

import auto_dungeon_daily

WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS = 180

# 真机宝库面板OCR 结果（2026-10-12 实测，坐标为中心点）。
# 亡灵宝箱在右下格，存量 504；军团宝箱在左下格，存量 422 —— 两者存量行
# 的纵坐标完全相同，只有横坐标不同，这正是"按顺序取第一个"会取错的原因。
VAULT_PANEL_TEXTS = [
    {"text": "宝库", "center": (359, 220), "confidence": 1.0},
    {"text": "大陆宝箱", "center": (169, 451), "confidence": 1.0},
    {"text": "501/5", "center": (169, 484), "confidence": 0.969},
    {"text": "军团宝箱", "center": (168, 870), "confidence": 0.999},
    {"text": "422/5", "center": (168, 904), "confidence": 0.985},
    {"text": "风暴宝箱", "center": (359, 871), "confidence": 0.999},
    {"text": "503/5", "center": (359, 904), "confidence": 0.982},
    {"text": "亡灵宝箱", "center": (549, 870), "confidence": 0.997},
    {"text": "504/5", "center": (550, 904), "confidence": 0.976},
]


def _make_manager(monkeypatch, texts=None, vault_ok=True):
    """构造一个注入好假OCR 文本的 ``DailyCollectManager``。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        texts: 假 OCR 文本列表；None 表示不进宝库。
        vault_ok: 「主城」→「宝库」两步入口是否都能点中。

    Returns:
        tuple: ``(manager, calls)``，``calls`` 记录所有关键调用。
    """
    calls: dict[str, Any] = {"back_to_main": 0, "clicks": [], "afk_seconds": []}

    def fake_find_and_click(text, **kwargs):
        calls["clicks"].append(text)
        if text == "宝库":
            return vault_ok
        return True

    def fake_back_to_main(*args, **kwargs):
        calls["back_to_main"] += 1

    monkeypatch.setattr(auto_dungeon_daily, "find_text_and_click_safe", fake_find_and_click)
    monkeypatch.setattr(auto_dungeon_daily, "back_to_main", fake_back_to_main)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_all_texts",
        lambda *a, **k: [] if texts is None else list(texts),
    )
    monkeypatch.setattr(
        auto_dungeon_daily,
        "sleep",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        auto_dungeon_daily,
        "is_game_foreground",
        lambda *a, **k: True,
    )
    return auto_dungeon_daily.DailyCollectManager(), calls


def test_read_chest_stock_anchors_on_chest_name(monkeypatch):
    """存量必须按宝箱名锚点读，而不是取面板里第一个 x/y。"""
    manager, _ = _make_manager(monkeypatch, texts=VAULT_PANEL_TEXTS)

    assert manager._read_chest_stock("亡灵宝箱") == 504
    assert manager._read_chest_stock("军团宝箱") == 422


def test_read_chest_stock_returns_none_when_vault_unreachable(monkeypatch):
    """进不去宝库时返回 None（读不到），不能当成存量为 0。"""
    manager, _ = _make_manager(monkeypatch, texts=None, vault_ok=False)

    assert manager._read_chest_stock("亡灵宝箱") is None


def test_read_chest_stock_returns_none_when_chest_absent(monkeypatch):
    """宝库里没有该宝箱时返回 None，而不是误读别的格子。"""
    texts = [t for t in VAULT_PANEL_TEXTS if t["text"] != "亡灵宝箱"]
    manager, _ = _make_manager(monkeypatch, texts=texts)

    assert manager._read_chest_stock("亡灵宝箱") is None


def test_no_afk_when_stock_above_target(monkeypatch):
    """存量已达目标时不挂机。"""
    manager, calls = _make_manager(monkeypatch, texts=VAULT_PANEL_TEXTS)
    afked: list[int] = []
    monkeypatch.setattr(
        manager,
        "_afk_for_chest_stock",
        lambda seconds=0: afked.append(seconds),
    )

    manager._ensure_chest_stock("亡灵宝箱")

    assert afked == []


def test_afk_then_recheck_when_stock_below_target(monkeypatch):
    """存量不足目标时先挂机再复读，且挂机时长来自配置常量。"""
    texts = [
        t if t["text"] != "504/5" else {"text": "150/5", "center": (550, 904), "confidence": 0.97}
        for t in VAULT_PANEL_TEXTS
    ]
    manager, calls = _make_manager(monkeypatch, texts=texts)
    afked: list[int] = []
    monkeypatch.setattr(
        manager,
        "_afk_for_chest_stock",
        lambda seconds=0: afked.append(seconds),
    )

    manager._ensure_chest_stock("亡灵宝箱")

    assert afked == [auto_dungeon_daily.CHEST_AFK_SECONDS]
    # 先补后领：读存量发生在挂机之前
    assert calls["back_to_main"] >= 1


def test_no_blind_afk_when_stock_unknown(monkeypatch):
    """读不到存量时只告警、不盲挂 —— 挂半小时的代价远大于少领一次。"""
    manager, _ = _make_manager(monkeypatch, texts=None, vault_ok=False)
    afked: list[int] = []
    monkeypatch.setattr(
        manager,
        "_afk_for_chest_stock",
        lambda seconds=0: afked.append(seconds),
    )

    manager._ensure_chest_stock("亡灵宝箱")

    assert afked == []


def test_open_chests_supplements_before_opening(monkeypatch):
    """``_open_chests`` 必须先补存量，再走原有的开箱流程。"""
    manager, calls = _make_manager(monkeypatch, texts=VAULT_PANEL_TEXTS)
    order: list[str] = []
    monkeypatch.setattr(
        manager,
        "_ensure_chest_stock",
        lambda chest_name: order.append(f"ensure:{chest_name}"),
    )
    # 开箱流程的后续动作：入口点击 + 「开启10次」查找
    monkeypatch.setattr(auto_dungeon_daily, "find_text", lambda *a, **k: None)

    result = manager._open_chests("亡灵宝箱")

    assert order == ["ensure:亡灵宝箱"], "开箱前必须先补存量"
    assert calls["clicks"][:3] == ["主城", "宝库", "亡灵宝箱"], (
        f"补完存量后应照常走原开箱链路，实际点击序列={calls['clicks']}"
    )
    # 读不到「开启10次」时开箱返回 False，但补充动作已经发生
    assert result is False


def test_afk_heartbeat_below_watchdog_threshold():
    """挂机心跳与轮询片长必须显著小于看门狗阈值，否则半小时静默必被误杀。"""
    heartbeat = auto_dungeon_daily.CHEST_AFK_HEARTBEAT_SECONDS
    poll = auto_dungeon_daily.CHEST_AFK_POLL_SECONDS

    assert heartbeat < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"心跳间隔 {heartbeat}s 不小于看门狗阈值 "
        f"{WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS}s，挂机会被判僵死并重启模拟器。"
    )
    assert poll < WATCHDOG_LOG_IDLE_TIMEOUT_SECONDS, (
        f"轮询片长 {poll}s 不小于看门狗阈值，"
        f"单片就足以让看门狗看不到心跳。"
    )


def test_afk_emits_heartbeat_logs(monkeypatch, caplog):
    """挂机期间必须持续输出心跳日志，否则看门狗会误判僵死。"""
    manager, _ = _make_manager(monkeypatch)
    now = {"t": 0.0}

    def fake_sleep(seconds, reason=""):
        now["t"] += seconds

    monkeypatch.setattr(auto_dungeon_daily, "sleep", fake_sleep)
    monkeypatch.setattr(auto_dungeon_daily, "is_game_foreground", lambda *a, **k: True)
    monkeypatch.setattr(auto_dungeon_daily.time, "time", lambda: now["t"])

    with caplog.at_level("INFO"):
        manager._afk_for_chest_stock(600)

    beats = [r for r in caplog.records if "挂机中" in r.getMessage()]
    assert beats, (
        "挂机期间没有任何心跳日志 —— 看门狗把会话日志 180 秒不动判成僵死，"
        "会杀掉会话并重启模拟器。"
    )


def test_afk_aborts_when_game_left_foreground(monkeypatch):
    """挂机期间游戏被顶到后台必须立刻中止，而不是空等半小时。"""
    manager, _ = _make_manager(monkeypatch)
    now = {"t": 0.0}
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *a, **k: now.__setitem__("t", now["t"] + (a[0] if a else 0)))
    monkeypatch.setattr(auto_dungeon_daily.time, "time", lambda: now["t"])
    monkeypatch.setattr(auto_dungeon_daily, "is_game_foreground", lambda *a, **k: False)

    with pytest.raises(auto_dungeon_daily.GameNotForegroundError):
        manager._afk_for_chest_stock(600)


def test_read_chest_stock_bypasses_ocr_similar_cache(monkeypatch):
    """读存量必须绕过 OCR 相似缓存，否则挂机后的复读会拿到挂机前的旧数字。

    真机背景（2026-10-19）：挂机 1800 秒后复读，日志记「270 → 270」，
    同时 `output/cache/cache.db` 里那条宝库面板条目 06:27:07 创建、
    06:57:15 被再次命中（hit_count 1→2、没有新增条目）——第二次读根本没
    重新识别，直接返回了半小时前的 OCR 结果。原因是 `find_all` 默认
    `use_cache=True`，而 OCR 缓存按**整屏 dhash 汉明距离 ≤10** 判同一张图，
    同一个宝库面板只改了几位数字，距离远小于阈值。
    """
    stale = [
        {"text": "亡灵宝箱", "center": (549, 870), "confidence": 0.997},
        {"text": "270/5", "center": (550, 904), "confidence": 0.976},
    ]
    fresh = [
        {"text": "亡灵宝箱", "center": (549, 870), "confidence": 0.997},
        {"text": "410/5", "center": (550, 904), "confidence": 0.976},
    ]
    seen: list[dict[str, Any]] = []

    def fake_find_all_texts(*args, **kwargs):
        seen.append(dict(kwargs))
        # 复现真机语义：允许用缓存时会拿到旧截图的结果
        return list(fresh) if kwargs.get("use_cache") is False else list(stale)

    manager, _ = _make_manager(monkeypatch, texts=stale)
    monkeypatch.setattr(auto_dungeon_daily, "find_all_texts", fake_find_all_texts)

    assert manager._read_chest_stock("亡灵宝箱") == 410, (
        "存量被 OCR 相似缓存顶成了旧值 —— 挂机会白烧 30 分钟且看不出原因"
    )
    assert seen and seen[0].get("use_cache") is False, "存量读取必须显式 use_cache=False"


def test_zero_growth_after_afk_logs_warning(monkeypatch, caplog):
    """挂机后存量一点没涨必须显式告警，别让这 30 分钟白烧得无声无息。"""
    manager, _ = _make_manager(monkeypatch)
    reads = [270, 270]
    monkeypatch.setattr(manager, "_read_chest_stock", lambda _name: reads.pop(0))
    monkeypatch.setattr(manager, "_afk_for_chest_stock", lambda seconds=0: None)

    with caplog.at_level("WARNING", logger="auto_dungeon_daily"):
        manager._ensure_chest_stock("亡灵宝箱")

    assert any("存量未增长" in record.getMessage() for record in caplog.records), (
        f"零增长时没有任何告警，实际日志={[r.getMessage() for r in caplog.records]}"
    )
