"""体检报告通知通道的行为锁定。

覆盖四件事：

1. 体检报告走 ``BARK_HEALTH_SERVER`` 独立通道（未配置时回落 ``BARK_SERVER``）；
2. 体检报告**不**叠加 ``[config | emulator]`` 上下文；
3. 超长正文被截断到 Bark 能接受的 URL 长度内（否则整条推送会失败）；
4. ``setup_simple_logger`` 会挂上下文 filter —— 不挂时格式串里的
   ``%(config)s`` 会让每次打日志都抛 ``ValueError``。

所有网络出口都被打桩：``tests/conftest.py`` 的 autouse 拦网会判真实通知为失败，
所以需要走通派发链路的用例显式标 ``@pytest.mark.allow_real_notifications``，
并把 ``requests.get`` 换成替身（``captured_requests`` fixture）。
"""

import logging
import urllib.parse
from typing import Any, Dict, List

import pytest

import auto_dungeon_notification as notif
import logger_config
from logger_config import _ContextFilter

HEALTH_SERVER = "https://api.day.app/health_key/"
DEFAULT_SERVER = "https://api.day.app/default_key/"


class _FakeResponse:
    """最小可用的 ``requests.Response`` 替身。"""

    status_code = 200
    text = '{"code":200,"message":"success"}'


class _FakeSystemConfig:
    """最小可用的系统配置替身。"""

    def __init__(self, bark_config: Dict[str, Any]) -> None:
        self._bark_config = bark_config

    def is_bark_enabled(self) -> bool:
        """Bark 视为已启用。"""
        return True

    def get_bark_config(self) -> Dict[str, Any]:
        """返回注入的 Bark 配置。"""
        return self._bark_config


@pytest.fixture
def captured_requests(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    """打桩 ``requests.get``，把每次调用记录下来。

    Returns:
        list[dict]: 每次调用的 ``{"url": ..., "params": ...}``。
    """
    calls: List[Dict[str, Any]] = []

    def fake_get(url: str, params: Dict[str, Any] | None = None, **_kw: Any):
        calls.append({"url": url, "params": params or {}})
        return _FakeResponse()

    monkeypatch.setattr(notif.requests, "get", fake_get)
    return calls


def _patch_config(monkeypatch: pytest.MonkeyPatch, bark_config: Dict[str, Any]) -> None:
    """把通知模块读到的系统配置换成替身。

    Args:
        monkeypatch: pytest 打桩工具。
        bark_config: 要注入的 Bark 配置字典。
    """
    monkeypatch.setattr(notif, "_get_notification_config", lambda: _FakeSystemConfig(bark_config))


@pytest.mark.allow_real_notifications
def test_health_report_uses_dedicated_channel_and_skips_context(
    monkeypatch: pytest.MonkeyPatch, captured_requests: List[Dict[str, Any]]
) -> None:
    """体检报告走独立通道，且正文里不出现上下文后缀。"""
    _patch_config(
        monkeypatch,
        {"enabled": True, "server": DEFAULT_SERVER, "health_server": HEALTH_SERVER},
    )

    ok = notif.send_health_report("体检 ✅", "warrior 11/11\nmage_alt 9/10")

    assert ok is True
    assert len(captured_requests) == 1
    url = captured_requests[0]["url"]
    assert url.startswith(HEALTH_SERVER.rstrip("/")), f"没走体检通道: {url}"
    assert DEFAULT_SERVER.rstrip("/") not in url

    decoded = urllib.parse.unquote(url)
    assert "体检 ✅" in decoded
    assert "配置:" not in decoded, "全局体检报告不该带「配置: xxx」后缀"
    assert "模拟器:" not in decoded
    assert "%5B" not in url, "标题不该带 [config | emulator] 前缀"


@pytest.mark.allow_real_notifications
def test_health_report_falls_back_to_default_server(
    monkeypatch: pytest.MonkeyPatch, captured_requests: List[Dict[str, Any]]
) -> None:
    """未配置体检通道时回落到 ``BARK_SERVER``，而不是直接失败。"""
    _patch_config(monkeypatch, {"enabled": True, "server": DEFAULT_SERVER, "health_server": ""})

    ok = notif.send_health_report("体检", "内容")

    assert ok is True
    assert captured_requests[0]["url"].startswith(DEFAULT_SERVER.rstrip("/"))


@pytest.mark.allow_real_notifications
def test_health_report_keeps_group_and_level(
    monkeypatch: pytest.MonkeyPatch, captured_requests: List[Dict[str, Any]]
) -> None:
    """组名与级别仍然生效（体检异常时需要 timeSensitive 才容易被看到）。"""
    _patch_config(
        monkeypatch,
        {
            "enabled": True,
            "server": DEFAULT_SERVER,
            "health_server": HEALTH_SERVER,
            "group": "dungeon_helper",
        },
    )

    notif.send_health_report("体检 ❌", "有异常", level="timeSensitive")

    params = captured_requests[0]["params"]
    assert params["group"] == "dungeon_helper"
    assert params["level"] == "timeSensitive"


def test_truncate_for_url_leaves_short_message_untouched() -> None:
    """短正文原样返回，且不标记截断。"""
    text = "一切正常"
    result, truncated = notif._truncate_for_url(text, 500)
    assert result == text
    assert truncated is False


def test_truncate_for_url_marks_and_fits_long_message() -> None:
    """超长正文必须被截断到预算内，并留下可见标记。"""
    text = "异常" * 2000
    budget = 300
    result, truncated = notif._truncate_for_url(text, budget)

    assert truncated is True
    assert result.endswith("已截断）")
    assert len(urllib.parse.quote(result, safe="")) <= budget


@pytest.mark.allow_real_notifications
def test_long_health_report_url_stays_within_bark_limit(
    monkeypatch: pytest.MonkeyPatch, captured_requests: List[Dict[str, Any]]
) -> None:
    """端到端：极长体检报告拼出的 URL 不能超过 Bark 上限。"""
    _patch_config(
        monkeypatch,
        {"enabled": True, "server": DEFAULT_SERVER, "health_server": HEALTH_SERVER},
    )

    ok = notif.send_health_report("体检报告", "很长的一行" * 2000)

    assert ok is True
    url = captured_requests[0]["url"]
    assert len(url) <= notif.BARK_MAX_URL_LENGTH, f"URL 超长将被 Bark 拒绝: {len(url)}"


def test_simple_logger_attaches_context_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """``setup_simple_logger`` 必须挂上下文 filter。

    格式串 ``DEFAULT_SIMPLE_FORMAT`` 含 ``%(config)s %(emulator)s``，
    而 ``logging.basicConfig`` 不会自动注入这两个字段 —— 不挂 filter 时
    每次打日志都会抛 ``ValueError: Formatting field not found in record``。
    """
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    for handler in saved_handlers:
        root.removeHandler(handler)

    try:
        logger_config.setup_simple_logger(level="INFO")
        handlers = list(logging.getLogger().handlers)
        assert handlers, "basicConfig 应当挂上 handler"

        for handler in handlers:
            assert any(
                isinstance(f, _ContextFilter) for f in handler.filters
            ), "handler 缺上下文 filter，格式串里的 %(config)s 会抛 ValueError"

        # 真打一条，确认格式化不再炸
        logging.getLogger("filter_probe").info("格式检查")
    finally:
        for handler in list(logging.getLogger().handlers):
            if handler not in saved_handlers:
                logging.getLogger().removeHandler(handler)
                handler.close()
        for handler in saved_handlers:
            root.addHandler(handler)
