"""pytest 全局测试隔离。

最重要的一条：**测试绝不能把通知真的发出去**。

2026-09-21 大王收到一条假告警：

    [unknown | unknown] ⚠️ 每日任务未完成
    每日任务未完成：exchange_purple_first
    结果：券已够（40/40）但兑换未生效
    截图：（截图失败）
    配置: unknown  模拟器: unknown

根因不是游戏流程有问题，而是有测试走到了**未打桩的真实通知链路**：
测试环境没有模拟器、也没有配置上下文，于是推送里「截图失败 / 配置 unknown」，
内容恰好就是该测试构造的 `balance=40` 场景。测试污染了真实告警渠道，
会让大王对着一条假消息排查半天。

这里在底层统一拦网：任何测试（包括将来新写的）都不可能再发出真实通知。
真的需要走通通知链路的测试，用 `@pytest.mark.allow_real_notifications` 显式豁免。

被拦下不等于静默——测试若触发了通知，会被判为失败并提示补打桩，
免得「忘了 mock」再演变成线上假告警。
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest

import auto_dungeon_notification as _notification

#: 通知模块里所有可能真正发出网络请求的入口
_TRANSPORT_NAMES = (
    "send_notification",
    "send_pushover_notification",
    "send_pushover_html_notification",
    "send_bark_notification",
)

#: 被拦下的通知尝试写到这里，便于事后排查
_ATTEMPT_LOG = os.path.join("log", "_blocked_test_notifications.txt")

_LOCAL_REFS: list[tuple[Any, str]] | None = None


def _blocked_ids() -> set[int]:
    """收集通知模块里「会真正发出去」的函数 id。

    Returns:
        set[int]: 需要拦截的函数的 :func:`id` 集合。
    """
    ids: set[int] = set()
    for name in _TRANSPORT_NAMES:
        func = getattr(_notification, name, None)
        if callable(func):
            ids.add(id(func))
    return ids


def _local_refs() -> list[tuple[Any, str]]:
    """找出「绕过模块属性」的本地引用。

    `from auto_dungeon_notification import send_notification` 会在调用方模块里
    留下一份独立引用，只改通知模块的属性对它无效，必须逐个替换。

    结果在首次调用时计算并缓存 —— 那时收集阶段已完成，各测试模块都已导入。

    Returns:
        list[tuple[Any, str]]: ``(模块, 属性名)`` 列表。
    """
    global _LOCAL_REFS
    if _LOCAL_REFS is None:
        blocked = _blocked_ids()
        refs: list[tuple[Any, str]] = []
        for module in list(sys.modules.values()):
            if module is None or module is _notification:
                continue
            for attr, value in list(vars(module).items()):
                if callable(value) and id(value) in blocked:
                    refs.append((module, attr))
        _LOCAL_REFS = refs
    return _LOCAL_REFS


def _record_attempts(nodeid: str, attempts: list[tuple[Any, Any]]) -> None:
    """把被拦下的通知尝试追加到日志文件。

    Args:
        nodeid: 触发通知的测试节点 ID。
        attempts: 被拦下的 ``(args, kwargs)`` 列表。
    """
    try:
        os.makedirs(os.path.dirname(_ATTEMPT_LOG), exist_ok=True)
        with open(_ATTEMPT_LOG, "a", encoding="utf-8") as fh:
            for args, kwargs in attempts:
                fh.write(f"{nodeid}\t{args!r}\t{kwargs!r}\n")
    except OSError:  # pragma: no cover - 纯记录用途，失败不影响测试结论
        pass


@pytest.fixture(autouse=True)
def block_real_notifications(request: pytest.FixtureRequest, monkeypatch) -> Any:
    """封掉所有真实通知出口，并在测试触发通知时判失败。

    Args:
        request: pytest 请求对象，用于读取豁免标记。
        monkeypatch: pytest 打桩工具。

    Yields:
        None: 测试执行期间生效。
    """
    if request.node.get_closest_marker("allow_real_notifications"):
        yield
        return

    attempts: list[tuple[Any, Any]] = []

    def _blocked_send(*args: Any, **kwargs: Any) -> bool:
        attempts.append((args, kwargs))
        return False

    for name in _TRANSPORT_NAMES:
        if hasattr(_notification, name):
            monkeypatch.setattr(_notification, name, _blocked_send)
    for module, attr in _local_refs():
        monkeypatch.setattr(module, attr, _blocked_send, raising=False)

    yield

    if attempts:
        _record_attempts(request.node.nodeid, attempts)
        first = attempts[0]
        pytest.fail(
            f"测试试图发出真实通知 {len(attempts)} 次，已被拦下：{first[0]!r}。\n"
            "请在该测试里给 `_notify_step_failure` / `send_notification` 打桩，"
            "否则会给大王推假告警。"
        )
