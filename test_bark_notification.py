#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 Bark 通知功能
"""

import sys
import os
import logging
import coloredlogs
import requests
import urllib.parse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system_config_loader import load_system_config  # noqa: E402

# 配置日志
logger = logging.getLogger(__name__)
coloredlogs.install(
    level="INFO",
    logger=logger,
    fmt="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def send_bark_notification(system_config, title, message, level="active"):
    """
    发送 Bark 通知（独立测试版本）

    :param system_config: 系统配置加载器实例
    :param title: 通知标题
    :param message: 通知内容
    :param level: 通知级别，可选值: active(默认), timeSensitive, passive
    :return: 是否发送成功
    """
    if not system_config.is_bark_enabled():
        logger.warning("🔕 Bark 通知未启用，请在配置文件中启用")
        return False

    bark_config = system_config.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.error("❌ Bark 服务器地址未配置")
        return False

    try:
        # 构造 Bark URL
        encoded_title = urllib.parse.quote(title)
        encoded_message = urllib.parse.quote(message)

        # 如果 server 已经包含完整路径，直接使用
        if "?" in server or server.endswith("/"):
            url = f"{server.rstrip('/')}/{encoded_title}/{encoded_message}"
        else:
            url = f"{server}/{encoded_title}/{encoded_message}"

        # 添加可选参数
        params = {}
        if bark_config.get("group"):
            params["group"] = bark_config["group"]
        if level:
            params["level"] = level

        # 发送请求
        logger.info(f"📱 发送 Bark 通知: {title}")
        logger.info(f"🔗 URL: {url}")
        logger.info(f"📋 参数: {params}")

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            logger.info("✅ Bark 通知发送成功")
            logger.info(f"📄 响应: {response.text}")
            return True
        else:
            logger.warning(f"⚠️ Bark 通知发送失败，状态码: {response.status_code}")
            logger.warning(f"📄 响应: {response.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error("❌ Bark 通知发送超时")
        return False
    except Exception as e:
        logger.error(f"❌ 发送 Bark 通知失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🧪 Bark 通知功能测试")
    print("=" * 60 + "\n")

    # 加载系统配置
    config_file = "system_config.json"

    if not os.path.exists(config_file):
        logger.error(f"❌ 系统配置文件不存在: {config_file}")
        logger.info("💡 请确保 system_config.json 文件存在")
        return 1

    try:
        system_config = load_system_config(config_file)

        # 显示配置信息
        bark_config = system_config.get_bark_config()
        logger.info("📝 Bark 配置:")
        logger.info(f"  - 启用: {system_config.is_bark_enabled()}")
        logger.info(f"  - 服务器: {bark_config.get('server', '未配置')}")
        logger.info(f"  - 分组: {bark_config.get('group', '未配置')}")

        if not system_config.is_bark_enabled():
            logger.warning("\n⚠️ Bark 通知未启用")
            logger.info("💡 请在配置文件中设置 bark.enabled 为 true")
            logger.info("💡 并配置正确的 bark.server 地址")
            return 1

        # 发送测试通知
        print("\n" + "-" * 60)
        logger.info("📱 发送测试通知...")
        print("-" * 60 + "\n")

        success = send_bark_notification(
            system_config,
            "副本助手 - 测试通知",
            "这是一条测试通知，如果你收到了这条消息，说明 Bark 通知配置成功！",
            level="active",
        )

        print("\n" + "=" * 60)
        if success:
            logger.info("✅ 测试成功！请检查你的设备是否收到通知")
        else:
            logger.error("❌ 测试失败，请检查配置和网络连接")
        print("=" * 60 + "\n")

        return 0 if success else 1

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
