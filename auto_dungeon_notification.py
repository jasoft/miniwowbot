"""
auto_dungeon 通知模块

支持多种通知服务（Bark、Pushover），通过 .env 配置选择使用哪种服务。
提供统一的发送接口，自动处理不同服务的参数差异。
"""

import logging
import os
import urllib.parse
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from auto_dungeon_container import get_container
from logger_config import GlobalLogContext
from system_config_loader import load_system_config

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

NOTIFY_ON_EXIT_ONLY_ENV = "MINIWOW_NOTIFY_ON_EXIT_ONLY"


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
    """丰富消息标题和内容，添加配置和模拟器信息"""
    _container = get_container()
    cfg = GlobalLogContext.context.get("config") or (_container.config_name or "unknown")
    emu = GlobalLogContext.context.get("emulator") or (_container.target_emulator or "unknown")

    enriched_title = f"[{cfg} | {emu}] {title}"
    enriched_message = f"{message}\n配置: {cfg}\n模拟器: {emu}"

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
        return False

    if not sc.is_bark_enabled():
        logger.debug("🔕 Bark 通知未启用，跳过发送")
        return False

    bark_config = sc.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.warning("⚠️ Bark 服务器地址未配置")
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
            return True
        else:
            logger.warning(f"⚠️ Bark 通知发送失败，状态码: {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.warning("⚠️ Bark 通知发送超时")
        return False
    except Exception as e:
        logger.error(f"❌ 发送 Bark 通知失败: {e}")
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
    from pushover_complete import PushoverAPI

    config = _get_pushover_config()
    if config is None:
        logger.debug("🔕 Pushover 配置未完成，跳过发送")
        return False

    try:
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
            return True
        else:
            logger.warning(
                f"⚠️ Pushover 通知发送失败，响应: {response}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ 发送 Pushover 通知失败: {e}")
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
    force: bool = False,
    **kwargs,
) -> bool:
    """统一的发送通知接口。

    根据配置自动选择通知服务，支持通过 provider 参数指定。
    当环境变量 ``MINIWOW_NOTIFY_ON_EXIT_ONLY=1`` 且 ``force`` 为 ``False`` 时，
    会跳过运行期通知，只保留程序退出时的最终汇总通知。

    Args:
        title: 通知标题。
        message: 通知内容。
        provider: 通知服务提供商（``"bark"``、``"pushover"``、``"auto"``）。
        level: Bark 通知级别（``active``、``timeSensitive``、``passive``）。
        priority: Pushover 优先级（``-1``、``0``、``1``、``2``）。
        html: 是否使用 HTML 格式（Pushover）。
        force: 是否忽略运行期静默策略并强制发送。
        **kwargs: 其他服务特定参数。

    Returns:
        是否发送成功。
    """
    notify_on_exit_only = os.environ.get(NOTIFY_ON_EXIT_ONLY_ENV, "").strip().lower()
    if notify_on_exit_only in {"1", "true", "yes", "on"} and not force:
        logger.info(f"🔕 已抑制运行期通知: {title}")
        return False

    if provider == "bark":
        return send_bark_notification(title, message, level=level, **kwargs)
    elif provider == "pushover":
        return send_pushover_notification(
            title, message, priority=priority, html=html, **kwargs
        )
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
            return False
    else:
        logger.warning(f"⚠️ 未知的通知服务提供商: {provider}")
        return False


# 向后兼容：保持原有的 send_bark_notification 导出
__all__ = [
    "send_bark_notification",
    "send_pushover_notification",
    "send_pushover_html_notification",
    "send_notification",
]
