"""「领取主题奖励」重试打开活动面板的回归测试。

背景（2026-10-27 06:02 真机）：OCR 把右侧「活动」图标与旁边一条聊天飘字框成
**同一个**检测框（``text='暴击：（;)活动'``、``center=(585, 235)``），而该图标
10-16~10-26 十天真机坐标稳定在 ``(667~671, 234~235)``。旧实现直接点框中心 →
偏了 84 像素 → 面板没打开 → 「未识别到目标活动卡片」→ 整个「领取主题奖励」判失败，
当天的券兑换被一并跳过。

本测试锁三条不变量：

1. **行为**：首读无卡片时，必须重试打开面板；重试命中卡片后步骤应判成功。
2. **落点**：重试必须点「干净」的框（文本恰好是「活动」/框最窄），不能再用被污染的
   大框中心。
3. **机制**：重试次数有上限，不会无限点。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import auto_dungeon_daily

# 真机 2026-10-27 的污染框：文本与中心的原样摘录。
POLLUTED_ENTRY = {
    "text": "暴击：（;)活动",
    "center": (585, 235),
    "confidence": 0.93,
    "bbox": [[300, 220], [640, 220], [640, 250], [300, 250]],
}
# 同一时刻的干净框：坐标取自 10-16~10-26 十天真机稳定值。
CLEAN_ENTRY = {
    "text": "活动",
    "center": (669, 234),
    "confidence": 0.99,
    "bbox": [[650, 220], [690, 220], [690, 250], [650, 250]],
}
CARD = {"text": "狗头人世界", "center": (548, 544), "confidence": 0.999}


def _make_manager() -> auto_dungeon_daily.DailyCollectManager:
    """构造一个只跑主题奖励流程的 manager。

    Returns:
        绑定了假 db 的 DailyCollectManager 实例。
    """
    fake_db = MagicMock()
    fake_db.is_daily_step_completed.return_value = False
    return auto_dungeon_daily.DailyCollectManager(config_loader=MagicMock(), db=fake_db)


def _claim_event_rewards_without_retry_support(
    manager: auto_dungeon_daily.DailyCollectManager,
) -> bool:
    """调用主题奖励步骤，并把「旧实现没有重试路径」归一成业务失败。

    反证（撤回生产改动）时，旧实现没有 ``_reopen_activity_panel``，会抛
    ``AttributeError`` —— 那是**打桩目标不存在**的机械失败，证明不了「行为确实缺失」。
    这里把它折算成「步骤判失败」，让反证落在下面的 ``is True`` 行为断言上。

    Args:
        manager: DailyCollectManager 实例。

    Returns:
        步骤返回值；旧实现缺少重试路径时返回 False。
    """
    try:
        return manager._claim_event_rewards()
    except AttributeError:
        return False


def _stub_flow(monkeypatch, manager, text_exists_results, find_all_results, touched):
    """把主题奖励流程里除「找活动卡片」以外的动作全部打桩。

    Args:
        monkeypatch: pytest 的 monkeypatch。
        manager: DailyCollectManager 实例。
        text_exists_results: ``text_exists`` 依次返回的结果。
        find_all_results: ``find_all_texts`` 依次返回的结果。
        touched: 记录 touch 坐标的列表。
    """
    text_exists_calls = {"count": 0}

    def fake_text_exists(*args, **kwargs):
        index = min(text_exists_calls["count"], len(text_exists_results) - 1)
        text_exists_calls["count"] += 1
        return text_exists_results[index]

    find_all_calls = {"count": 0}

    def fake_find_all_texts(*args, **kwargs):
        index = min(find_all_calls["count"], len(find_all_results) - 1)
        find_all_calls["count"] += 1
        return find_all_results[index]

    monkeypatch.setattr(auto_dungeon_daily, "back_to_main", lambda: None)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        lambda *args, **kwargs: POLLUTED_ENTRY,
    )
    monkeypatch.setattr(auto_dungeon_daily, "text_exists", fake_text_exists)
    monkeypatch.setattr(auto_dungeon_daily, "find_all_texts", fake_find_all_texts)
    monkeypatch.setattr(auto_dungeon_daily, "find_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda pos: touched.append(pos))
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_dungeon_daily, "send_notification", lambda *args, **kwargs: None)

    monkeypatch.setattr(manager, "_donate_event_materials", lambda pos: True)
    monkeypatch.setattr(manager, "_claim_event_chest_reward", lambda: True)
    monkeypatch.setattr(manager, "_open_exchange_tab", lambda: [])
    monkeypatch.setattr(manager, "_redeem_fire_tower_ticket_items", lambda states: False)

    return text_exists_calls, find_all_calls


def test_retry_after_polluted_entry_reaches_clean_entry(monkeypatch) -> None:
    """首读无卡片时必须重试，且重试落点要用干净框（不是被污染的大框中心）。"""
    manager = _make_manager()
    touched: list = []
    text_exists_calls, _ = _stub_flow(
        monkeypatch,
        manager,
        text_exists_results=[None, CARD],
        find_all_results=[[POLLUTED_ENTRY, CLEAN_ENTRY]],
        touched=touched,
    )

    assert _claim_event_rewards_without_retry_support(manager) is True
    # 机制：确实重新查过卡片（不是首读失败就收手）
    assert text_exists_calls["count"] >= 2
    # 行为：落点必须是干净框；污染框中心不应再被点到
    assert (669, 234) in touched
    assert (585, 235) not in touched


def test_retry_is_bounded_when_no_entry_found(monkeypatch) -> None:
    """重试找不到入口时必须有界退出（不无限点），并判定步骤失败。"""
    manager = _make_manager()
    touched: list = []
    text_exists_calls, find_all_calls = _stub_flow(
        monkeypatch,
        manager,
        text_exists_results=[None],
        find_all_results=[[]],
        touched=touched,
    )

    assert _claim_event_rewards_without_retry_support(manager) is False
    assert find_all_calls["count"] == 1
    assert text_exists_calls["count"] == 1
    assert touched == []


def test_retry_attempts_never_exceed_budget(monkeypatch) -> None:
    """重试点击次数不得超过预算（防止有人改成无限重试）。"""
    manager = _make_manager()
    touched: list = []
    _stub_flow(
        monkeypatch,
        manager,
        text_exists_results=[None],
        find_all_results=[[CLEAN_ENTRY]],
        touched=touched,
    )

    assert _claim_event_rewards_without_retry_support(manager) is False
    retry_clicks = [pos for pos in touched if pos == CLEAN_ENTRY["center"]]
    assert 1 <= len(retry_clicks) <= auto_dungeon_daily.ACTIVITY_PANEL_RETRY_ATTEMPTS


def test_prefer_exact_text_then_narrow_box() -> None:
    """入口选择：文本恰好等于「活动」优先；同等文本取框最窄的那个。"""
    manager = _make_manager()
    # 旧实现没有这个度量，取默认值 inf → 下面的断言会以行为不符失败（非机械失败）
    bbox_width = getattr(manager, "_bbox_width", lambda element: float("inf"))
    assert bbox_width(CLEAN_ENTRY) == 40.0
    assert bbox_width({}) == float("inf")

    candidates = [
        {"text": "暴击：（;)活动", "center": (585, 235), "bbox": [[300, 0], [640, 0]]},
        {"text": "活动", "center": (500, 100), "bbox": [[480, 0], [560, 0]]},
        {"text": "活动", "center": (669, 234), "bbox": [[650, 0], [690, 0]]},
    ]
    ordered = sorted(
        candidates,
        key=lambda item: (
            (item.get("text") or "").strip() != "活动",
            bbox_width(item),
        ),
    )
    assert ordered[0]["center"] == (669, 234)
