"""
auto_dungeon 通知模块

支持多种通知服务（Bark、Pushover），通过 .env 配置选择使用哪种服务。
提供统一的发送接口，自动处理不同服务的参数差异。

审计约定（2026-09-21 起）
-------------------------
**每一条通知都必须留下落盘记录**，不论成功、失败还是被跳过。
原因是 2026-09-21 收到一条 ``[unknown | unknown]`` 且「截图失败」的告警，
却无从判断它由谁发出、当时上下文是什么 —— 因为通知链路本身不留痕迹。

记录写在项目根（非 cwd）下：

- ``log/notifications/YYYY-MM-DD.jsonl`` —— 机器可读，一条通知一行 JSON；
- ``log/notifications.log`` —— 人读，带时间戳的一行摘要。

两者都由本模块**自己**写文件，不依赖 root logger 是否挂了文件 handler，
所以无论从 cron、pytest 还是交互式脚本调用，都一定能落到磁盘。
"""

import json
import logging
import os
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from auto_dungeon_container import get_container
from logger_config import GlobalLogContext
from system_config_loader import load_system_config

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


# ---------------------------------------------------------------------------
# 通知审计：保证「谁在什么时候发了什么、结果如何」可以事后回溯
# ---------------------------------------------------------------------------

#: 审计 JSONL 所在目录（相对项目根）
AUDIT_DIR_NAME = "notifications"
#: 人读审计日志（相对项目根 log/）
AUDIT_TEXT_NAME = "notifications.log"

#: 上下文缺失（config/emulator 取不到）只提示一次，避免刷屏
_context_missing_warned = False


def _project_log_path(*parts: str) -> Path:
    """拼出项目根下的 log 路径，**不依赖当前工作目录**。

    cron 由计划任务拉起、工作目录未必是项目根；早期用 ``os.getcwd()``
    拼路径的写法会把日志散落到别处（实测出现过 0 字节的
    ``autodungeon_unknown.log``）。

    Args:
        *parts: 相对 ``log/`` 的路径片段。

    Returns:
        Path: 绝对路径。
    """
    from project_paths import resolve_project_path

    return resolve_project_path("log", *parts)


def _caller_hint() -> str:
    """返回「第一个不在本模块里的调用帧」，用于回答「这条通知是谁发的」。

    Returns:
        str: 形如 ``auto_dungeon_daily.py:360 in _notify_step_failure``；
        无法定位时返回 ``unknown``。
    """
    try:
        frame = sys._getframe(2)
        while frame is not None and frame.f_globals.get("__name__") == __name__:
            frame = frame.f_back
        if frame is None:
            return "unknown"
        return (
            f"{os.path.basename(frame.f_code.co_filename)}:"
            f"{frame.f_lineno} in {frame.f_code.co_name}"
        )
    except Exception:  # pragma: no cover - 纯诊断信息
        return "unknown"


def _resolve_log_context() -> tuple[str, str, bool]:
    """解析通知里要展示的 config / emulator，并报告上下文是否缺失。

    ``unknown`` 有两种可能：真的不知道，或者**根本没设置上下文**。
    后者是代码问题（例如从测试或临时脚本里发通知），必须能区分出来。

    Returns:
        tuple[str, str, bool]: ``(config, emulator, 上下文是否缺失)``。
    """
    _container = get_container()
    ctx = GlobalLogContext.context

    ctx_cfg = ctx.get("config")
    ctx_emu = ctx.get("emulator")
    cfg = ctx_cfg or (_container.config_name or "unknown")
    emu = ctx_emu or (_container.target_emulator or "unknown")

    cfg_missing = not ctx_cfg and not _container.config_name
    emu_missing = not ctx_emu and not _container.target_emulator
    return cfg, emu, bool(cfg_missing or emu_missing)


def _audit_notification(
    event: str,
    provider: str,
    title: str,
    message: str,
    ok: bool,
    reason: Optional[str] = None,
    **extra: Any,
) -> None:
    """把一条通知记录写盘（JSONL + 人读日志）。

    绝不抛异常：审计失败不能影响通知本身，更不能阻断主流程。

    Args:
        event: 事件类型，``sent`` / ``failed`` / ``skipped`` / ``blocked_test``。
        provider: 通知服务名。
        title: 通知标题（**原始**标题，未叠加 ``[cfg | emu]`` 前缀）。
        message: 通知正文。
        ok: 是否成功送达。
        reason: 未送达或跳过的原因。
        **extra: 额外字段（分辨率、截图路径、优先级等）。
    """
    global _context_missing_warned

    try:
        cfg, emu, ctx_missing = _resolve_log_context()
    except Exception:
        cfg, emu, ctx_missing = "unknown", "unknown", True

    if ctx_missing and not _context_missing_warned:
        _context_missing_warned = True
        logger.warning(
            "⚠️ 通知上下文缺失（config/emulator 均为 unknown）——"
            "通常意味着这条通知不是从正常的模拟器会话里发出的。"
            f"调用点: {_caller_hint()}"
        )

    record: Dict[str, Any] = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "event": event,
        "provider": provider,
        "ok": ok,
        "title": title,
        "message": message,
        "config": cfg,
        "emulator": emu,
        "context_missing": ctx_missing,
        "caller": _caller_hint(),
        "pid": os.getpid(),
        "reason": reason,
    }
    record.update(extra)

    # 1) 机器可读的 JSONL
    try:
        jsonl_path = _project_log_path(AUDIT_DIR_NAME, f"{datetime.now():%Y-%m-%d}.jsonl")
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - 盘满/权限等
        logger.warning(f"⚠️ 写通知审计 JSONL 失败: {exc}")

    # 2) 人读的一行摘要
    try:
        flag = "✅" if ok else ("🚫" if event == "blocked_test" else "❌")
        detail = f" 原因={reason}" if reason else ""
        line = (
            f"{record['ts']} {flag} [{event}] {provider} "
            f"[{cfg} | {emu}] {title} | "
            f"{message.replace(chr(10), ' / ')} (by {record['caller']}){detail}\n"
        )
        text_path = _project_log_path(AUDIT_TEXT_NAME)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        with open(text_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception as exc:  # pragma: no cover
        logger.warning(f"⚠️ 写通知审计文本日志失败: {exc}")

    # 3) 同时进主日志流，方便和业务日志对照
    if ok:
        logger.info(f"📝 通知已记录: [{event}] {title} -> {provider}")
    else:
        logger.warning(f"📝 通知未送达已记录: [{event}] {title} -> {provider} ({reason})")


def _get_notification_config() -> Optional[Dict[str, Any]]:
    """获取通知服务配置"""
    _container = get_container()
    sc = _container.system_config
    if sc is None:
        try:
            sc = load_system_config()
            _container.system_config = sc
        except Exception as exc:
            logger.warning(f"⚠️ 加载系统配置失败: {exc}")
            return None
    return sc


def _get_pushover_config() -> Optional[Dict[str, str]]:
    """获取 Pushover 配置（从 .env 读取）"""
    import os

    app_key = os.environ.get("PUSHOVER_APP_KEY")
    user_key = os.environ.get("PUSHOVER_USER_KEY")

    if not app_key or not user_key:
        logger.debug("🔕 Pushover 配置未完成，跳过")
        return None

    return {"app_key": app_key, "user_key": user_key}


def _enrich_message(title: str, message: str) -> tuple[str, str]:
    """丰富消息标题和内容，添加配置和模拟器信息。

    上下文缺失时会在正文里显式标注 —— 否则 ``unknown`` 看起来像某个
    真实配置的名字，收件人无从判断这其实意味着「没设置运行上下文」。

    Args:
        title: 原始标题。
        message: 原始正文。

    Returns:
        tuple[str, str]: ``(带前缀的标题, 追加了上下文的正文)``。
    """
    cfg, emu, ctx_missing = _resolve_log_context()
    marker = "（未设置运行上下文）" if ctx_missing else ""

    enriched_title = f"[{cfg} | {emu}] {title}"
    enriched_message = f"{message}\n配置: {cfg}{marker}\n模拟器: {emu}{marker}"

    return enriched_title, enriched_message


def send_bark_notification(title: str, message: str, level: str = "active", **kwargs) -> bool:
    """发送 Bark 通知

    Args:
        title: 通知标题
        message: 通知内容
        level: 通知级别 (active, timeSensitive, passive)
        **kwargs: 其他 Bark 参数

    Returns:
        是否发送成功
    """
    sc = _get_notification_config()
    if sc is None:
        _audit_notification(
            "skipped", "bark", title, message, False, "系统配置加载失败，无法判断 Bark 是否可用"
        )
        return False

    if not sc.is_bark_enabled():
        logger.debug("🔕 Bark 通知未启用，跳过发送")
        _audit_notification("skipped", "bark", title, message, False, "Bark 未启用")
        return False

    bark_config = sc.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.warning("⚠️ Bark 服务器地址未配置")
        _audit_notification("failed", "bark", title, message, False, "Bark 服务器地址未配置")
        return False

    try:
        enriched_title, enriched_message = _enrich_message(title, message)

        encoded_title = urllib.parse.quote(enriched_title, safe="")
        encoded_message = urllib.parse.quote(enriched_message, safe="")

        if "?" in server or server.endswith("/"):
            url = f"{server.rstrip('/')}/{encoded_title}/{encoded_message}"
        else:
            url = f"{server}/{encoded_title}/{encoded_message}"

        params = {}
        if bark_config.get("group"):
            params["group"] = bark_config["group"]
        if level:
            params["level"] = level
        # 合并额外参数
        params.update(kwargs)

        logger.info(f"📱 发送 Bark 通知: {enriched_title}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            logger.info("✅ Bark 通知发送成功")
            _audit_notification("sent", "bark", title, message, True, None, level=level)
            return True
        else:
            logger.warning(f"⚠️ Bark 通知发送失败，状态码: {response.status_code}")
            _audit_notification(
                "failed",
                "bark",
                title,
                message,
                False,
                f"HTTP {response.status_code}",
                level=level,
            )
            return False

    except requests.exceptions.Timeout:
        logger.warning("⚠️ Bark 通知发送超时")
        _audit_notification("failed", "bark", title, message, False, "请求超时", level=level)
        return False
    except Exception as e:
        logger.error(f"❌ 发送 Bark 通知失败: {e}")
        _audit_notification(
            "failed", "bark", title, message, False, f"{type(e).__name__}: {e}", level=level
        )
        return False


def send_pushover_notification(
    title: str,
    message: str,
    priority: int = 0,
    html: bool = False,
    **kwargs,
) -> bool:
    """发送 Pushover 通知

    Args:
        title: 通知标题
        message: 通知内容
        priority: 优先级 (-1, 0, 1, 2)
        html: 是否使用 HTML 格式（支持更丰富的文本格式）
        **kwargs: 其他 Pushover 参数 (sound, url, etc.)

    Returns:
        是否发送成功
    """
    # 截图是否真的存在，直接决定推送里会不会出现「截图失败」。
    # 在最早的出口之前算好，这样连「被拦截」的记录也带得上。
    image_path = kwargs.get("image")
    if image_path:
        image_ok = os.path.isfile(str(image_path)) and os.path.getsize(str(image_path)) > 0
    else:
        image_ok = None

    # 兜底防线：pytest 运行期绝不允许把通知推到大王手机上。
    # 2026-09-21 有测试漏打桩，把一条「券已够（40/40）但兑换未生效」的假告警
    # 真的推了出去，害得大王去查一个根本不存在的兑换故障。
    # 正常业务代码不会带 PYTEST_CURRENT_TEST，所以这条对线上零影响。
    if os.environ.get("PYTEST_CURRENT_TEST"):
        logger.warning(f"🧪 pytest 运行期，跳过真实 Pushover 通知: {title}")
        _audit_notification(
            "blocked_test",
            "pushover",
            title,
            message,
            False,
            "pytest 运行期，已拦截（业务代码不会带 PYTEST_CURRENT_TEST）",
            priority=priority,
            html=html,
            image=image_path,
            image_ok=image_ok,
        )
        return False

    config = _get_pushover_config()
    if config is None:
        logger.debug("🔕 Pushover 配置未完成，跳过发送")
        _audit_notification(
            "skipped", "pushover", title, message, False, "PUSHOVER_APP_KEY/USER_KEY 未配置"
        )
        return False

    try:
        from pushover_complete import PushoverAPI

        enriched_title, enriched_message = _enrich_message(title, message)

        api = PushoverAPI(config["app_key"])

        # 构建参数
        params = {
            "user": config["user_key"],
            "message": enriched_message,
            "title": enriched_title,
            "priority": priority,
        }

        if html:
            params["html"] = 1  # Pushover 使用 1 表示启用 HTML

        # 合并额外参数
        params.update(kwargs)

        logger.info(f"📱 发送 Pushover 通知: {enriched_title}")
        response = api.send_message(**params)

        # 新版 API 返回 dict，检查 status 字段
        if response.get("status") == 1:
            logger.info("✅ Pushover 通知发送成功")
            _audit_notification(
                "sent",
                "pushover",
                title,
                message,
                True,
                None,
                priority=priority,
                html=html,
                image=image_path,
                image_ok=image_ok,
            )
            return True
        else:
            logger.warning(f"⚠️ Pushover 通知发送失败，响应: {response}")
            _audit_notification(
                "failed",
                "pushover",
                title,
                message,
                False,
                f"接口返回 status!=1: {response}",
                priority=priority,
                html=html,
                image=image_path,
                image_ok=image_ok,
            )
            return False

    except Exception as e:
        logger.error(f"❌ 发送 Pushover 通知失败: {e}")
        _audit_notification(
            "failed",
            "pushover",
            title,
            message,
            False,
            f"{type(e).__name__}: {e}",
            priority=priority,
            html=html,
            image=image_path,
            image_ok=image_ok,
        )
        return False


def send_pushover_html_notification(title: str, message: str, **kwargs) -> bool:
    """发送 Pushover HTML 格式通知

    支持 HTML 格式的富文本通知，可以显示颜色和格式。

    Args:
        title: 通知标题
        message: HTML 格式的通知内容
        **kwargs: 其他 Pushover 参数

    Returns:
        是否发送成功
    """
    return send_pushover_notification(title, message, priority=0, html=True, **kwargs)


def send_notification(
    title: str,
    message: str,
    provider: str = "auto",
    level: str = "active",
    priority: int = 0,
    html: bool = False,
    **kwargs,
) -> bool:
    """统一的发送通知接口

    根据配置自动选择通知服务，支持通过 provider 参数指定。

    Args:
        title: 通知标题
        message: 通知内容
        provider: 通知服务提供商 ("bark", "pushover", "auto")
        level: Bark 通知级别 (active, timeSensitive, passive)
        priority: Pushover 优先级 (-1, 0, 1, 2)
        html: 是否使用 HTML 格式（Pushover）
        **kwargs: 其他服务特定参数

    Returns:
        是否发送成功
    """
    if provider == "bark":
        return send_bark_notification(title, message, level=level, **kwargs)
    elif provider == "pushover":
        return send_pushover_notification(title, message, priority=priority, html=html, **kwargs)
    elif provider == "auto":
        # 自动选择：根据配置尝试可用的服务
        sc = _get_notification_config()
        pushover_config = _get_pushover_config()

        # 优先使用 Pushover（如果配置了），否则使用 Bark
        if pushover_config is not None and sc is not None and sc.is_bark_enabled():
            # 两者都配置了，默认使用 Pushover
            return send_pushover_notification(
                title, message, priority=priority, html=html, **kwargs
            )
        elif pushover_config is not None:
            # 只有 Pushover
            return send_pushover_notification(
                title, message, priority=priority, html=html, **kwargs
            )
        elif sc is not None and sc.is_bark_enabled():
            # 只有 Bark
            return send_bark_notification(title, message, level=level, **kwargs)
        else:
            logger.warning("⚠️ 没有配置任何通知服务")
            # 委托给具体 provider 的分支已由它自己记账，这里只记「谁都没接」的情况
            _audit_notification(
                "skipped",
                "auto",
                title,
                message,
                False,
                "没有任何可用的通知服务（Pushover 未配置且 Bark 未启用）",
            )
            return False
    else:
        logger.warning(f"⚠️ 未知的通知服务提供商: {provider}")
        _audit_notification(
            "failed", provider, title, message, False, f"未知的通知服务提供商: {provider}"
        )
        return False


# 向后兼容：保持原有的 send_bark_notification 导出
__all__ = [
    "send_bark_notification",
    "send_pushover_notification",
    "send_pushover_html_notification",
    "send_notification",
]
