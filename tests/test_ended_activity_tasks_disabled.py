"""已下架活动的日常任务必须处于关闭状态。

背景：游戏里的限时活动会随版本下架，主界面入口随之消失。项目里所有
``daily_tasks`` 都挂在 ``configs/*.json`` 上，活动下架后如果忘了改配置，
脚本每天都会在「入口找不到」这一步失败并推一条「每日任务未完成」告警，
但**记录不到任何真实故障**（纯噪音）。

本项目已经踩过两次同类坑：

* 「猎魔试炼」——活动结束后置 ``selected: false``；
* 「灵魂之塔签到」——2026-10-04 起主界面入口消失（``Found: '灵魂之塔'``
  连续 10 天可读、当天两个会话同时读不到），需要同步置 ``false``。

同时锁一条「两个 config 必须一致」的不变量：历史上出现过只改
``warrior.json``、漏掉 ``mage_alt.json``，导致次日另一个会话继续告警。
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"

#: 已下架活动的日常任务名 -> 下架说明（新增时把原因写在这里）。
ENDED_ACTIVITY_TASKS = {
    "猎魔试炼": "活动已结束，主界面入口消失",
    "灵魂之塔签到": "2026-10-04 起主界面入口消失（连续 10 天可读后当天两会话同时读不到）",
}


def _load_daily_tasks(config_name: str) -> dict:
    """读取某个配置里的日常任务选中状态。

    Args:
        config_name: 配置文件名（不含 ``.json``）。

    Returns:
        dict: ``{任务名: selected}``；未定义 ``daily_tasks`` 时为空字典。
    """
    path = CONFIG_DIR / f"{config_name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["name"]: item.get("selected", False) for item in data.get("daily_tasks") or []}


def _configs_with_daily_tasks() -> list:
    """列出所有定义了 ``daily_tasks`` 的配置名。

    Returns:
        list: 配置名（不含扩展名），按字典序排列。
    """
    names = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("daily_tasks"):
            names.append(path.stem)
    return names


@pytest.mark.parametrize("config_name", _configs_with_daily_tasks())
def test_ended_activity_tasks_are_disabled(config_name: str) -> None:
    """已下架活动的日常任务在每个配置里都必须是 ``selected: false``。"""
    tasks = _load_daily_tasks(config_name)
    enabled = [name for name in ENDED_ACTIVITY_TASKS if tasks.get(name)]

    assert not enabled, (
        f"{config_name}.json 仍启用了已下架活动的日常任务 {enabled}；"
        "活动结束后必须置 selected: false，否则每天产生一条无意义的告警"
    )


def test_daily_tasks_selection_is_consistent_across_configs() -> None:
    """多个配置的日常任务选中集合必须一致（防止只改一个配置）。"""
    configs = _configs_with_daily_tasks()
    assert len(configs) >= 2, f"预期至少两个配置定义 daily_tasks，实际 {configs}"

    baseline_name = configs[0]
    baseline = _load_daily_tasks(baseline_name)
    for other_name in configs[1:]:
        other = _load_daily_tasks(other_name)
        assert other == baseline, (
            f"{other_name}.json 与 {baseline_name}.json 的日常任务选中状态不一致："
            f"{other_name}={other} vs {baseline_name}={baseline}"
        )
