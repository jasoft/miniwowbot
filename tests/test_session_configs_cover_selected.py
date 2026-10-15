"""含已选副本的配置必须被某个会话覆盖。

背景：``check_progress.py`` 会遍历 **``configs/`` 下所有配置文件** 判断当日是否
「全部完成」，而编排器 ``cron_run_all_dungeons.py`` 只跑 ``emulators.json`` 里
各会话 ``configs`` 列出的配置。两者之间**没有任何一致性保证** —— 只要有配置
选了副本却不在任何会话里，它永远不会被执行，``poe stats`` 就会恒返回
「N 个未完成」（退出码 1），编排器随即把整轮重试跑满 5 次并以结果码 1 收场
（每天白跑 4 轮「启模拟器→开会话→5 秒退出」）。

2026-10-15 实测：``configs/mage.json`` 的「亡灵之地」11 个副本全选（大王
10-14 20:33 编辑），但 ``7694ab6`` 单账号化时把 main 会话 ``configs`` 收缩成
``["warrior"]``，于是 06:05 那轮只跑了 warrior、``poe stats`` 报 mage 11 个
未打、退出码 1 触发重试。修复见 ``1f19034``（把 mage 加回 main 会话）。

本测试锁住这条不变量，让同类「配置漂移」在提交前就被拦下，而不是等到
第二天清晨静默烧掉一整轮。
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"
EMULATORS_JSON = PROJECT_ROOT / "emulators.json"


def _load_session_configs() -> set:
    """读取 ``emulators.json`` 中所有会话引用的配置名并集。

    Returns:
        set: 配置名集合（不含 ``.json`` 后缀）。
    """
    data = json.loads(EMULATORS_JSON.read_text(encoding="utf-8"))
    names: set = set()
    for session in data.get("sessions") or []:
        for cfg in session.get("configs") or []:
            normalized = str(cfg).strip()
            if normalized:
                names.add(normalized)
    return names


def _configs_with_selected_dungeons() -> dict:
    """列出所有在 ``zone_dungeons`` 里选中了副本的配置。

    只看 ``zone_dungeons``：``daily_tasks`` 由 ``config_loader`` 合成成「日常任务」
    区域，不是副本，``check_progress.py`` 的计数口径同样排除它。

    Returns:
        dict: ``{配置名: 已选副本数}``，仅包含已选副本数 > 0 的配置。
    """
    result: dict = {}
    for path in sorted(CONFIG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        zone_dungeons = data.get("zone_dungeons") or {}
        selected = 0
        for dungeons in zone_dungeons.values():
            if not isinstance(dungeons, list):
                continue
            for dungeon in dungeons:
                if isinstance(dungeon, dict) and dungeon.get("selected", False):
                    selected += 1
                elif isinstance(dungeon, str):
                    selected += 1
        if selected > 0:
            result[path.stem] = selected
    return result


def test_selected_configs_are_covered_by_sessions() -> None:
    """有已选副本的配置必须出现在某个会话的 ``configs`` 列表里。

    否则 ``check_progress.py`` 会永远判它「未完成」，整轮重试跑满仍以结果码 1 收场。
    """
    session_configs = _load_session_configs()
    selected_configs = _configs_with_selected_dungeons()

    uncovered = sorted(name for name in selected_configs if name not in session_configs)
    assert not uncovered, (
        f"以下配置选了副本，但没有任何会话（emulators.json）会执行它们：{uncovered}；"
        f"check_progress.py 会因此恒判「未完成」→ 编排器重试耗满后返回结果码 1。"
        f"请把它们加入对应会话的 configs，或将该配置的副本 selected 置 false。"
        f"（当前会话覆盖：{sorted(session_configs)}）"
    )


def test_session_configs_exist() -> None:
    """会话引用的每个配置都必须真的存在于 ``configs/`` 下（防拼写错误）。"""
    session_configs = _load_session_configs()
    missing = sorted(name for name in session_configs if not (CONFIG_DIR / f"{name}.json").exists())
    assert not missing, (
        f"emulators.json 引用了不存在的配置文件：{missing}；" f"运行时会因读不到配置而失败。"
    )
