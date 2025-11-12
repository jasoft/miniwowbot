#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""魔兽世界职业配色表, 供 CLI 与 Streamlit 共享."""

from __future__ import annotations

from functools import lru_cache

# 官方职业颜色 (来源: https://worldofwarcraft.blizzard.com)
_HEX_COLOR_TABLE = {
    "death knight": "#C41E3A",
    "demon hunter": "#A330C9",
    "druid": "#FF7D0A",
    "evoker": "#33937F",
    "hunter": "#ABD473",
    "mage": "#40C7EB",
    "monk": "#00FF96",
    "paladin": "#F58CBA",
    "priest": "#FFFFFF",
    "rogue": "#FFF569",
    "shaman": "#0070DE",
    "warlock": "#8787ED",
    "warrior": "#C79C6E",
}

_DEFAULT_HEX = "#CCCCCC"

_ALIAS_TABLE = {
    "战士": "warrior",
    "武僧": "monk",
    "僧侣": "monk",
    "武僧Monk": "monk",  # 兼容潜在配置
    "法师": "mage",
    "猎人": "hunter",
    "牧师": "priest",
    "圣骑士": "paladin",
    "盗贼": "rogue",
    "萨满祭司": "shaman",
    "萨满": "shaman",
    "术士": "warlock",
    "德鲁伊": "druid",
    "死亡骑士": "death knight",
    "恶魔猎手": "demon hunter",
    "唤魔师": "evoker",
    "死亡骑士DK": "death knight",
    "恶魔猎手DH": "demon hunter",
}


def _normalize_class_name(class_name: str | None) -> str | None:
    if not class_name:
        return None
    key = class_name.strip().lower()
    alias = _ALIAS_TABLE.get(class_name.strip()) or _ALIAS_TABLE.get(key)
    if alias:
        return alias
    return key


@lru_cache(maxsize=None)
def get_class_hex_color(class_name: str | None) -> str:
    """返回职业对应的 HEX 颜色."""
    normalized = _normalize_class_name(class_name)
    if not normalized:
        return _DEFAULT_HEX
    return _HEX_COLOR_TABLE.get(normalized, _DEFAULT_HEX)


def get_class_ansi_color(class_name: str | None) -> str:
    """根据职业颜色返回 24-bit ANSI 前景色代码."""
    hex_color = get_class_hex_color(class_name).lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


__all__ = [
    "get_class_hex_color",
    "get_class_ansi_color",
]
