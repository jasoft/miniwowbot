"""用合成状态验证真实 Clef API 的动作选择，禁止连接游戏设备。"""

# ruff: noqa: E402

import json
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "levelup.air"))
load_dotenv(ROOT / ".env")

from clef_client import ClefClient

CASES = (
    ("交任务优先", "complete", ["complete", "wait"], "A completed quest icon is visible."),
    ("领取与切区工具", "request", ["request", "wait"], "Not in combat. Request quests is visible."),
    ("使用战斗技能", "combat", ["combat", "wait"], "Active combat with HP bar and skill cooldowns."),
    ("推进副本", "advance", ["advance", "wait"], "Not in combat. Dungeon XP is full."),
    ("装备物品", "equip", ["equip", "wait"], "Not in combat. A new item has an equip button."),
    ("超时恢复", "recover", ["recover", "wait"], "Not in combat. No progress for 180 seconds."),
    ("领取优先于装备", "request", ["request", "equip", "wait"], "Not in combat. Can request and equip."),
    ("推进优先于装备", "advance", ["advance", "equip", "wait"], "Not in combat. XP full and can equip."),
)


def main() -> int:
    """调用真实模型并保存合成状态评估结果。

    Returns:
        所有案例符合预期返回0，否则返回1。
    """
    client = ClefClient()
    records = []
    for name, expected, allowed, description in CASES:
        observation = {
            "goal": "Level up continuously. Request quests before advancing, then equip items.",
            "allowed_actions": allowed,
            "description": description,
        }
        decision = client.decide(observation)
        records.append({
            "name": name, "expected": expected, "matched": decision.action == expected,
            "observation": observation, "decision": asdict(decision),
        })
    result = {
        "kind": "synthetic_states_real_api",
        "correct": sum(record["matched"] for record in records),
        "total": len(records), "cases": records,
    }
    target = ROOT / "output" / "clef-evaluation.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["correct"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
