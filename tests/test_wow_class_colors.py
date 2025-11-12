#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""验证魔兽职业配色表的功能."""

from wow_class_colors import get_class_hex_color, get_class_ansi_color


def test_get_class_hex_color_supports_chinese_names():
    assert get_class_hex_color("战士") == "#C79C6E"
    assert get_class_hex_color("法师") == "#40C7EB"


def test_get_class_hex_color_supports_aliases_and_defaults():
    assert get_class_hex_color("Warrior") == "#C79C6E"
    assert get_class_hex_color("死亡骑士") == "#C41E3A"
    assert get_class_hex_color("未知职业") == "#CCCCCC"


def test_get_class_ansi_color_returns_truecolor_sequence():
    ansi_code = get_class_ansi_color("猎人")
    assert ansi_code.startswith("\033[38;2;")
    assert ansi_code.endswith("m")
