#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
副本配置文件
包含所有副本列表和 OCR 识别纠正映射
"""

# OCR 识别纠正映射表
# 格式: {"OCR识别的错误文本": "正确的文本"}
# 用于纠正 OCR 常见的识别错误
OCR_CORRECTION_MAP = {
    "梦魔丛林": "梦魇丛林",  # OCR 经常把"魇"识别成"魔"
    # 可以继续添加其他常见的 OCR 识别错误
    # "错误文本": "正确文本",
}


def correct_ocr_text(text):
    """
    纠正 OCR 识别错误的文本

    Args:
        text: OCR 识别的文本

    Returns:
        纠正后的文本
    """
    return OCR_CORRECTION_MAP.get(text, text)


# 副本配置字典
# 格式: {"区域名称": [{"name": "副本名", "selected": True/False}, ...]}
# selected: True 表示选定该副本，会自动打；False 表示跳过该副本
ZONE_DUNGEONS = {
    # 风暴群岛
    "风暴群岛": [
        {"name": "真理之地", "selected": True},
        {"name": "预言神殿", "selected": True},
        {"name": "海底王宫", "selected": True},
        {"name": "泰坦密室", "selected": True},
        {"name": "黑暗庄园", "selected": True},
        {"name": "海底囚牢", "selected": True},
        {"name": "地精岛", "selected": True},
        {"name": "泰坦遗迹", "selected": True},
        {"name": "海盗监狱", "selected": True},
        {"name": "巨魔陵墓", "selected": True},
        {"name": "毒蛇神庙", "selected": True},
        {"name": "腐化沼泽", "selected": True},
        {"name": "海港城", "selected": True},
    ],
    # 军团领域
    "军团领域": [
        {"name": "大墓地密室", "selected": True},
        {"name": "流放王座", "selected": True},
        {"name": "毁灭之地", "selected": True},
        {"name": "大墓地圣殿", "selected": True},
        {"name": "封印地窟", "selected": True},
        {"name": "魔能宫殿", "selected": True},
        {"name": "魔能要塞", "selected": True},
        {"name": "魔法高台", "selected": True},
        {"name": "地底巢穴", "selected": True},
        {"name": "风暴绿洲", "selected": True},
        {"name": "渡鸦堡垒", "selected": True},
        {"name": "梦魇丛林", "selected": True},
    ],
    # 暗影大陆
    "暗影大陆": [
        {"name": "钢铁码头", "selected": False},
        {"name": "食人魔王国", "selected": True},
        {"name": "黑暗熔炉", "selected": True},
        {"name": "通天峰", "selected": False},
        {"name": "熔渣车间", "selected": True},
        {"name": "食人魔矿井", "selected": False},
        {"name": "木精圣地", "selected": False},
        {"name": "鲜血庭院", "selected": True},
        {"name": "钢铁车站", "selected": False},
        {"name": "神圣陵墓", "selected": False},
        {"name": "兽人墓地", "selected": False},
        {"name": "毁灭高台", "selected": True},
    ],
    # 迷雾大陆
    "迷雾大陆": [
        {"name": "兽人圣殿", "selected": True},
        {"name": "恐魔之心", "selected": False},
        {"name": "古魔宝库", "selected": True},
        {"name": "兽人都城", "selected": False},
        {"name": "古魔宫殿", "selected": False},
        {"name": "风暴之巅", "selected": True},
        {"name": "酿酒厂", "selected": False},
        {"name": "风暴王座", "selected": True},
        {"name": "青龙寺", "selected": False},
        {"name": "白虎寺", "selected": False},
        {"name": "日落关", "selected": False},
        {"name": "玄牛寺", "selected": False},
    ],
    # 元素之地
    "元素之地": [
        {"name": "火焰宫殿", "selected": True},
        {"name": "守护者神殿", "selected": True},
        {"name": "黑龙宫殿", "selected": False},
        {"name": "黑暗堡垒", "selected": False},
        {"name": "潮汐宫殿", "selected": False},
        {"name": "黑暗监狱", "selected": False},
        {"name": "泰坦密室", "selected": False},
        {"name": "大地神殿", "selected": True},
        {"name": "失落之城", "selected": False},
        {"name": "天空之城", "selected": True},
        {"name": "黑石熔炉", "selected": False},
    ],
    # 冰封大陆
    "冰封大陆": [
        {"name": "泰坦基地", "selected": False},
        {"name": "冠军试炼", "selected": False},
        {"name": "寒冰堡垒", "selected": False},
        {"name": "寒冰王座", "selected": False},
        {"name": "灵魂熔炉", "selected": False},
        {"name": "瘟疫之城", "selected": False},
        {"name": "古代大厅", "selected": False},
        {"name": "古代王国", "selected": False},
        {"name": "巨魔要塞", "selected": False},
        {"name": "峡湾城堡", "selected": True},
        {"name": "蓝龙巢穴", "selected": True},
    ],
    # 虚空领域
    "虚空领域": [
        {"name": "魔法之井", "selected": False},
        {"name": "虚空要塞", "selected": True},
        {"name": "海底神殿", "selected": False},
        {"name": "守护者之塔上层", "selected": False},
        {"name": "黑暗神殿", "selected": False},
        {"name": "守护者之塔下层", "selected": False},
        {"name": "圣山战场", "selected": False},
        {"name": "虚空舰", "selected": False},
        {"name": "沼泽水库", "selected": False},
        {"name": "山丘城堡", "selected": False},
        {"name": "地狱火堡垒", "selected": False},
        {"name": "亡者之城", "selected": True},
    ],
    # 东部大陆
    "东部大陆": [
        {"name": "亡灵要塞", "selected": True},
        {"name": "黑龙巢穴", "selected": False},
        {"name": "火焰之心", "selected": False},
        {"name": "巨石密室", "selected": False},
        {"name": "诅咒教堂", "selected": False},
        {"name": "盗贼矿井", "selected": False},
        {"name": "机械要塞", "selected": False},
        {"name": "巨魔墓地", "selected": False},
        {"name": "噩梦洞穴", "selected": False},
        {"name": "野猪人高地", "selected": False},
        {"name": "水晶庭院", "selected": False},
        {"name": "龙人塔", "selected": False},
        {"name": "精灵遗迹", "selected": False},
        {"name": "沉没的神庙", "selected": False},
    ],
}


def get_all_dungeons():
    """
    获取所有副本列表（扁平化）

    Returns:
        list: 所有副本名称的列表
    """
    all_dungeons = []
    for dungeons in ZONE_DUNGEONS.values():
        for dungeon in dungeons:
            all_dungeons.append(dungeon["name"])
    return all_dungeons


def get_all_selected_dungeons():
    """
    获取所有选定的副本列表（扁平化）

    Returns:
        list: 所有选定的副本名称的列表
    """
    selected_dungeons = []
    for dungeons in ZONE_DUNGEONS.values():
        for dungeon in dungeons:
            if dungeon["selected"]:
                selected_dungeons.append(dungeon["name"])
    return selected_dungeons


def get_dungeon_count():
    """
    获取副本总数

    Returns:
        int: 副本总数
    """
    return sum(len(dungeons) for dungeons in ZONE_DUNGEONS.values())


def get_selected_dungeon_count():
    """
    获取选定的副本总数

    Returns:
        int: 选定的副本总数
    """
    count = 0
    for dungeons in ZONE_DUNGEONS.values():
        for dungeon in dungeons:
            if dungeon["selected"]:
                count += 1
    return count


def get_zone_count():
    """
    获取区域总数

    Returns:
        int: 区域总数
    """
    return len(ZONE_DUNGEONS)


def get_dungeons_by_zone(zone_name):
    """
    获取指定区域的副本列表

    Args:
        zone_name: 区域名称

    Returns:
        list: 副本字典列表，如果区域不存在则返回空列表
    """
    return ZONE_DUNGEONS.get(zone_name, [])


def get_selected_dungeons_by_zone(zone_name):
    """
    获取指定区域的选定副本列表

    Args:
        zone_name: 区域名称

    Returns:
        list: 选定的副本字典列表
    """
    dungeons = ZONE_DUNGEONS.get(zone_name, [])
    return [d for d in dungeons if d["selected"]]


def is_valid_zone(zone_name):
    """
    检查区域是否存在

    Args:
        zone_name: 区域名称

    Returns:
        bool: 区域是否存在
    """
    return zone_name in ZONE_DUNGEONS


def is_valid_dungeon(dungeon_name):
    """
    检查副本是否存在

    Args:
        dungeon_name: 副本名称

    Returns:
        bool: 副本是否存在
    """
    return dungeon_name in get_all_dungeons()


def get_zone_by_dungeon(dungeon_name):
    """
    根据副本名称获取所属区域

    Args:
        dungeon_name: 副本名称

    Returns:
        str: 区域名称，如果副本不存在则返回 None
    """
    for zone_name, dungeons in ZONE_DUNGEONS.items():
        for dungeon in dungeons:
            if dungeon["name"] == dungeon_name:
                return zone_name
    return None


def is_dungeon_selected(dungeon_name):
    """
    检查副本是否被选定

    Args:
        dungeon_name: 副本名称

    Returns:
        bool: 副本是否被选定，如果副本不存在则返回 False
    """
    for dungeons in ZONE_DUNGEONS.values():
        for dungeon in dungeons:
            if dungeon["name"] == dungeon_name:
                return dungeon["selected"]
    return False


def set_dungeon_selected(dungeon_name, selected=True):
    """
    设置副本的选定状态

    Args:
        dungeon_name: 副本名称
        selected: 是否选定，默认为 True

    Returns:
        bool: 是否设置成功
    """
    for dungeons in ZONE_DUNGEONS.values():
        for dungeon in dungeons:
            if dungeon["name"] == dungeon_name:
                dungeon["selected"] = selected
                return True
    return False


# 导出常用的变量和函数
__all__ = [
    "OCR_CORRECTION_MAP",
    "correct_ocr_text",
    "ZONE_DUNGEONS",
    "get_all_dungeons",
    "get_all_selected_dungeons",
    "get_dungeon_count",
    "get_selected_dungeon_count",
    "get_zone_count",
    "get_dungeons_by_zone",
    "get_selected_dungeons_by_zone",
    "is_valid_zone",
    "is_valid_dungeon",
    "get_zone_by_dungeon",
    "is_dungeon_selected",
    "set_dungeon_selected",
]
