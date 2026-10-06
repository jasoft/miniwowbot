"""验证 Typesafe 响应校验和游戏动作的执行边界。"""

# ruff: noqa: E402

import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parents[2]))

import clef_client
import clef_policy
from clef_client import ACTION_CRITERIA, ClefClient, parse_decision
from state import WorldState


def response_payload(action: str = "wait") -> dict:
    """构造与官方协议一致的响应。

    Args:
        action: 最高概率动作。

    Returns:
        Cloudflare 包装后的成功响应。
    """
    return {
        "success": True,
        "result": {
            "answers": {"action": {
                "type": "choice", "choice": action, "confidence": 0.9,
                "probabilities": {key: float(key == action) for key in ACTION_CRITERIA},
            }},
            "usage": {"input_tokens": 123},
        },
    }


@pytest.mark.parametrize("invalid", ["unknown", "nan", "sum", "missing", "wrong_max", "bool"])
def test_reject_invalid_decisions(invalid: str) -> None:
    """拒绝未知动作、非有限概率、错误概率和缺失结构。

    Args:
        invalid: 无效响应的类型。
    """
    payload = response_payload()
    answer = payload["result"]["answers"]["action"]
    if invalid == "unknown":
        answer["choice"] = "shell"
    elif invalid == "nan":
        answer["confidence"] = float("nan")
    elif invalid == "sum":
        answer["probabilities"]["complete"] = 0.5
    elif invalid == "missing":
        del answer["probabilities"]
    elif invalid == "wrong_max":
        answer["choice"] = "complete"
    else:
        answer["confidence"] = True
    with pytest.raises(ValueError):
        parse_decision(payload, 1.2)


def test_valid_response() -> None:
    """保留动作概率、置信度和耗时。"""
    decision = parse_decision(response_payload("request"), 1.2)
    assert decision.action == "request"
    assert decision.latency_seconds == 1.2
    assert decision.input_tokens == 123


def test_client_uses_typed_questions_and_embedded_image(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实客户端请求使用类型化问题与嵌入图片。

    Args:
        monkeypatch: 环境及请求替换工具。
    """
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("CLOUDFLARE_AUTH_TOKEN", "test-token")
    post = Mock(return_value=Mock(status_code=200, json=lambda: response_payload()))
    monkeypatch.setattr(clef_client.requests, "post", post)
    assert ClefClient().decide({}, b"image", "image/jpeg").action == "wait"
    body = post.call_args.kwargs["json"]
    assert body["questions"]["action"]["type"] == "choice"
    assert body["images"] == [{"content_type": "image/jpeg", "base64": "aW1hZ2U="}]


def test_network_errors_do_not_disclose_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """网络异常中的凭据与URL不会传播到日志。

    Args:
        monkeypatch: 环境及请求替换工具。
    """
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "private-account")
    monkeypatch.setenv("CLOUDFLARE_AUTH_TOKEN", "private-token")
    monkeypatch.setattr(
        clef_client.requests, "post", Mock(side_effect=requests.Timeout("private-token"))
    )
    with pytest.raises(RuntimeError) as error:
        ClefClient().decide({})
    assert "private" not in str(error.value)


def test_missing_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """配置缺失时在设备动作开始前失败。

    Args:
        monkeypatch: 环境替换工具。
    """
    monkeypatch.delenv("CLOUDFLARE_AUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="CLOUDFLARE_AUTH_TOKEN"):
        ClefClient()


def test_stale_request_is_rejected_when_combat_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    """请求期间进入战斗时，不执行旧的领取决策。

    Args:
        monkeypatch: 动作替换工具。
    """
    state = WorldState(ocr=Mock(), actions=Mock(), templates={})
    state.signals["request_task_el"] = Mock()
    assert "request" in clef_policy.allowed_actions(state)
    state.signals["in_combat"] = True
    handler = Mock()
    monkeypatch.setitem(clef_policy.ACTION_HANDLERS, "request", handler)
    assert not clef_policy.execute_action("request", state)
    handler.assert_not_called()


def test_completion_preempts_combat_and_timeout() -> None:
    """交任务信号优先于战斗与超时。"""
    state = WorldState(ocr=Mock(), actions=Mock(), templates={})
    state.signals.update(task_complete_pos=(30, 40), in_combat=True)
    state.last_task_time = time.time() - 200
    assert clef_policy.allowed_actions(state) == ["complete", "wait"]
    assert not clef_policy.execute_action("combat", state)


def test_request_cooldown_and_unknown_action() -> None:
    """领取冷却期不调用领取处理器，未知动作也不执行。"""
    state = WorldState(ocr=Mock(), actions=Mock(), templates={})
    state.signals["request_task_el"] = Mock()
    state.request_retry_after = time.time() + 30
    assert clef_policy.allowed_actions(state) == ["wait"]
    assert not clef_policy.execute_action("shell", state)


def test_request_dispatches_existing_region_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型领取动作调用已验证的任务扫描和区域切换工具。

    Args:
        monkeypatch: 动作替换工具。
    """
    state = WorldState(ocr=Mock(), actions=Mock(), templates={})
    state.signals["request_task_el"] = Mock()
    handler = Mock()
    monkeypatch.setitem(clef_policy.ACTION_HANDLERS, "request", handler)
    assert clef_policy.execute_action("request", state)
    handler.assert_called_once_with(state)


def test_request_schema_excludes_unavailable_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """战斗状态只提交战斗和等待，减少模型选择不存在的按钮。

    Args:
        monkeypatch: 环境及请求替换工具。
    """
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("CLOUDFLARE_AUTH_TOKEN", "test-token")
    payload = response_payload("combat")
    payload["result"]["answers"]["action"]["probabilities"] = {"combat": 1.0, "wait": 0.0}
    post = Mock(return_value=Mock(status_code=200, json=lambda: payload))
    monkeypatch.setattr(clef_client.requests, "post", post)
    decision = ClefClient().decide({"allowed_actions": ["combat", "wait"]})
    assert decision.action == "combat"
    assert set(post.call_args.kwargs["json"]["questions"]["action"]["criteria"]) == {
        "combat", "wait",
    }


def test_combat_requires_health_and_multiple_cooldowns() -> None:
    """血量与技能冷却共同存在时才补充战斗信号。"""
    state = WorldState(ocr=Mock(), actions=Mock(), templates={})
    health = {"text": "127K/598K", "center": (360, 420)}
    cooldowns = [{"text": "20", "center": (x, 645)} for x in (140, 270, 400)]
    clef_policy.supplement_combat_signal(state, [health])
    assert not state.signals.get("combat_controls_visible")
    clef_policy.supplement_combat_signal(state, [health, *cooldowns])
    assert state.signals["combat_controls_visible"]
    assert not state.signals.get("in_combat")
    clef_policy.supplement_combat_signal(state, [health, *cooldowns, {"text": "接受任务"}])
    assert not state.signals["combat_controls_visible"]


def test_background_skills_do_not_block_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """背景技能可见时仍可接任务，技能调用后不污染副本战斗信号。

    Args:
        monkeypatch: 动作替换工具。
    """
    state = WorldState(ocr=Mock(), actions=Mock(), templates={})
    state.signals.update(request_task_el=Mock(), combat_controls_visible=True)
    assert "request" in clef_policy.allowed_actions(state)
    handler = Mock()
    monkeypatch.setitem(clef_policy.ACTION_HANDLERS, "combat", handler)
    assert clef_policy.execute_action("combat", state)
    handler.assert_called_once_with(state)
    assert not state.signals["in_combat"]
