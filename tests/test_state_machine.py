#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 AutoDungeonStateMachine 的状态切换逻辑
"""

import pytest

import auto_dungeon
from auto_dungeon import AutoDungeonStateMachine


class DummyConfig:
    """简单的配置占位对象"""

    pass


@pytest.fixture
def state_machine_env(monkeypatch):
    """为状态机测试准备依赖函数的假实现"""

    events = {
        "selected": [],
        "open_map": 0,
        "zone_switch": [],
        "focused": [],
        "battle": [],
        "daily": 0,
        "main": 0,
        "sell": 0,
        "click_free": True,
    }

    def fake_select_character(char_class):
        events["selected"].append(char_class)

    def fake_open_map():
        events["open_map"] += 1

    def fake_switch_zone(zone_name):
        events["zone_switch"].append(zone_name)
        return True

    def fake_focus(dungeon_name, zone_name, max_attempts=2):
        events["focused"].append((zone_name, dungeon_name, max_attempts))
        return True

    def fake_click_free():
        return events["click_free"]

    def fake_find_text_and_click_safe(*args, **kwargs):
        return True

    def fake_auto_combat(completed_dungeons=0, total_dungeons=0):
        events["battle"].append(
            {"completed": completed_dungeons, "total": total_dungeons}
        )

    def fake_daily_collect():
        events["daily"] += 1

    def fake_back_to_main(*args, **kwargs):
        events["main"] += 1

    def fake_sell_trashes():
        events["sell"] += 1

    monkeypatch.setattr(auto_dungeon, "select_character", fake_select_character)
    monkeypatch.setattr(auto_dungeon, "open_map", fake_open_map)
    monkeypatch.setattr(auto_dungeon, "switch_to_zone", fake_switch_zone)
    monkeypatch.setattr(auto_dungeon, "focus_and_click_dungeon", fake_focus)
    monkeypatch.setattr(auto_dungeon, "click_free_button", fake_click_free)
    monkeypatch.setattr(
        auto_dungeon, "find_text_and_click_safe", fake_find_text_and_click_safe
    )
    monkeypatch.setattr(auto_dungeon, "auto_combat", fake_auto_combat)
    monkeypatch.setattr(auto_dungeon, "daily_collect", fake_daily_collect)
    monkeypatch.setattr(auto_dungeon, "back_to_main", fake_back_to_main)
    monkeypatch.setattr(auto_dungeon, "sell_trashes", fake_sell_trashes)

    machine = AutoDungeonStateMachine(config_loader=DummyConfig())
    return machine, events


class TestAutoDungeonStateMachine:
    """验证状态机关键路径"""

    def test_full_flow(self, state_machine_env):
        machine, events = state_machine_env

        assert machine.select_character_state(char_class="Warrior") is not False
        assert events["selected"] == ["Warrior"]
        assert machine.state == "main_menu"

        assert machine.prepare_dungeon_state("ZoneA", "DungeonA")
        assert events["focused"][-1][:2] == ("ZoneA", "DungeonA")
        assert machine.state == "dungeon_selection"

        assert machine.start_battle_state(
            "DungeonA", completed_dungeons=2, total_dungeons=5
        )
        assert events["battle"][0] == {"completed": 2, "total": 5}
        assert machine.state == "dungeon_battle"

        machine.complete_battle_state()
        assert machine.state == "reward_claim"

        machine.return_to_main_state()
        assert machine.state == "main_menu"
        assert events["main"] >= 1

        assert machine.claim_daily_rewards() is not False
        assert events["daily"] == 1
        assert machine.state == "reward_claim"

        machine.return_to_main_state()
        assert machine.state == "main_menu"

        assert machine.sell_loot() is not False
        assert events["sell"] == 1
        assert machine.state == "sell_loot"

        machine.finish_sell_loot()
        assert machine.state == "main_menu"

    def test_no_free_battle_path(self, state_machine_env):
        machine, events = state_machine_env
        events["click_free"] = False

        machine.select_character_state(char_class="Mage")
        assert machine.state == "main_menu"

        assert machine.prepare_dungeon_state("ZoneB", "DungeonB")
        assert machine.state == "dungeon_selection"

        assert machine.start_battle_state("DungeonB") is False
        assert machine.state == "dungeon_selection"

        machine.return_to_main_state()
        assert machine.state == "main_menu"
        assert events["main"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
