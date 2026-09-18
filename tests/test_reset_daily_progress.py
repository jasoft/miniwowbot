"""`scripts/reset_daily_progress.py` 的核心逻辑测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from database.dungeon_db import DungeonProgress, db as progress_db
from scripts import reset_daily_progress as rdp


def _init_temp_db(db_path: Path) -> None:
    """把全局 peewee 连接指向临时库并建表。

    Args:
        db_path: 临时数据库文件路径。

    Returns:
        None.
    """
    if not progress_db.is_closed():
        progress_db.close()
    progress_db.init(str(db_path))
    progress_db.connect()
    progress_db.create_tables([DungeonProgress], safe=True)


def _insert(config_name: str, date: str, zone_name: str, dungeon_name: str) -> None:
    """插入一条已完成记录。

    Args:
        config_name: 配置名。
        date: 逻辑日期。
        zone_name: 区域名。
        dungeon_name: 副本名。

    Returns:
        None.
    """
    DungeonProgress.insert(
        config_name=config_name,
        date=date,
        zone_name=zone_name,
        dungeon_name=dungeon_name,
        completed=1,
        completed_at=datetime.now(),
    ).execute()


@pytest.fixture()
def temp_db(tmp_path: Path):
    """提供指向临时库的测试环境，并在结束后关闭连接。

    Yields:
        Path: 临时数据库文件路径。
    """
    db_path = tmp_path / "progress.db"
    _init_temp_db(db_path)
    yield db_path
    progress_db.close()
    progress_db.init(str(rdp.DEFAULT_DB_PATH))


def test_resolve_logic_date_switches_at_6am() -> None:
    """验证 06:00 换日：05:59 算前一天，06:00 算当天。"""
    assert rdp.resolve_logic_date(datetime(2026, 9, 18, 5, 59)) == "2026-09-17"
    assert rdp.resolve_logic_date(datetime(2026, 9, 18, 6, 0)) == "2026-09-18"
    assert rdp.resolve_logic_date(datetime(2026, 9, 18, 23, 30)) == "2026-09-18"


def test_fetch_pending_records_filters_by_config_and_date(temp_db: Path) -> None:
    """验证只命中目标配置与目标日期。"""
    _insert("warrior", "2026-09-18", "亡灵之地", "聚魂之地")
    _insert("mage", "2026-09-18", "亡灵之地", "聚魂之地")
    _insert("warrior", "2026-09-17", "亡灵之地", "永恒王座")

    records = rdp.fetch_pending_records(["warrior"], "2026-09-18")

    assert len(records) == 1
    assert records[0].config_name == "warrior"
    assert records[0].dungeon_name == "聚魂之地"


def test_fetch_pending_records_accepts_multiple_configs(temp_db: Path) -> None:
    """验证多配置查询可以一次命中。"""
    _insert("warrior", "2026-09-18", "亡灵之地", "聚魂之地")
    _insert("mage", "2026-09-18", "亡灵之地", "永恒王座")
    _insert("rogue", "2026-09-18", "亡灵之地", "战争剧院")

    records = rdp.fetch_pending_records(["warrior", "mage"], "2026-09-18")

    assert sorted(record.config_name for record in records) == ["mage", "warrior"]


def test_keep_daily_excludes_daily_records(temp_db: Path) -> None:
    """验证 --keep-daily 保留日常任务与每日领取记录。"""
    _insert("warrior", "2026-09-18", rdp.DAILY_TASK_ZONE_NAME, "随从派遣")
    _insert("warrior", "2026-09-18", rdp.DAILY_COLLECT_ZONE_NAME, "daily_collect")
    _insert("warrior", "2026-09-18", "亡灵之地", "聚魂之地")

    records = rdp.fetch_pending_records(["warrior"], "2026-09-18", keep_daily=True)

    assert [(record.zone_name, record.dungeon_name) for record in records] == [
        ("亡灵之地", "聚魂之地")
    ]


def test_delete_records_removes_only_matching_rows(temp_db: Path) -> None:
    """验证删除只影响目标配置与日期，且保留日常记录。"""
    _insert("warrior", "2026-09-18", "亡灵之地", "聚魂之地")
    _insert("warrior", "2026-09-18", "亡灵之地", "永恒王座")
    _insert("warrior", "2026-09-18", rdp.DAILY_TASK_ZONE_NAME, "随从派遣")
    _insert("mage", "2026-09-18", "亡灵之地", "聚魂之地")
    _insert("warrior", "2026-09-17", "亡灵之地", "战争剧院")

    deleted = rdp.delete_records(["warrior"], "2026-09-18", keep_daily=True)

    assert deleted == 2
    remaining = {(r.config_name, r.date, r.dungeon_name) for r in DungeonProgress.select()}
    assert remaining == {
        ("warrior", "2026-09-18", "随从派遣"),
        ("mage", "2026-09-18", "聚魂之地"),
        ("warrior", "2026-09-17", "战争剧院"),
    }


def test_delete_records_without_configs_is_noop(temp_db: Path) -> None:
    """验证空配置列表不会误删任何数据。"""
    _insert("warrior", "2026-09-18", "亡灵之地", "聚魂之地")

    assert rdp.delete_records([], "2026-09-18") == 0
    assert DungeonProgress.select().count() == 1


def test_summarize_records_groups_by_config_and_zone(temp_db: Path) -> None:
    """验证汇总结果按「配置 → 区域」分组计数。"""
    _insert("warrior", "2026-09-18", "亡灵之地", "聚魂之地")
    _insert("warrior", "2026-09-18", "亡灵之地", "永恒王座")
    _insert("warrior", "2026-09-18", rdp.DAILY_TASK_ZONE_NAME, "随从派遣")
    _insert("mage", "2026-09-18", "暗影大陆", "古魔宝库")

    summary = rdp.summarize_records(rdp.fetch_pending_records(["warrior", "mage"], "2026-09-18"))

    assert summary["warrior"] == {"亡灵之地": 2, rdp.DAILY_TASK_ZONE_NAME: 1}
    assert summary["mage"] == {"暗影大陆": 1}


def test_validate_date_rejects_invalid_format() -> None:
    """验证非法日期格式会抛出 typer.BadParameter。"""
    import typer

    assert rdp.validate_date("2026-09-18") == "2026-09-18"
    with pytest.raises(typer.BadParameter):
        rdp.validate_date("2026/09/18")


def test_list_available_configs_reads_configs_dir() -> None:
    """验证可读出现有职业配置名，且包含 warrior / mage。"""
    names = rdp.list_available_configs()

    assert "warrior" in names
    assert "mage" in names
    assert all(name.endswith(".json") is False for name in names)
