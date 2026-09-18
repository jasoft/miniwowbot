"""`check_progress` 每日任务统计回归测试。"""

from __future__ import annotations

import json

from config_loader import ConfigLoader
from check_progress import ProgressChecker
import check_progress


def test_load_config_dungeons_excludes_daily_tasks(
    tmp_path,
    monkeypatch,
) -> None:
    """验证副本进度检查不把「日常任务」算进副本列表。

    「日常任务」是 `ConfigLoader` 从 `daily_tasks` 合成后并入 `zone_dungeons` 的，
    它不是副本。若计入，日常任务里当天做不完的项目会让整轮检查恒判「未完成」，
    导致退出码恒 1 并触发整轮重试。

    Args:
        tmp_path: pytest 提供的临时目录。
        monkeypatch: pytest 的 monkeypatch 工具。
    """
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    config_path = configs_dir / "warrior.json"
    config_path.write_text(
        json.dumps(
            {
                "class": "战士",
                "daily_tasks": [
                    {"name": "领取挂机奖励", "selected": True},
                    {"name": "领取邮件", "selected": False},
                ],
                "zone_dungeons": {
                    "风暴群岛": [
                        {"name": "真理之地", "selected": True},
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        check_progress,
        "load_config",
        lambda _config_name: ConfigLoader(str(config_path)),
    )

    checker = ProgressChecker(db_path=str(tmp_path / "progress.db"))
    try:
        zone_dungeons, all_dungeons = checker._load_config_dungeons("warrior")
    finally:
        checker.close()

    # 副本计数口径：日常任务一律排除
    assert ("日常任务", "领取挂机奖励") not in all_dungeons
    assert ("日常任务", "领取邮件") not in all_dungeons
    assert "日常任务" not in zone_dungeons

    # 真副本不受影响
    assert ("风暴群岛", "真理之地") in all_dungeons
    assert "风暴群岛" in zone_dungeons
