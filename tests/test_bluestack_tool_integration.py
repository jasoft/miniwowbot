#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`bluestack-tool.py` 真实 BlueStacks 集成测试。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "bluestack-tool.py"

spec = importlib.util.spec_from_file_location("bluestack_tool_integration", SCRIPT_PATH)
bluestack_tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["bluestack_tool_integration"] = bluestack_tool
spec.loader.exec_module(bluestack_tool)

pytestmark = pytest.mark.integration


def run_tool_command(*args: str) -> tuple[int, dict[str, Any]]:
    """运行 `bluestack-tool.py` 并返回退出码与 JSON 结果。

    Args:
        *args: 传递给脚本的命令行参数。

    Returns:
        `(returncode, payload)` 元组。
    """
    command = [sys.executable, str(SCRIPT_PATH), *args, "--format", "json"]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        cwd=PROJECT_ROOT,
    )
    payload = json.loads(completed.stdout)
    return completed.returncode, payload


def wait_for_instance_status(
    instance_id: str,
    expected_statuses: set[str],
    timeout: int = 60,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    """轮询实例状态直到命中目标状态。

    Args:
        instance_id: 要查询的实例 ID。
        expected_statuses: 期望命中的状态集合。
        timeout: 最长等待秒数。
        poll_interval: 轮询间隔秒数。

    Returns:
        最后一条状态载荷。

    Raises:
        AssertionError: 等待超时时抛出。
    """
    deadline = time.time() + timeout
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        _, payload = run_tool_command("status", "--id", instance_id)
        last_payload = payload
        status = payload["instance"]["status"]
        if status in expected_statuses:
            return payload
        time.sleep(poll_interval)

    raise AssertionError(f"等待实例 {instance_id} 状态超时，最后状态: {last_payload}")


@pytest.fixture(scope="module")
def target_instance_id() -> str:
    """返回用于真实启停测试的实例 ID。"""
    instance_id = "1"
    if bluestack_tool.resolve_instance_by_id(instance_id) is None:
        pytest.skip(f"未找到默认测试实例: {instance_id}")
    return instance_id


@pytest.fixture(scope="module")
def ensure_bluestacks_environment() -> None:
    """验证集成测试所需的 BlueStacks 运行环境。"""
    if sys.platform != "win32":
        pytest.skip("BlueStacks 集成测试仅支持 Windows")

    player_path = bluestack_tool.resolve_bluestacks_player_path(None)
    adb_path = bluestack_tool.resolve_adb_path(None)
    if not player_path:
        pytest.skip("未找到 BlueStacks Player，跳过集成测试")
    if not adb_path:
        pytest.skip("未找到 adb，跳过集成测试")


class TestBluestacksToolIntegration:
    """验证真实 BlueStacks 的启动与停止流程。"""

    def test_start_then_stop_instance(
        self, ensure_bluestacks_environment: None, target_instance_id: str
    ) -> None:
        """验证实例可以被真实启动并在测试结束前关闭。"""
        del ensure_bluestacks_environment

        # 预清理，避免上一次异常退出留下运行中的实例。
        run_tool_command("stop", "--id", target_instance_id, "--timeout", "30")
        wait_for_instance_status(target_instance_id, {"stopped"}, timeout=30)

        try:
            start_code, start_payload = run_tool_command(
                "start",
                "--id",
                target_instance_id,
                "--no-wait",
            )
            assert start_code == bluestack_tool.EXIT_OK
            assert start_payload["ok"] is True

            started_payload = wait_for_instance_status(
                target_instance_id,
                {"starting", "running"},
                timeout=30,
            )
            assert started_payload["instance"]["player_running"] is True

            stop_code, stop_payload = run_tool_command(
                "stop",
                "--id",
                target_instance_id,
                "--timeout",
                "60",
            )
            assert stop_code == bluestack_tool.EXIT_OK
            assert stop_payload["ok"] is True

            stopped_payload = wait_for_instance_status(
                target_instance_id,
                {"stopped"},
                timeout=30,
            )
            assert stopped_payload["instance"]["player_running"] is False
        finally:
            run_tool_command("stop", "--id", target_instance_id, "--timeout", "30")
            wait_for_instance_status(target_instance_id, {"stopped"}, timeout=30)
