"""副本剩余计数的口径回归测试。

「日常任务」是 ``config_loader`` 从 ``daily_tasks`` 合成并并入 ``zone_dungeons``
的伪区域，只为了让执行流程能遍历到它，**它不是副本**。2026-10-27 真机：
副本 11/11 全部通关，但因为一个日常步骤（``small_cookie``）失败，
``count_remaining_selected_dungeons`` 数出「仍有 1 个副本未完成」，
打出「准备继续 / 已达到最大轮数，仍有 1 个副本未完成」两条误导性告警。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import auto_dungeon_core
from database.dungeon_db import DAILY_TASK_ZONE_NAME


class _FakeConfigLoader:
    """只提供两个区域视图的假配置加载器。"""

    def __init__(self) -> None:
        """初始化区域数据。"""
        self.zones = {
            "亡灵之地": [
                {"name": "聚魂之地", "selected": True},
                {"name": "永恒王座", "selected": True},
                {"name": "黑石熔炉", "selected": False},
            ],
            DAILY_TASK_ZONE_NAME: [
                {"name": "领取主题奖励", "selected": True},
            ],
        }

    def get_zone_dungeons(self) -> dict:
        """返回**含**「日常任务」的执行用视图。

        Returns:
            区域 -> 条目列表。
        """
        return self.zones

    def get_dungeon_zones(self) -> dict:
        """返回**不含**「日常任务」的副本口径视图。

        Returns:
            区域 -> 条目列表。
        """
        return {zone: items for zone, items in self.zones.items() if zone != DAILY_TASK_ZONE_NAME}


def _fake_container() -> object:
    """构造只有 config_loader 的容器替身。

    Returns:
        带 ``config_loader`` 属性的对象。
    """
    container = MagicMock()
    container.config_loader = _FakeConfigLoader()
    return container


def _fake_db(daily_completed: bool) -> MagicMock:
    """构造按区域区分完成状态的假进度库。

    Args:
        daily_completed: 日常任务是否已判定完成。

    Returns:
        MagicMock 形式的 ProgressDB。
    """

    def is_completed(zone_name: str, dungeon_name: str) -> bool:
        if zone_name == DAILY_TASK_ZONE_NAME:
            return daily_completed
        return True

    db = MagicMock()
    db.is_dungeon_completed.side_effect = is_completed
    return db


def test_remaining_count_excludes_daily_tasks(monkeypatch) -> None:
    """日常任务未完成时，副本剩余数必须是 0（改前会误报 1）。"""
    monkeypatch.setattr(auto_dungeon_core, "_container", _fake_container())

    assert auto_dungeon_core.count_remaining_selected_dungeons(_fake_db(False)) == 0


def test_remaining_count_still_counts_real_dungeons(monkeypatch) -> None:
    """真副本未完成时必须照旧数出来，口径修正不能把真问题一起漏掉。"""
    monkeypatch.setattr(auto_dungeon_core, "_container", _fake_container())
    db = MagicMock()
    db.is_dungeon_completed.return_value = False

    # 2 个 selected 副本（第 3 个 selected=False 不计）+ 1 个日常任务
    assert auto_dungeon_core.count_remaining_selected_dungeons(db) == 2


def test_incomplete_daily_tasks_counted_separately(monkeypatch) -> None:
    """未完成的日常任务要单独统计，作为「今天有步骤没做成」的总账。"""
    monkeypatch.setattr(auto_dungeon_core, "_container", _fake_container())
    # 旧实现没有这个函数，取默认值 -1 → 断言以行为不符失败（非机械失败）
    count_incomplete = getattr(auto_dungeon_core, "count_incomplete_daily_tasks", lambda db: -1)

    assert count_incomplete(_fake_db(False)) == 1
    assert count_incomplete(_fake_db(True)) == 0
