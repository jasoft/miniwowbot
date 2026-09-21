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


def _write_dungeon_config(tmp_path: Path, name: str) -> Path:
    """写入「1 个选定副本 + 1 个已选日常任务」的最小配置。

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
        "daily_tasks": [{"name": "领取主题奖励", "selected": True}],
        "zone_dungeons": {
            "亡灵之地": [{"name": "聚魂之地", "selected": True}],
        },
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return config_path


def _make_db_class(completed_count: int, daily_collect_completed: bool = False):
    """构造返回固定完成数的数据库替身。

    Args:
        completed_count: 需要返回的已完成副本数量。
        daily_collect_completed: 每日收集的总完成标记。

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

        def is_daily_collect_completed(self) -> bool:
            """返回固定的每日收集完成标记。"""
            return daily_collect_completed

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
    # 步骤失败会走告警分支，必须打桩 —— 漏打桩会把假告警真的推给大王。
    alerts: list[str] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )

    monkeypatch.setattr(auto_dungeon_daily, "back_to_main", lambda: None)
    monkeypatch.setattr(auto_dungeon_daily, "find_text_and_click", lambda *args, **kwargs: True)
    monkeypatch.setattr(auto_dungeon_daily, "text_exists", lambda *args, **kwargs: None)

    assert manager.execute_task("领取主题奖励") is False
    fake_db.mark_daily_step_completed.assert_not_called()
    assert alerts == ["small_cookie"]


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
    monkeypatch.setattr(
        auto_dungeon_daily, "DailyCollectManager", lambda *args, **kwargs: fake_manager
    )

    assert auto_dungeon_daily.execute_daily_collect() is False
    fake_db.mark_daily_collect_completed.assert_not_called()


def test_is_config_completed_ignores_daily_tasks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """只有日常任务、没有选定副本时，配置预检查应判定为已完成。

    副本进度口径**不含**「日常任务」：日常任务里存在当天无法完成的项目
    （例如活动下线），若计入则预检查会恒判「未完成」并触发整轮重试。
    日常任务本身做没做成，由 `execute_daily_collect()` 的逐步判定 + 失败告警负责。
    """
    _write_daily_task_config(tmp_path, "warrior")
    monkeypatch.setattr(run_dungeons, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(run_dungeons, "DungeonProgressDB", _make_db_class(0))

    logger = logging.getLogger("test_run_dungeons_pending_daily")

    assert run_dungeons._is_config_completed("warrior", logger) is True


def test_is_config_completed_counts_only_dungeons(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """有选定副本时，日常任务不参与计数：副本没打完就仍算未完成。"""
    _write_dungeon_config(tmp_path, "warrior")
    monkeypatch.setattr(run_dungeons, "SCRIPT_DIR", tmp_path)

    logger = logging.getLogger("test_run_dungeons_only_dungeons")

    # 选定副本 1 个，已完成 0 个 → 未完成（日常任务完成与否不影响）
    monkeypatch.setattr(run_dungeons, "DungeonProgressDB", _make_db_class(0))
    assert run_dungeons._is_config_completed("warrior", logger) is False

    # 副本数达到 1 → 已完成
    monkeypatch.setattr(run_dungeons, "DungeonProgressDB", _make_db_class(1))
    assert run_dungeons._is_config_completed("warrior", logger) is True


def test_is_config_completed_daily_only_config_uses_daily_flag(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """没有选定副本但启用了每日收集时，以每日收集的完成标记为准。

    防止「副本数为 0 → 直接跳过」把只跑日常任务的配置整轮短路掉。
    """
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "druid.json").write_text(
        json.dumps(
            {
                "class": "德鲁伊",
                "enable_daily_collect": True,
                "daily_tasks": [{"name": "领取主题奖励", "selected": True}],
                "zone_dungeons": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_dungeons, "SCRIPT_DIR", tmp_path)
    logger = logging.getLogger("test_run_dungeons_daily_only")

    # 每日收集未完成 → 仍需执行
    monkeypatch.setattr(
        run_dungeons,
        "DungeonProgressDB",
        _make_db_class(0, daily_collect_completed=False),
    )
    assert run_dungeons._is_config_completed("druid", logger) is False

    # 每日收集已完成 → 跳过
    monkeypatch.setattr(
        run_dungeons,
        "DungeonProgressDB",
        _make_db_class(0, daily_collect_completed=True),
    )
    assert run_dungeons._is_config_completed("druid", logger) is True


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


# 真机实测的券价布局：行0=40(紫)、行1=30(蓝)、行2=30、行3=20、行4=50
_EXCHANGE_LAYOUT_TAIL: tuple[int, ...] = (30, 20, 50)


def _pad_exchange_states(states):
    """把行状态补足到真机布局的 5 行。

    兑换流程会校验「读到的行数 == 页面实际行数」，行数不足会被判成
    OCR 漏检导致行序错位、整轮跳过。所以夹具不能只给前两行。
    补齐的行券价取真机观测值，且不会被当作兑换目标。

    Args:
        states: 至少要包含行序 0 与 1 的行状态。

    Returns:
        list[EventExchangeItemState]: 补齐到 5 行的行状态。
    """
    padded = list(states)
    for index in range(len(padded), 5):
        padded.append(
            _make_exchange_state(
                item_key=f"row_{index}",
                row_index=index,
                required_tickets=_EXCHANGE_LAYOUT_TAIL[index - 2],
                current_tickets=0,
                button_center=(300, 400 + 120 * index),
            )
        )
    return padded


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
        lambda: _pad_exchange_states(
            [
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
            ]
        ),
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
        lambda: _pad_exchange_states(
            [
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
            ]
        ),
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
        lambda: _pad_exchange_states(
            [
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
            ]
        ),
    )

    bought_items = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: bought_items.append(state.item_key) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is False
    assert bought_items == []
