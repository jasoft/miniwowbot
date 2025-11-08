#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""测试 auto_dungeon 主循环的补漏逻辑"""

from collections import deque
import types
import pytest

import auto_dungeon


class DummyDB:
    """用于 count_remaining_selected_dungeons 的简单数据库桩"""

    def __init__(self, completed):
        self._completed = set(completed)

    def is_dungeon_completed(self, zone_name, dungeon_name):
        return (zone_name, dungeon_name) in self._completed


class TestCountRemaining:
    def test_count_remaining_selected_dungeons(self, monkeypatch):
        monkeypatch.setattr(auto_dungeon, "config_loader", object())
        monkeypatch.setattr(
            auto_dungeon,
            "zone_dungeons",
            {
                "ZoneA": [
                    {"name": "A1", "selected": True},
                    {"name": "A2", "selected": False},
                ],
                "ZoneB": [
                    {"name": "B1", "selected": True},
                    {"name": "B2", "selected": True},
                ],
            },
        )

        db = DummyDB({("ZoneA", "A1"), ("ZoneB", "B1")})
        remaining = auto_dungeon.count_remaining_selected_dungeons(db)
        assert remaining == 1  # 只剩 ZoneB-B2


class TestMainLoop:
    def test_main_retries_until_all_dungeons_done(self, monkeypatch):
        fake_args = types.SimpleNamespace(
            load_account=None,
            skip_emulator_check=True,
            emulator=None,
            config="configs/test.json",
            env_overrides=None,
        )
        monkeypatch.setattr(auto_dungeon, "parse_arguments", lambda: fake_args)

        def fake_initialize_configs(config_path, env_overrides):
            monkeypatch.setattr(
                auto_dungeon,
                "config_loader",
                types.SimpleNamespace(
                    get_config_name=lambda: "test-config", get_char_class=lambda: None
                ),
            )
            monkeypatch.setattr(
                auto_dungeon,
                "zone_dungeons",
                {"Zone": [{"name": "Dungeon", "selected": True}]},
            )

        monkeypatch.setattr(auto_dungeon, "initialize_configs", fake_initialize_configs)
        monkeypatch.setattr(auto_dungeon, "initialize_device_and_ocr", lambda emulator: None)
        monkeypatch.setattr(auto_dungeon, "select_character", lambda char: None)
        monkeypatch.setattr(auto_dungeon, "stop_app", lambda package: None)
        monkeypatch.setattr(auto_dungeon, "start_app", lambda package: None)
        monkeypatch.setattr(auto_dungeon, "sleep", lambda seconds: None)
        monkeypatch.setattr(auto_dungeon, "back_to_main", lambda: None)
        monkeypatch.setattr(auto_dungeon, "check_and_start_emulator", lambda emulator: True)
        monkeypatch.setattr(auto_dungeon, "send_bark_notification", lambda *args, **kwargs: None)

        monkeypatch.setattr(auto_dungeon, "show_progress_statistics", lambda db: (0, 2, 2))

        run_calls = []

        def fake_run(db, total):
            run_calls.append(total)

        monkeypatch.setattr(auto_dungeon, "run_dungeon_traversal", fake_run)

        remaining_counts = deque([5, 0])

        def fake_count(db):
            return remaining_counts.popleft()

        monkeypatch.setattr(auto_dungeon, "count_remaining_selected_dungeons", fake_count)

        class FakeDB:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

            def get_today_completed_count(self):
                return 3

        monkeypatch.setattr(auto_dungeon, "DungeonProgressDB", FakeDB)

        auto_dungeon.main()

        assert len(run_calls) == 2
        assert not remaining_counts
