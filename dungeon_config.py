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
# 格式: {"区域名称": ["副本1", "副本2", ...]}
ZONE_DUNGEONS = {
    # 风暴群岛
    "风暴群岛": [
        "真理之地",
        "预言神殿",
        "海底王宫",
        "泰坦密室",
        "黑暗庄园",
        "海底囚牢",
        "地精岛",
        "泰坦遗迹",
        "海盗监狱",
        "巨魔陵墓",
        "毒蛇神庙",
        "腐化沼泽",
        "海港城",
    ],
    # 军团领域
    "军团领域": [
        "大墓地密室",
        "流放王座",
        "毁灭之地",
        "大墓地圣殿",
        "封印地窟",
        "魔能宫殿",
        "魔能要塞",
        "魔法高台",
        "地底巢穴",
        "风暴绿洲",
        "渡鸦堡垒",
        "梦魇丛林",
        "黑暗神殿",
    ],
    # 暗影大陆
    "暗影大陆": [
        "钢铁码头",
        "食人魔王国",
        "黑暗熔炉",
        "通天峰",
        "熔渣车间",
        "食人魔矿井",
        "木精圣地",
        "鲜血庭院",
        "钢铁车站",
        "神圣陵墓",
        "兽人墓地",
        "毁灭高台",
    ],
    # 迷雾大陆
    "迷雾大陆": [
        "兽人圣殿",
        "恐魔之心",
        "古魔宝库",
        "兽人都城",
        "古魔宫殿",
        "风暴之巅",
        "酿酒厂",
        "风暴王座",
        "青龙寺",
        "白虎寺",
        "日落关",
        "玄牛寺",
    ],
    # 元素之地
    "元素之地": [
        "火焰宫殿",
        "守护者神殿",
        "黑龙宫殿",
        "黑暗堡垒",
        "潮汐宫殿",
        "黑暗监狱",
        "泰坦密室",
        "大地神殿",
        "失落之城",
        "天空之城",
        "黑石熔炉",
    ],
    # 冰封大陆
    "冰封大陆": [
        "泰坦基地",
        "冠军试炼",
        "寒冰堡垒",
        "寒冰王座",
        "灵魂熔炉",
        "瘟疫之城",
        "古代大厅",
        "古代王国",
        "巨魔要塞",
        "峡湾城堡",
        "蓝龙巢穴",
    ],
    # 虚空领域
    "虚空领域": [
        "魔法之井",
        "虚空要塞",
        "海底神殿",
        "守护者之塔上层",
        "黑暗神殿",
        "守护者之塔下层",
        "圣山战场",
        "虚空舰",
        "沼泽水库",
        "山丘城堡",
        "地狱火堡垒",
        "亡者之城",
    ],
    # 东部大陆
    "东部大陆": [
        "亡灵要塞",
        "黑龙巢穴",
        "火焰之心",
        "巨石密室",
        "诅咒教堂",
        "盗贼矿井",
        "机械要塞",
        "巨魔墓地",
        "噩梦洞穴",
        "野猪人高地",
        "水晶庭院",
        "龙人塔",
        "精灵遗迹",
        "沉没的神庙",
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
        all_dungeons.extend(dungeons)
    return all_dungeons


def get_dungeon_count():
    """
    获取副本总数

    Returns:
        int: 副本总数
    """
    return sum(len(dungeons) for dungeons in ZONE_DUNGEONS.values())


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
        list: 副本列表，如果区域不存在则返回空列表
    """
    return ZONE_DUNGEONS.get(zone_name, [])


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
        if dungeon_name in dungeons:
            return zone_name
    return None


# 导出常用的变量和函数
__all__ = [
    "OCR_CORRECTION_MAP",
    "correct_ocr_text",
    "ZONE_DUNGEONS",
    "get_all_dungeons",
    "get_dungeon_count",
    "get_zone_count",
    "get_dungeons_by_zone",
    "is_valid_zone",
    "is_valid_dungeon",
    "get_zone_by_dungeon",
]
