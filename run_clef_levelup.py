"""运行有界的 Clef 游戏升级实验，并记录可复查的决策轨迹。"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import cv2
from airtest.core.api import auto_setup, device, snapshot
from vibe_ocr import OCRHelper

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "levelup.air"))

from clef_client import ClefClient
from clef_policy import (
    allowed_actions, build_observation, execute_action, supplement_combat_signal,
)
from config import configure_airtest
from detectors import scan_fast, scan_workflow
from game_actions import GameActions
from state import WorldState
from templates import build_templates
from actions import back_to_main


async def refresh(state: WorldState) -> None:
    """串行刷新检测信号，避免动作和截图竞争。

    Args:
        state: 需要更新的世界状态。
    """
    await scan_fast(state)
    await scan_workflow(state, 0)


async def run_experiment(args: argparse.Namespace) -> int:
    """运行模型观察、复核和动作执行闭环。

    Args:
        args: 命令行配置。

    Returns:
        正常结束返回0；API或动作连续失败返回1。
    """
    client = ClefClient(args.timeout)
    auto_setup(
        str(ROOT / "levelup.air" / "levelup.py"),
        devices=[f"Android://127.0.0.1:5037/{args.emulator}"],
        project_root=str(ROOT),
        compress=90,
    )
    os.environ["ANDROID_SERIAL"] = device().uuid
    configure_airtest()
    ocr = OCRHelper(snapshot_func=snapshot)
    state = WorldState(ocr=ocr, actions=GameActions(ocr), templates=build_templates())
    if args.execute:
        back_to_main(state)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    executed: Counter[str] = Counter()
    latencies: list[float] = []
    tokens = 0
    failures = 0
    total_errors = 0
    idle_steps = 0
    exit_code = 0
    started = time.monotonic()
    trace_path = output / "decisions.jsonl"
    with trace_path.open("w", encoding="utf-8") as trace:
        for step in range(args.steps):
            if time.monotonic() - started >= args.max_seconds:
                break
            record: dict = {"step": step, "mode": "execute" if args.execute else "observe"}
            try:
                await refresh(state)
                frame = device().snapshot()
                if frame.shape[:2] != (1280, 720):
                    raise ValueError("现有动作坐标要求720×1280画面，请调整模拟器分辨率")
                success, encoded = cv2.imencode(".png", frame)
                if not success:
                    raise ValueError("截图编码失败")
                image = encoded.tobytes()
                image_path = output / f"screen_{step:04d}.png"
                image_path.write_bytes(image)
                # 模型观察中的 OCR 与上传图片来自同一帧。
                texts = ocr.get_all_texts_from_image(str(image_path))
                supplement_combat_signal(state, texts)
                observation = build_observation(state, texts)
                if observation["allowed_actions"] == ["wait"]:
                    idle_steps += 1
                    failures = 0
                    record.update({"observation": observation, "execution_reason": "idle_no_api"})
                    trace.write(json.dumps(record, ensure_ascii=False) + "\n")
                    trace.flush()
                    await asyncio.sleep(args.interval)
                    continue
                # 网关会估算 base64 的令牌数；使用小 JPEG 避免原始 PNG 被拒绝。
                success, compressed = cv2.imencode(
                    ".jpg", cv2.resize(frame, (360, 640)), [cv2.IMWRITE_JPEG_QUALITY, 70]
                )
                if not success:
                    raise ValueError("模型截图压缩失败")
                decision = client.decide(
                    observation, None if args.text_only else compressed.tobytes(), "image/jpeg"
                )
                record.update({"observation": observation, "decision": asdict(decision)})
                counts[decision.action] += 1
                latencies.append(decision.latency_seconds)
                tokens += decision.input_tokens
                reason = "observe_only"
                called = False
                if args.execute:
                    if decision.confidence < args.min_confidence:
                        reason = "low_confidence"
                    elif time.monotonic() - started >= args.max_seconds:
                        reason = "time_budget"
                    else:
                        await refresh(state)
                        fresh_frame = device().snapshot()
                        fresh_path = output / f"fresh_{step:04d}.png"
                        cv2.imwrite(str(fresh_path), fresh_frame)
                        supplement_combat_signal(
                            state, ocr.get_all_texts_from_image(str(fresh_path))
                        )
                        record["fresh_allowed_actions"] = allowed_actions(state)
                        called = execute_action(decision.action, state)
                        reason = "handler_called" if called else "wait_or_changed_state"
                        if called:
                            executed[decision.action] += 1
                            record["after_ocr"] = ocr.capture_and_get_all_texts(use_cache=False)
                record.update({"handler_called": called, "execution_reason": reason})
                logging.info(
                    "第%d步: %s confidence=%.3f API=%.2fs %s",
                    step, decision.action, decision.confidence, decision.latency_seconds, reason,
                )
                failures = 0
            except (RuntimeError, ValueError) as exc:
                exit_code = 1
                total_errors += 1
                failures += 1
                record["error"] = str(exc)
                logging.error("第%d步失败: %s", step, exc)
            except Exception as exc:
                exit_code = 1
                total_errors += 1
                failures += 1
                # 第三方异常可能带有环境配置，只保存异常类型。
                record["error"] = type(exc).__name__
                logging.error("第%d步失败，异常类型: %s", step, type(exc).__name__)
            trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            trace.flush()
            if failures >= 3:
                exit_code = 1
                break
            await asyncio.sleep(args.interval)
    summary = {
        "mode": "execute" if args.execute else "observe",
        "decisions": dict(counts),
        "handlers_called": dict(executed),
        "api_calls_succeeded": len(latencies),
        "idle_steps_without_api": idle_steps,
        "errors": total_errors,
        "api_mean_seconds": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "input_tokens": tokens,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "exit_code": exit_code,
        "note": "处理器调用不等于任务成功；需结合after_ocr与工作流日志验证。",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return exit_code


def main() -> int:
    """解析实验配置并启动运行。

    Returns:
        实验进程退出码。
    """
    parser = argparse.ArgumentParser(description="Clef Typesafe 升级实验（默认仅观察）")
    parser.add_argument("--emulator", default="127.0.0.1:5565")
    parser.add_argument("--execute", action="store_true", help="实际执行白名单游戏动作")
    parser.add_argument("--text-only", action="store_true", help="仅发送OCR和信号，不上传图片")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--max-seconds", type=float, default=180)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument("--output", default="output/clef-levelup")
    args = parser.parse_args()
    if (
        args.steps <= 0 or args.max_seconds <= 0 or args.interval < 0
        or args.timeout <= 0 or not 0 <= args.min_confidence <= 1
    ):
        parser.error("步数、时限及超时必须为正，间隔非负，置信度必须位于0到1")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("airtest").setLevel(logging.CRITICAL)
    try:
        return asyncio.run(run_experiment(args))
    except (RuntimeError, ValueError) as exc:
        logging.error("实验未启动: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
