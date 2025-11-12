#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""为 Streamlit 副本进度面板提供可测试的数据准备工具。"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Sequence, Tuple

from database import DungeonProgressDB
from database.dungeon_db import DungeonProgress, SPECIAL_ZONE_NAMES
from peewee import fn

ConfigDict = Dict[str, dict]


def load_configurations(config_dir: str = "configs") -> ConfigDict:
    """加载配置目录下的所有角色配置。"""
    configs: ConfigDict = {}
    if not os.path.isdir(config_dir):
        return configs

    for filename in sorted(os.listdir(config_dir)):
        if not filename.endswith(".json"):
            continue
        config_name = filename[:-5]
        path = os.path.join(config_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            continue

        zones_payload = []
        for zone_name, dungeon_list in payload.get("zone_dungeons", {}).items():
            normalized = []
            for dungeon in dungeon_list:
                if "name" not in dungeon:
                    continue
                normalized.append(
                    {
                        "name": dungeon["name"],
                        "selected": bool(dungeon.get("selected", True)),
                    }
                )
            zones_payload.append({"zone_name": zone_name, "dungeons": normalized})

        configs[config_name] = {
            "class_name": payload.get("class", "未知"),
            "description": payload.get("description", ""),
            "zones": zones_payload,
        }

    return configs


def fetch_today_records(
    db: DungeonProgressDB, include_special: bool = False
) -> List[dict]:
    """查询今天所有已完成副本的记录列表。"""
    today = db.get_today_date()
    conditions = (
        (DungeonProgress.date == today)
        & (DungeonProgress.completed == 1)
    )
    if not include_special and SPECIAL_ZONE_NAMES:
        conditions &= ~(DungeonProgress.zone_name.in_(SPECIAL_ZONE_NAMES))

    query = (
        DungeonProgress.select(
            DungeonProgress.config_name,
            DungeonProgress.zone_name,
            DungeonProgress.dungeon_name,
            DungeonProgress.completed_at,
        )
        .where(conditions)
        .order_by(DungeonProgress.completed_at)
    )

    return [
        {
            "config_name": record.config_name,
            "zone_name": record.zone_name,
            "dungeon_name": record.dungeon_name,
            "completed_at": record.completed_at,
        }
        for record in query
    ]


def build_config_progress(
    configs: ConfigDict, today_records: Sequence[dict]
) -> List[dict]:
    """将配置文件与今日进度合并, 生成面板展示所需的数据。"""
    completion_map: Dict[str, set] = defaultdict(set)
    completion_times: Dict[Tuple[str, str, str], object] = {}

    for record in today_records:
        key = (record["config_name"], record["zone_name"], record["dungeon_name"])
        completion_map[record["config_name"]].add((record["zone_name"], record["dungeon_name"]))
        completion_times[key] = record["completed_at"]

    all_configs = set(configs.keys()) | set(completion_map.keys())
    progress_data: List[dict] = []

    for config_name in sorted(all_configs):
        config_payload = configs.get(config_name, {
            "class_name": "未知",
            "description": "",
            "zones": [],
        })
        known_pairs = {
            (zone["zone_name"], dungeon["name"])
            for zone in config_payload.get("zones", [])
            for dungeon in zone.get("dungeons", [])
            if bool(dungeon.get("selected", True))
        }

        zones_output = []
        total_planned = 0
        completed_planned = 0

        for zone in config_payload.get("zones", []):
            zone_name = zone["zone_name"]
            planned_count = 0
            zone_completed = 0
            dungeon_entries = []

            for dungeon in zone.get("dungeons", []):
                should_run = bool(dungeon.get("selected", True))
                if not should_run:
                    continue

                dungeon_name = dungeon["name"]
                is_completed = (
                    (zone_name, dungeon_name) in completion_map.get(config_name, set())
                )
                planned_count += 1
                total_planned += 1
                if is_completed:
                    completed_planned += 1
                    zone_completed += 1

                dungeon_entries.append(
                    {
                        "name": dungeon_name,
                        "selected": True,
                        "completed": is_completed,
                        "completed_at": completion_times.get(
                            (config_name, zone_name, dungeon_name)
                        ),
                    }
                )

            if dungeon_entries:
                zones_output.append(
                    {
                        "zone_name": zone_name,
                        "planned_count": planned_count,
                        "completed_count": zone_completed,
                        "dungeons": dungeon_entries,
                    }
                )

        extra_completions = [
            {
                "zone_name": zone_name,
                "dungeon_name": dungeon_name,
                "completed_at": completion_times.get(
                    (config_name, zone_name, dungeon_name)
                ),
            }
            for zone_name, dungeon_name in completion_map.get(config_name, set())
            if (zone_name, dungeon_name) not in known_pairs
        ]

        progress_data.append(
            {
                "config_name": config_name,
                "class_name": config_payload.get("class_name", "未知"),
                "description": config_payload.get("description", ""),
                "zones": zones_output,
                "total_planned": total_planned,
                "completed_planned": completed_planned,
                "completion_rate": (
                    completed_planned / total_planned if total_planned else 0.0
                ),
                "extra_completions": extra_completions,
                "actual_completed": len(completion_map.get(config_name, set())),
            }
        )

    return progress_data


def compute_zone_stats(today_records: Sequence[dict]) -> List[Tuple[str, int]]:
    """统计今天所有职业在各区域的完成数量。"""
    zone_counter: Dict[str, int] = defaultdict(int)
    for record in today_records:
        zone = record["zone_name"]
        if SPECIAL_ZONE_NAMES and zone in SPECIAL_ZONE_NAMES:
            continue
        zone_counter[zone] += 1

    return sorted(zone_counter.items(), key=lambda item: item[1], reverse=True)


def compute_recent_totals(
    db: DungeonProgressDB, days: int = 7, include_special: bool = False
) -> List[Tuple[str, int]]:
    """获取最近 N 天的总通关数量。"""
    if days <= 0:
        return []

    target_dates = [
        (date.today() - timedelta(days=offset)).isoformat() for offset in range(days)
    ]

    conditions = (
        (DungeonProgress.date.in_(target_dates))
        & (DungeonProgress.completed == 1)
    )
    if not include_special and SPECIAL_ZONE_NAMES:
        conditions &= ~(DungeonProgress.zone_name.in_(SPECIAL_ZONE_NAMES))

    query = (
        DungeonProgress.select(
            DungeonProgress.date, fn.COUNT(DungeonProgress.id).alias("count")
        )
        .where(conditions)
        .group_by(DungeonProgress.date)
    )
    count_map = {row.date: row.count for row in query}

    return [(day, count_map.get(day, 0)) for day in target_dates]


def summarize_progress(config_progress: Sequence[dict]) -> dict:
    """对职业进度做整体汇总, 便于在仪表盘顶层展示。"""
    total_planned = sum(item.get("total_planned", 0) for item in config_progress)
    total_completed = sum(
        item.get("completed_planned", 0) for item in config_progress
    )
    completion_rate = total_completed / total_planned if total_planned else 0.0

    ranking = sorted(
        [
            {
                "config_name": item["config_name"],
                "class_name": item.get("class_name", "未知"),
                "completed": item.get("completed_planned", 0),
                "actual_completed": item.get("actual_completed", 0),
            }
            for item in config_progress
        ],
        key=lambda entry: entry["completed"],
        reverse=True,
    )

    active_configs = sum(1 for item in config_progress if item.get("actual_completed", 0))

    return {
        "total_planned": total_planned,
        "total_completed": total_completed,
        "completion_rate": completion_rate,
        "active_configs": active_configs,
        "ranking": ranking,
    }


__all__ = [
    "load_configurations",
    "fetch_today_records",
    "build_config_progress",
    "compute_zone_stats",
    "compute_recent_totals",
    "summarize_progress",
]
