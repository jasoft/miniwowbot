"""每日任务回归测试。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import auto_dungeon_daily
import run_dungeons


def _write_daily_task_config(tmp_path: Path, name: str) -> Path:
    """写入仅包含日常任务的最小配置。

    Args:
        tmp_path: 临时目录根路径。
        name: 配置名（不含扩展名）。

    Returns:
        生成的配置文件路径。
    """
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{name}.json"
    payload = {
        "class": "战士",
        "daily_tasks": [
            {"name": "领取主题奖励", "selected": True},
        ],
        "zone_dungeons": {},
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return config_path


def _make_db_class(completed_count: int):
    """构造返回固定完成数的数据库替身。

    Args:
        completed_count: 需要返回的已完成数量。

    Returns:
        模拟的数据库类。
    """

    class DummyDB:
        """用于预检查逻辑的数据库替身。"""

        def __init__(
            self,
            config_name: str,
            db_path: str = "database/dungeon_progress.db",
        ):
            self.config_name = config_name
            self.db_path = db_path

        def cleanup_old_records(self, days_to_keep: int = 7) -> None:
            """模拟清理旧记录。"""
            return None

        def get_today_completed_count(self, include_special: bool = False) -> int:
            """返回固定的已完成数量。"""
            return completed_count

        def __enter__(self) -> "DummyDB":
            """进入上下文。"""
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            """退出上下文。"""
            return None

    return DummyDB


def test_execute_task_event_rewards_missing_entry_does_not_mark_step(monkeypatch) -> None:
    """未找到活动入口时，不应把主题奖励步骤记录为完成。"""
    fake_db = MagicMock()
    fake_db.is_daily_step_completed.return_value = False
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )

    monkeypatch.setattr(auto_dungeon_daily, "back_to_main", lambda: None)
    monkeypatch.setattr(auto_dungeon_daily, "find_text_and_click", lambda *args, **kwargs: True)
    monkeypatch.setattr(auto_dungeon_daily, "text_exists", lambda *args, **kwargs: None)

    assert manager.execute_task("领取主题奖励") is False
    fake_db.mark_daily_step_completed.assert_not_called()


def test_execute_daily_collect_incomplete_run_does_not_mark_finished(monkeypatch) -> None:
    """整套每日收集未全部成功时，不应写入总完成标记。"""
    fake_container = MagicMock()
    fake_container.config_loader.get_config_name.return_value = "warrior"
    monkeypatch.setattr(auto_dungeon_daily, "get_container", lambda: fake_container)

    fake_db = MagicMock()
    fake_db.is_daily_collect_completed.return_value = False
    fake_db.__enter__.return_value = fake_db
    fake_db.__exit__.return_value = None

    fake_manager = MagicMock()
    fake_manager.collect_daily_rewards.return_value = False

    monkeypatch.setattr("database.DungeonProgressDB", lambda config_name: fake_db)
    monkeypatch.setattr(auto_dungeon_daily, "DailyCollectManager", lambda *args, **kwargs: fake_manager)

    assert auto_dungeon_daily.execute_daily_collect() is False
    fake_db.mark_daily_collect_completed.assert_not_called()


def test_is_config_completed_returns_false_when_daily_task_pending(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """仅剩未完成日常任务时，配置预检查仍应判定为未完成。"""
    _write_daily_task_config(tmp_path, "warrior")
    monkeypatch.setattr(run_dungeons, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(run_dungeons, "DungeonProgressDB", _make_db_class(0))

    logger = logging.getLogger("test_run_dungeons_pending_daily")

    assert run_dungeons._is_config_completed("warrior", logger) is False


def _make_exchange_state(
    *,
    item_key: str,
    row_index: int,
    required_tickets: int,
    current_tickets: int | None,
    button_center: tuple[int, int] = (320, 640),
    is_affordable_by_color: bool | None = True,
):
    """构造兑换状态测试数据。"""
    return auto_dungeon_daily.EventExchangeItemState(
        row_index=row_index,
        item_key=item_key,
        required_tickets=required_tickets,
        current_tickets=current_tickets,
        button_center=button_center,
        is_affordable_by_color=is_affordable_by_color,
    )


def test_redeem_fire_tower_ticket_items_buys_purple_item_first(monkeypatch) -> None:
    """第一件可买时，应优先兑换紫色物品。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )

    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [
            _make_exchange_state(
                item_key="purple_first",
                row_index=0,
                required_tickets=40,
                current_tickets=40,
                button_center=(300, 400),
            ),
            _make_exchange_state(
                item_key="blue_second",
                row_index=1,
                required_tickets=30,
                current_tickets=20,
                button_center=(300, 520),
            ),
        ],
    )

    bought_items = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: bought_items.append(state.item_key) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is True
    assert bought_items == ["purple_first"]


def test_redeem_fire_tower_ticket_items_buys_blue_after_purple_completed(
    monkeypatch,
) -> None:
    """第一件已购后，第二件可买时应只兑换第二件。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.side_effect = (
        lambda event_name, item_key, cycle_id=None: item_key == "purple_first"
    )
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )

    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [
            _make_exchange_state(
                item_key="purple_first",
                row_index=0,
                required_tickets=40,
                current_tickets=0,
                button_center=(300, 400),
            ),
            _make_exchange_state(
                item_key="blue_second",
                row_index=1,
                required_tickets=30,
                current_tickets=30,
                button_center=(300, 520),
            ),
        ],
    )

    bought_items = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: bought_items.append(state.item_key) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is True
    assert bought_items == ["blue_second"]


def test_redeem_fire_tower_ticket_items_does_not_skip_unbought_purple_item(
    monkeypatch,
) -> None:
    """第一件未买且不可买时，不应越过它去买第二件。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )

    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [
            _make_exchange_state(
                item_key="purple_first",
                row_index=0,
                required_tickets=40,
                current_tickets=20,
                button_center=(300, 400),
            ),
            _make_exchange_state(
                item_key="blue_second",
                row_index=1,
                required_tickets=30,
                current_tickets=30,
                button_center=(300, 520),
            ),
        ],
    )

    bought_items = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: bought_items.append(state.item_key) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is False
    assert bought_items == []
