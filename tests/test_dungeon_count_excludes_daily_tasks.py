"""副本计数口径：排除「日常任务」区域的回归测试。

背景：`ConfigLoader._load_config()` 会把配置里的 `daily_tasks` 合成成一个名为
「日常任务」的区域并塞进 `zone_dungeons`，好让执行流程能遍历到它去跑每日任务。
但它**不是副本**，一旦被算进「副本数量 / 副本进度」，就会出现：

- `total_selected` 虚高（副本数 + 日常任务数）
- 日常任务里存在当天做不完的项目 → 完成数永远差 1 → 进度恒判未完成
- 进而退出码恒 1 → 触发整轮重试

因此「日常任务」应与 `__daily_collect__` 同等对待，默认一律排除。
"""

from __future__ import annotations

import json

from config_loader import ConfigLoader
from database.dungeon_db import DAILY_TASK_ZONE_NAME, DungeonProgressDB


def _write_config(tmp_path) -> str:
    """写入一个同时含日常任务与副本的最小配置，返回配置路径。"""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    config_path = configs_dir / "warrior.json"
    config_path.write_text(
        json.dumps(
            {
                "class": "战士",
                "daily_tasks": [
                    {"name": "领取挂机奖励", "selected": True},
                    {"name": "领取邮件", "selected": True},
                    {"name": "领取广告奖励", "selected": False},
                ],
                "zone_dungeons": {
                    "风暴群岛": [
                        {"name": "真理之地", "selected": True},
                        {"name": "腐化沼泽", "selected": True},
                    ],
                    "亡灵之地": [
                        {"name": "聚魂之地", "selected": False},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(config_path)


class TestConfigLoaderDungeonCounting:
    """`ConfigLoader` 的副本计数不应包含「日常任务」。"""

    def test_counts_exclude_daily_tasks(self, tmp_path) -> None:
        """副本数量、选定副本数量均不含日常任务。"""
        loader = ConfigLoader(_write_config(tmp_path))

        # 日常任务 3 项里 2 项 selected，若计入会多出 2
        assert loader.get_selected_dungeon_count() == 2
        assert loader.get_dungeon_count() == 3

    def test_flattened_lists_exclude_daily_tasks(self, tmp_path) -> None:
        """扁平化的副本名列表不含日常任务名。"""
        loader = ConfigLoader(_write_config(tmp_path))

        assert loader.get_all_selected_dungeons() == ["真理之地", "腐化沼泽"]
        assert "领取挂机奖励" not in loader.get_all_dungeons()
        assert "领取邮件" not in loader.get_all_dungeons()

    def test_dungeon_zones_excludes_but_zone_dungeons_keeps(self, tmp_path) -> None:
        """副本区域表排除日常任务，而执行用的区域表仍保留它。"""
        loader = ConfigLoader(_write_config(tmp_path))

        # 副本口径
        dungeon_zones = loader.get_dungeon_zones()
        assert DAILY_TASK_ZONE_NAME not in dungeon_zones
        assert set(dungeon_zones) == {"风暴群岛", "亡灵之地"}

        # 执行流程口径：必须仍能遍历到日常任务
        exec_zones = loader.get_zone_dungeons()
        assert DAILY_TASK_ZONE_NAME in exec_zones
        assert len(exec_zones[DAILY_TASK_ZONE_NAME]) == 3


class TestDatabaseCounting:
    """数据库默认统计同样排除「日常任务」区域。"""

    def test_daily_task_zone_excluded_from_counts_by_default(self, tmp_path) -> None:
        """「日常任务」默认不计入副本数量与副本列表。"""
        db_path = str(tmp_path / "progress.db")
        with DungeonProgressDB(db_path=db_path, config_name="warrior") as progress_db:
            progress_db.mark_dungeon_completed("风暴群岛", "真理之地")
            progress_db.mark_dungeon_completed(DAILY_TASK_ZONE_NAME, "领取挂机奖励")
            progress_db.mark_dungeon_completed(DAILY_TASK_ZONE_NAME, "领取邮件")

            assert progress_db.get_today_completed_count() == 1

            dungeons = progress_db.get_today_completed_dungeons()
            assert ("风暴群岛", "真理之地") in dungeons
            assert all(zone != DAILY_TASK_ZONE_NAME for zone, _ in dungeons)

            assert DAILY_TASK_ZONE_NAME not in dict(progress_db.get_zone_stats())

    def test_daily_task_zone_included_when_special_requested(self, tmp_path) -> None:
        """显式要求 special 时，「日常任务」应被纳入。"""
        db_path = str(tmp_path / "progress.db")
        with DungeonProgressDB(db_path=db_path, config_name="warrior") as progress_db:
            progress_db.mark_dungeon_completed("风暴群岛", "真理之地")
            progress_db.mark_dungeon_completed(DAILY_TASK_ZONE_NAME, "领取挂机奖励")

            assert progress_db.get_today_completed_count(include_special=True) == 2

            dungeons_full = progress_db.get_today_completed_dungeons(include_special=True)
            assert (DAILY_TASK_ZONE_NAME, "领取挂机奖励") in dungeons_full
