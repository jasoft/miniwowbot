"""
auto_dungeon 通知模块
"""

import logging
import urllib.parse
import requests

from auto_dungeon_container import get_container
from logger_config import GlobalLogContext
from system_config_loader import load_system_config

logger = logging.getLogger(__name__)

def send_bark_notification(title: str, message: str, level: str = "active") -> bool:
    """发送 Bark 通知"""
    _container = get_container()
    sc = _container.system_config
    if sc is None:
        try:
            sc = load_system_config()
            _container.system_config = sc
        except Exception as exc:
            logger.warning(f"⚠️ 加载系统配置失败，无法发送 Bark 通知: {exc}")
            return False
    if not sc or not sc.is_bark_enabled():
        logger.debug("🔕 Bark 通知未启用，跳过发送")
        return False

    bark_config = sc.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.warning("⚠️ Bark 服务器地址未配置")
        return False

    try:
        cfg = GlobalLogContext.context.get("config") or (_container.config_name or "unknown")
        emu = GlobalLogContext.context.get("emulator") or (_container.target_emulator or "unknown")
        enriched_title = f"[{cfg} | {emu}] {title}"
        enriched_message = f"{message}\n配置: {cfg}\n模拟器: {emu}"

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

        logger.info(f"📱 发送 Bark 通知: {enriched_title}")
        logger.info(f"📄 Bark 内容: {enriched_message}")
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
