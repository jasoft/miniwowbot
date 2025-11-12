#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""测试 view_progress_dashboard 模块的数据处理逻辑。"""

import json
import os
import tempfile
from datetime import datetime, timedelta, date

import pytest

from database import DungeonProgressDB
from database.dungeon_db import (
    DAILY_COLLECT_DUNGEON_NAME,
    DAILY_COLLECT_ZONE_NAME,
    DungeonProgress,
)
from view_progress_dashboard import (
    build_config_progress,
    compute_recent_totals,
    compute_zone_stats,
    fetch_today_records,
    load_configurations,
    summarize_progress,
)


@pytest.fixture(name="temp_db_path")
def fixture_temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)


@pytest.fixture(name="temp_config_dir")
def fixture_temp_config_dir(tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    base_payload = {
        "description": "测试职业",
        "class": "战士",
        "zone_dungeons": {
            "风暴群岛": [
                {"name": "真理之地", "selected": True},
                {"name": "预言神殿", "selected": False},
            ],
            "军团领域": [
                {"name": "梦魇丛林", "selected": True}
            ],
        },
    }
    (config_dir / "alpha.json").write_text(
        json.dumps(base_payload, ensure_ascii=False), encoding="utf-8"
    )

    payload_b = base_payload.copy()
    payload_b["class"] = "法师"
    payload_b["description"] = "第二职业"
    (config_dir / "beta.json").write_text(
        json.dumps(payload_b, ensure_ascii=False), encoding="utf-8"
    )
    return str(config_dir)


def _mark_completed(db_path, config_name, zone, dungeon):
    with DungeonProgressDB(db_path, config_name) as db:
        db.mark_dungeon_completed(zone, dungeon)


def test_load_configurations_reads_zone_info(temp_config_dir):
    configs = load_configurations(temp_config_dir)
    assert set(configs.keys()) == {"alpha", "beta"}
    assert configs["alpha"]["class_name"] == "战士"
    zones = {zone["zone_name"]: zone for zone in configs["alpha"]["zones"]}
    assert "风暴群岛" in zones
    assert len(zones["风暴群岛"]["dungeons"]) == 2
    assert zones["风暴群岛"]["dungeons"][1]["selected"] is False


def test_fetch_today_records_and_zone_stats(temp_db_path):
    _mark_completed(temp_db_path, "alpha", "风暴群岛", "真理之地")
    _mark_completed(temp_db_path, "beta", "军团领域", "梦魇丛林")
    _mark_completed(temp_db_path, "beta", DAILY_COLLECT_ZONE_NAME, DAILY_COLLECT_DUNGEON_NAME)

    with DungeonProgressDB(temp_db_path, "alpha") as db:
        records_default = fetch_today_records(db)
        records_full = fetch_today_records(db, include_special=True)

    assert len(records_default) == 2
    assert len(records_full) == 3

    zone_stats = compute_zone_stats(records_full)
    zone_map = dict(zone_stats)
    assert zone_map["风暴群岛"] == 1
    assert zone_map["军团领域"] == 1
    assert DAILY_COLLECT_ZONE_NAME not in zone_map


def test_build_config_progress_matches_completion_flags(temp_db_path, temp_config_dir):
    _mark_completed(temp_db_path, "alpha", "风暴群岛", "真理之地")
    _mark_completed(temp_db_path, "alpha", "军团领域", "梦魇丛林")
    _mark_completed(temp_db_path, "alpha", "未知区域", "隐藏副本")

    configs = load_configurations(temp_config_dir)
    with DungeonProgressDB(temp_db_path, "alpha") as db:
        records = fetch_today_records(db, include_special=True)

    progress = build_config_progress(configs, records)
    alpha_data = next(item for item in progress if item["config_name"] == "alpha")
    assert alpha_data["total_planned"] == 2  # 只统计选中的副本
    assert alpha_data["completed_planned"] == 2
    assert len(alpha_data["extra_completions"]) == 1


def test_compute_recent_totals_counts_each_day(temp_db_path):
    today = date.today()
    with DungeonProgressDB(temp_db_path, "alpha") as db:
        for offset in range(3):
            target_date = (today - timedelta(days=offset)).isoformat()
            for idx in range(offset + 1):
                DungeonProgress.insert(
                    config_name="alpha",
                    date=target_date,
                    zone_name="风暴群岛",
                    dungeon_name=f"副本{offset}-{idx}",
                    completed=1,
                    completed_at=datetime.utcnow(),
                ).execute()

        stats = compute_recent_totals(db, days=3)

    assert stats[0][1] == 1  # 今天
    assert stats[1][1] == 2  # 昨天
    assert stats[2][1] == 3  # 前天


def test_summarize_progress_returns_ranking():
    sample = [
        {
            "config_name": "alpha",
            "class_name": "战士",
            "total_planned": 2,
            "completed_planned": 2,
            "actual_completed": 3,
        },
        {
            "config_name": "beta",
            "class_name": "法师",
            "total_planned": 4,
            "completed_planned": 1,
            "actual_completed": 1,
        },
    ]

    summary = summarize_progress(sample)
    assert summary["total_planned"] == 6
    assert summary["total_completed"] == 3
    assert summary["active_configs"] == 2
    assert summary["ranking"][0]["config_name"] == "alpha"
