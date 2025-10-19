# -*- encoding=utf8 -*-
__author__ = "Airtest"
import time
import sys
import os
import logging
import coloredlogs
import argparse
import random
import subprocess
import platform
import requests
import urllib.parse

from airtest.core.api import (
    wait,
    sleep,
    touch,
    exists,
    swipe,
    Template,
    stop_app,
    start_app,
)

# 设置 Airtest 日志级别
airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)

# 导入自定义的数据库模块和配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DungeonProgressDB  # noqa: E402
from config_loader import load_config  # noqa: E402
from system_config_loader import load_system_config  # noqa: E402
from coordinates import (  # noqa: E402
    DEPLOY_CONFIRM_BUTTON,
    ONE_KEY_DEPLOY,
    ONE_KEY_REWARD,
    SETTINGS_BUTTON,
    BACK_BUTTON,
    MAP_BUTTON,
    ACCOUNT_AVATAR,
    SKILL_POSITIONS,
    DAILY_REWARD_BOX_OFFSET_Y,
    DAILY_REWARD_CONFIRM,
    CLOSE_ZONE_MENU,
    ACCOUNT_DROPDOWN_ARROW,
    ACCOUNT_LIST_SWIPE_START,
    ACCOUNT_LIST_SWIPE_END,
    LOGIN_BUTTON,
    QUICK_AFK_COLLECT_BUTTON,
)

CLICK_INTERVAL = 1
STOP_FILE = ".stop_dungeon"  # 停止标记文件路径

# 配置彩色日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# 防止日志重复：移除已有的 handlers
logger.handlers.clear()
logger.propagate = False

coloredlogs.install(
    level="INFO",
    logger=logger,
    fmt="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level_styles={
        "debug": {"color": "cyan"},
        "info": {"color": "green"},
        "warning": {"color": "yellow"},
        "error": {"color": "red"},
        "critical": {"color": "red", "bold": True},
    },
    field_styles={
        "asctime": {"color": "blue"},
        "levelname": {"color": "white", "bold": True},
    },
)


# 全局变量，将在 main 函数中初始化
config_loader = None
system_config = None
zone_dungeons = None
ocr_helper = None


def check_bluestacks_running():
    """
    检查BlueStacks模拟器是否正在运行

    Returns:
        bool: 如果BlueStacks正在运行返回True，否则返回False
    """
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ["pgrep", "-f", "BlueStacks"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        elif system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq HD-Player.exe"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "HD-Player.exe" in result.stdout
        else:  # Linux
            result = subprocess.run(
                ["pgrep", "-f", "bluestacks"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
    except Exception as e:
        logger.warning(f"⚠️ 检查BlueStacks状态失败: {e}")
        return False


def start_bluestacks():
    """
    启动BlueStacks模拟器

    Returns:
        bool: 启动成功返回True，失败返回False
    """
    try:
        system = platform.system()
        logger.info("🚀 正在启动BlueStacks模拟器...")

        if system == "Darwin":  # macOS
            # macOS上通过open命令启动应用
            subprocess.Popen(
                ["open", "-a", "BlueStacks"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            # Windows上启动BlueStacks
            # 常见安装路径
            paths = [
                r"C:\Program Files\BlueStacks_nxt\HD-Player.exe",
                r"C:\Program Files (x86)\BlueStacks_nxt\HD-Player.exe",
                r"C:\Program Files\BlueStacks\HD-Player.exe",
                r"C:\Program Files (x86)\BlueStacks\HD-Player.exe",
            ]
            for path in paths:
                if os.path.exists(path):
                    subprocess.Popen(
                        [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    break
            else:
                logger.error("❌ 未找到BlueStacks安装路径")
                return False
        else:  # Linux
            # Linux上通过命令启动
            subprocess.Popen(
                ["bluestacks"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # 等待模拟器启动
        logger.info("⏳ 等待模拟器启动...")
        max_wait_time = 60  # 最多等待60秒
        wait_interval = 5
        elapsed = 0

        while elapsed < max_wait_time:
            time.sleep(wait_interval)
            elapsed += wait_interval
            if check_bluestacks_running():
                logger.info(f"✅ BlueStacks已启动 (耗时 {elapsed} 秒)")
                # 额外等待一段时间让模拟器完全就绪
                logger.info("⏳ 等待模拟器完全就绪...")
                time.sleep(10)
                return True
            logger.info(f"⏳ 继续等待... ({elapsed}/{max_wait_time}秒)")

        logger.error("❌ BlueStacks启动超时")
        return False

    except Exception as e:
        logger.error(f"❌ 启动BlueStacks失败: {e}")
        return False


def ensure_adb_connection():
    """
    确保ADB连接已建立
    无论模拟器是否刚启动，都执行一次adb devices来建立连接

    Returns:
        bool: 连接成功返回True，失败返回False
    """
    try:
        logger.info("🔌 执行 adb devices 建立连接...")
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            # 检查是否有设备连接
            lines = result.stdout.strip().split("\n")
            devices = [line for line in lines if "\tdevice" in line]

            if devices:
                logger.info(f"✅ 发现 {len(devices)} 个设备:")
                for device in devices:
                    logger.info(f"  📱 {device}")
                return True
            else:
                logger.warning("⚠️ 未发现已连接的设备")
                # 即使没有设备，也返回True，让后续的connect_device处理
                return True
        else:
            logger.error(f"❌ adb devices 执行失败: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("❌ 未找到adb命令，请确保Android SDK已安装并配置环境变量")
        return False
    except Exception as e:
        logger.error(f"❌ 执行adb devices失败: {e}")
        return False


def check_and_start_emulator():
    """
    检查模拟器状态并在需要时启动
    无论是否启动，都会执行adb devices建立连接

    Returns:
        bool: 准备成功返回True，失败返回False
    """
    logger.info("\n" + "=" * 60)
    logger.info("🔍 检查BlueStacks模拟器状态")
    logger.info("=" * 60)

    # 检查模拟器是否运行
    if check_bluestacks_running():
        logger.info("✅ BlueStacks模拟器已在运行")
    else:
        logger.info("⚠️ BlueStacks模拟器未运行")
        if not start_bluestacks():
            logger.error("❌ 无法启动BlueStacks模拟器")
            return False

    # 无论模拟器是否刚启动，都执行adb devices
    if not ensure_adb_connection():
        logger.error("❌ 建立ADB连接失败")
        return False

    logger.info("=" * 60 + "\n")
    return True


def check_stop_signal():
    """
    检查是否存在停止信号文件

    Returns:
        bool: 如果存在停止文件返回 True，否则返回 False
    """
    if os.path.exists(STOP_FILE):
        logger.warning(f"\n⛔ 检测到停止信号文件: {STOP_FILE}")
        logger.warning("⛔ 正在优雅地停止执行...")
        # 删除停止文件
        try:
            os.remove(STOP_FILE)
            logger.info("✅ 已删除停止信号文件")
        except Exception as e:
            logger.error(f"❌ 删除停止文件失败: {e}")
        return True
    return False


SETTINGS_TEMPLATE = Template(
    r"images/settings_button.png",
    resolution=(720, 1280),
    record_pos=(0.426, -0.738),
)

GIFTS_TEMPLATE = Template(
    r"images/gifts_button.png", resolution=(720, 1280), record_pos=(0.428, -0.424)
)


def find_text(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
    raise_exception=True,
):
    """
    使用 OCRHelper 查找文本
    支持 OCR 纠正：如果找不到原文本，会尝试查找 OCR 可能识别错误的文本

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :param raise_exception: 超时后是否抛出异常，默认True
    :return: OCR识别结果字典，包含 center, text, confidence 等信息
    :raises TimeoutError: 如果超时且 raise_exception=True
    """
    # 检查 ocr_helper 是否已初始化
    if ocr_helper is None:
        error_msg = "❌ OCR助手未初始化，无法查找文本"
        logger.error(error_msg)
        if raise_exception:
            raise RuntimeError(error_msg)
        return None

    region_desc = ""
    if regions:
        region_desc = f" [区域{regions}]"

    if occurrence > 1:
        logger.info(f"🔍 查找文本: {text} (第{occurrence}个){region_desc}")
    else:
        logger.info(f"🔍 查找文本: {text}{region_desc}")
    start_time = time.time()

    # 准备要尝试的文本列表：[原文本, OCR可能识别的错误文本]
    texts_to_try = [text]

    # 检查是否有对应的 OCR 纠正映射（反向查找）
    if config_loader:
        for ocr_text, correct_text in config_loader.get_ocr_correction_map().items():
            if correct_text == text:
                texts_to_try.append(ocr_text)
                logger.debug(f"💡 将同时尝试查找 OCR 可能识别的文本: {ocr_text}")
                break

    while time.time() - start_time < timeout:
        # 尝试所有可能的文本
        for try_text in texts_to_try:
            # 使用 OCRHelper 查找文本
            result = ocr_helper.capture_and_find_text(
                try_text,
                confidence_threshold=similarity_threshold,
                occurrence=occurrence,
                use_cache=use_cache,
                regions=regions,
            )

            if result and result.get("found"):
                if try_text != text:
                    logger.info(
                        f"✅ 通过 OCR 纠正找到文本: {text} (OCR识别为: {try_text}){region_desc}"
                    )
                else:
                    if occurrence > 1:
                        logger.info(
                            f"✅ 找到文本: {text} (第{occurrence}个){region_desc}"
                        )
                    else:
                        logger.info(f"✅ 找到文本: {text}{region_desc}")
                return result

        # 短暂休眠避免CPU占用过高
        sleep(0.1)

    # 超时处理
    error_msg = f"❌ 超时未找到文本: {text}"
    if occurrence > 1:
        error_msg = f"❌ 超时未找到文本: {text} (第{occurrence}个)"

    logger.warning(error_msg)

    if raise_exception:
        raise TimeoutError(error_msg)

    return None


def find_text_and_click(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
):
    """
    使用 OCRHelper 查找文本并点击
    支持 OCR 纠正：如果找不到原文本，会尝试查找 OCR 可能识别错误的文本

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定点击第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :return: 成功返回 find_text 的结果字典
    :raises TimeoutError: 如果超时未找到文本
    :raises Exception: 其他错误
    """
    try:
        # 调用 find_text 查找文本（抛出异常）
        result = find_text(
            text=text,
            timeout=timeout,
            similarity_threshold=similarity_threshold,
            occurrence=occurrence,
            use_cache=use_cache,
            regions=regions,
            raise_exception=True,
        )

        # 点击找到的位置
        assert result
        center = result["center"]
        touch(center)
        sleep(CLICK_INTERVAL)  # 每个点击后面停顿一下等待界面刷新

        region_desc = f" [区域{regions}]" if regions else ""
        logger.info(f"✅ 成功点击: {text}{region_desc} at {center}")
        return result

    except Exception as e:
        logger.error(f"❌ 查找并点击文本失败: {text} - {e}")
        raise


def find_text_and_click_safe(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
    default_return=False,
):
    """
    安全版本的 find_text_and_click，不会抛出异常

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定点击第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :param default_return: 找不到时返回的默认值（False或None）
    :return: 成功返回 find_text 的结果字典，失败返回 default_return
    """
    try:
        return find_text_and_click(
            text=text,
            timeout=timeout,
            similarity_threshold=similarity_threshold,
            occurrence=occurrence,
            use_cache=use_cache,
            regions=regions,
        )
    except Exception as e:
        region_desc = f" [区域{regions}]" if regions else ""
        logger.debug(f"⚠️ 安全查找并点击失败: {text}{region_desc} - {e}")
        return default_return


def click_back():
    """点击返回按钮（左上角）"""
    try:
        touch(BACK_BUTTON)
        sleep(CLICK_INTERVAL)  # 等待界面刷新
        logger.info("🔙 点击返回按钮")
        return True
    except Exception as e:
        logger.error(f"❌ 返回失败: {e}")
        return False


def click_free_button():
    """点击免费按钮"""
    free_words = ["免费"]

    for word in free_words:
        if find_text_and_click_safe(word, timeout=3, use_cache=False):
            logger.info(f"💰 点击了免费按钮: {word}")

            return True

    logger.warning("⚠️ 未找到免费按钮")
    return False


def send_bark_notification(title, message, level="active"):
    """
    发送 Bark 通知

    :param title: 通知标题
    :param message: 通知内容
    :param level: 通知级别，可选值: active(默认), timeSensitive, passive
    :return: 是否发送成功
    """
    if not system_config or not system_config.is_bark_enabled():
        logger.debug("🔕 Bark 通知未启用，跳过发送")
        return False

    bark_config = system_config.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.warning("⚠️ Bark 服务器地址未配置")
        return False

    try:
        # 构造 Bark URL
        # 格式: https://api.day.app/{device_key}/{title}/{body}?group={group}&level={level}
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


def is_main_world():
    """检查是否在主世界，并输出执行时间"""
    result = bool(exists(GIFTS_TEMPLATE))
    return result


def open_map():
    back_to_main()

    touch(MAP_BUTTON)
    logger.info("🗺️ 打开地图")
    sleep(CLICK_INTERVAL)


def auto_combat():
    """自动战斗"""
    logger.info("自动战斗")
    find_text_and_click_safe("战斗", regions=[8])

    while not is_main_world():
        positions = SKILL_POSITIONS.copy()
        random.shuffle(positions)
        for pos in positions:
            touch(pos)
            sleep(0.2)


def select_character(char_class):
    """
    选择角色

    Args:
        char_class: 角色职业名称（如：战士、法师、刺客等）
    """
    logger.info(f"⚔️ 选择角色: {char_class}")

    # 检查是否存在错误对话框
    error_templates = [
        Template(r"images/error_duplogin.png", resolution=(720, 1280)),
        Template(r"images/error_network.png", resolution=(720, 1280)),
    ]

    ok_button_template = Template(r"images/ok_button.png", resolution=(720, 1280))

    for error_template in error_templates:
        if exists(error_template):
            logger.warning("⚠️ 检测到错误对话框")
            if exists(ok_button_template):
                touch(ok_button_template)
                logger.info("✅ 点击OK按钮关闭错误对话框")
                sleep(1)
            break

    if not exists(
        Template(r"images/enter_game_button.png", resolution=(720, 1280))
    ):  # 如果不在选择角色界面，返回选择界面
        back_to_main()
        touch(SETTINGS_BUTTON)
        sleep(1)

        # 返回角色选择界面
        find_text_and_click_safe("返回角色选择界面")
        wait(Template(r"images/enter_game_button.png", resolution=(720, 1280)), 10)
    else:
        logger.info("已在角色选择界面")

    # 查找职业文字位置
    logger.info(f"🔍 查找职业: {char_class}")
    result = find_text(char_class, similarity_threshold=0.6)

    if result and result.get("found"):
        # 点击找到的位置
        pos = result["center"]
        # 点击文字上方 60 像素的位置
        click_x = pos[0]
        click_y = pos[1] - 60
        logger.info(f"👆 点击角色位置: ({click_x}, {click_y})")
        touch((click_x, click_y))
        sleep(1)

        # 等待回到主界面
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        logger.error(f"❌ 未找到职业: {char_class}")
        raise Exception(f"无法找到职业: {char_class}")

    find_text_and_click("进入游戏")
    wait_for_main()


def wait_for_main():
    """
    等待回到主界面
    如果 5 分钟（300秒）还没执行结束，则中断执行并发送通知
    """
    logger.info("⏳ 等待战斗结束...")
    timeout = 300  # 5 分钟超时
    start_time = time.time()

    try:
        # 使用较短的循环检查，以便能及时中断
        check_interval = 5  # 每5秒检查一次
        while time.time() - start_time < timeout:
            if exists(GIFTS_TEMPLATE):
                elapsed = time.time() - start_time
                logger.info(f"✅ 战斗结束，用时 {elapsed:.1f} 秒")
                return True

            # 检查是否有停止信号
            if check_stop_signal():
                logger.warning("⛔ 收到停止信号，中断等待")
                send_bark_notification(
                    "副本助手", "收到停止信号，已中断执行", level="timeSensitive"
                )
                raise KeyboardInterrupt("收到停止信号")

            time.sleep(check_interval)

        # 超时处理
        elapsed = time.time() - start_time
        error_msg = f"战斗超时（{elapsed:.1f}秒 > {timeout}秒），可能卡住了"
        logger.error(f"❌ {error_msg}")

        # 发送 Bark 通知
        send_bark_notification("副本助手 - 超时警告", error_msg, level="timeSensitive")

        # 抛出超时异常
        raise TimeoutError(error_msg)

    except TimeoutError:
        raise
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error(f"❌ 等待主界面时出错: {e}")
        send_bark_notification(
            "副本助手 - 错误", f"等待主界面时出错: {str(e)}", level="timeSensitive"
        )
        raise


def switch_to_zone(zone_name):
    """切换到指定区域"""
    logger.info(f"\n{'=' * 50}")
    logger.info(f"🌍 切换区域: {zone_name}")
    logger.info(f"{'=' * 50}")

    # 点击切换区域按钮
    switch_words = ["切换区域"]

    for word in switch_words:
        if find_text_and_click_safe(word, timeout=10):
            break

    # 点击区域名称
    if find_text_and_click_safe(zone_name, timeout=10, occurrence=2):
        logger.info(f"✅ 成功切换到: {zone_name}")
        touch(CLOSE_ZONE_MENU)  # 关闭切换菜单
        return True

    logger.error(f"❌ 切换失败: {zone_name}")
    return False


def sell_trashes():
    logger.info("💰 卖垃圾")
    click_back()
    if find_text_and_click_safe("装备", regions=[7, 8, 9]):
        if find_text_and_click_safe("整理售卖", regions=[7, 8, 9]):
            if find_text_and_click_safe("出售"):
                logger.info("✅ 成功完成装备售卖流程")
            else:
                raise Exception("❌ 点击'出售'按钮失败")
        else:
            raise Exception("❌ 点击'整理售卖'按钮失败")
    else:
        raise Exception("❌ 点击'装备'按钮失败")
    click_back()
    click_back()


def switch_account(account_name):
    logger.info(f"切换账号: {account_name}")
    stop_app("com.ms.ysjyzr")
    sleep(2)
    start_app("com.ms.ysjyzr")
    try:
        find_text("进入游戏", timeout=20, regions=[5])
        touch(ACCOUNT_AVATAR)
        sleep(2)
        find_text_and_click_safe("切换账号", regions=[2, 3])
    except Exception:
        logger.warning("⚠️ 未找到切换账号按钮，可能处于登录界面")
        pass
    find_text("最近登录", timeout=20, regions=[5])
    touch(ACCOUNT_DROPDOWN_ARROW)  # 下拉箭头

    success = False
    for _ in range(10):
        if find_text_and_click_safe(
            account_name, occurrence=2, use_cache=False, regions=[4, 5, 6, 7, 8, 9]
        ):
            success = True
            break
        swipe(ACCOUNT_LIST_SWIPE_START, ACCOUNT_LIST_SWIPE_END)

    if not success:
        raise Exception(
            f"Failed to find and click account '{account_name}' after 10 tries"
        )
    touch(LOGIN_BUTTON)  # 登录按钮


def back_to_main():
    logger.info("🔙 返回主界面")
    while not is_main_world():
        for _ in range(3):
            touch(BACK_BUTTON)


def switch_to(section_name):
    """切换到指定区域"""
    logger.info(f"🌍 切换到: {section_name}")
    return find_text_and_click(section_name, regions=[7, 8, 9])


class DailyCollectManager:
    """
    每日收集管理器
    负责处理所有每日收集相关的操作，包括：
    - 每日挂机奖励领取
    - 快速挂机领取
    - 随从派遣
    - 每日免费地下城领取
    """

    def __init__(self, config_loader=None):
        """
        初始化每日收集管理器

        Args:
            config_loader: 配置加载器实例
        """
        self.config_loader = config_loader
        self.logger = logger

    def collect_daily_rewards(self):
        """
        执行所有每日收集操作
        """
        self.logger.info("=" * 60)
        self.logger.info("🎁 开始执行每日收集操作")
        self.logger.info("=" * 60)

        try:
            # 1. 领取每日挂机奖励
            self._collect_idle_rewards()

            # 2. 购买商店每日
            self._buy_market_items()

            # 3. 执行随从派遣
            self._handle_retinue_deployment()

            # 4. 领取每日免费地下城
            self._collect_free_dungeons()

            # 5. 开启宝箱（如果配置了宝箱名称）
            if self.config_loader and self.config_loader.get_chest_name():
                self._open_chests(self.config_loader.get_chest_name())

            # 6. 打三次世界 boss
            for _ in range(3):
                self._kill_world_boss()

            self.logger.info("=" * 60)
            self.logger.info("✅ 每日收集操作全部完成")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"❌ 每日收集操作失败: {e}")
            raise

    def _collect_idle_rewards(self):
        """
        领取每日挂机奖励
        """
        self.logger.info("📦 开始领取每日挂机奖励")
        back_to_main()

        try:
            res = switch_to("战斗")
            assert res
            # 点击奖励箱子
            touch((res["center"][0], res["center"][1] + DAILY_REWARD_BOX_OFFSET_Y))
            sleep(CLICK_INTERVAL)
            touch(DAILY_REWARD_CONFIRM)
            sleep(CLICK_INTERVAL)
            find_text_and_click("确定", regions=[5])
            self.logger.info("✅ 每日挂机奖励领取成功")
            # 2. 执行快速挂机领取（如果启用）
            if self.config_loader and self.config_loader.is_quick_afk_enabled():
                self._collect_quick_afk()

            back_to_main()
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到战斗按钮或点击失败: {e}")
            raise

    def _collect_quick_afk(self):
        """
        执行快速挂机领取
        """
        self.logger.info("⚡ 开始快速挂机领取")
        if find_text_and_click_safe("快速挂机", regions=[4, 5, 6, 7, 8, 9]):
            # 多次点击领取按钮，确保领取所有奖励
            for i in range(10):
                touch(QUICK_AFK_COLLECT_BUTTON)
                sleep(1)
            self.logger.info("✅ 快速挂机领取完成")
        else:
            self.logger.warning("⚠️ 未找到快速挂机按钮")

    def _handle_retinue_deployment(self):
        """
        处理随从派遣操作
        """
        self.logger.info("👥 开始处理随从派遣")
        back_to_main()

        if find_text_and_click_safe("随从", regions=[7]):
            # 领取派遣奖励
            find_text_and_click("派遣", regions=[8])
            touch(ONE_KEY_REWARD)
            back_to_main()

            # 重新派遣
            find_text_and_click("派遣", regions=[8])
            touch(ONE_KEY_DEPLOY)
            sleep(1)
            touch(DEPLOY_CONFIRM_BUTTON)
            back_to_main()

            self.logger.info("✅ 随从派遣处理完成")
        else:
            self.logger.warning("⚠️ 未找到随从按钮，跳过派遣操作")

    def _collect_free_dungeons(self):
        """
        领取每日免费地下城（试炼塔）
        """
        self.logger.info("🏰 开始领取每日免费地下城")
        back_to_main()
        open_map()

        if find_text_and_click_safe("试炼塔", regions=[9]):
            self.logger.info("✅ 进入试炼塔")

            # 领取消量奖励
            self._sweep_tower_floor("刻印", regions=[7, 8])
            self._sweep_tower_floor("宝石", regions=[8, 8])
            self._sweep_tower_floor("雕文", regions=[9, 8])

            self.logger.info("✅ 每日免费地下城领取完成")
        else:
            self.logger.warning("⚠️ 未找到试炼塔，跳过免费地下城领取")

        back_to_main()

    def _sweep_tower_floor(self, floor_name, regions):
        """
        扫荡试炼塔的特定楼层

        Args:
            floor_name: 楼层名称（刻印、宝石、雕文）
            regions: 搜索区域列表 [楼层区域, 按钮区域]
        """
        if find_text_and_click_safe(floor_name, regions=[regions[0]]):
            try:
                find_text_and_click("扫荡一次", regions=[regions[1]])
                find_text_and_click("确定", regions=[5])
                self.logger.info(f"✅ 完成{floor_name}扫荡")
            except Exception as e:
                self.logger.warning(f"⚠️ 扫荡{floor_name}失败: {e}")
        else:
            self.logger.warning(f"⚠️ 未找到{floor_name}楼层")

    def _kill_world_boss(self):
        """
        杀死世界boss
        """
        self.logger.info("💀 开始杀死世界boss")
        back_to_main()
        open_map()
        try:
            find_text_and_click("切换区域", regions=[8])
            find_text_and_click("东部大陆", regions=[5])
            touch((126, 922))
            sleep(1.5)
            find_text_and_click("协助模式", regions=[8])
            find_text_and_click("创建队伍", regions=[4, 5])
            find_text_and_click("开始", regions=[5])
            find_text_and_click("离开", regions=[5], timeout=20)
            self.logger.info("✅ 杀死世界boss成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到世界boss: {e}")
            back_to_main()

    def _buy_market_items(self):
        """
        购买市场商品
        """
        self.logger.info("🛒 开始购买市场商品")
        back_to_main()
        try:
            find_text_and_click("主城", regions=[9])
            find_text_and_click("商店", regions=[4])
            touch((570, 258))
            sleep(1)
            find_text_and_click("购买", regions=[8])
            back_to_main()
            self.logger.info("✅ 购买市场商品成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到商店: {e}")
            back_to_main()

    def _open_chests(self, chest_name):
        """
        开启宝箱
        """
        self.logger.info(f"🎁 开始开启{chest_name}")
        back_to_main()
        try:
            find_text_and_click("主城", regions=[9])
            find_text_and_click("宝库", regions=[9])
            find_text_and_click(chest_name, regions=[4, 5, 6, 7, 8])
            res = find_text("开启", regions=[8])
            if res:
                for _ in range(10):
                    touch(res["center"])
                    sleep(0.2)
            back_to_main()
            self.logger.info("✅ 打开宝箱成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到宝箱: {e}")
            back_to_main()

    # 保留原始函数名作为向后兼容
    def daily_collect(self):
        """
        向后兼容的函数名
        """
        self.collect_daily_rewards()


# 创建全局实例，保持向后兼容
daily_collect_manager = DailyCollectManager(config_loader)


def daily_collect():
    """
    领取每日挂机奖励
    保持向后兼容的函数包装器
    """
    global daily_collect_manager
    # 确保使用最新的配置
    if daily_collect_manager.config_loader != config_loader:
        daily_collect_manager = DailyCollectManager(config_loader)
    daily_collect_manager.collect_daily_rewards()


def process_dungeon(dungeon_name, zone_name, index, total, db):
    """处理单个副本, 返回是否成功完成

    注意：调用此函数前应该已经检查过是否已通关
    """
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

    # 点击副本名称
    if not find_text_and_click_safe(dungeon_name, timeout=5):
        logger.warning(f"⏭️ 跳过: {dungeon_name}")
        return False
    sleep(2)  # 等待界面刷新

    # 尝试点击免费按钮
    if click_free_button():
        # 进入副本战斗，退出后会回到主界面
        auto_combat()
        logger.info(f"✅ 完成: {dungeon_name}")

        # 记录通关状态
        db.mark_dungeon_completed(zone_name, dungeon_name)

        sleep(CLICK_INTERVAL)
        return True
    else:
        # 没有免费按钮，说明今天已经通关过了，记录状态
        logger.warning("⚠️ 无免费按钮，标记为已完成")
        db.mark_dungeon_completed(zone_name, dungeon_name)
        click_back()

    return False


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="副本自动遍历脚本")
    parser.add_argument(
        "--skip-emulator-check",
        action="store_true",
        help="跳过模拟器检查和启动（用于测试或特殊情况）",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="configs/default.json",
        help="配置文件路径 (默认: configs/default.json)",
    )
    parser.add_argument(
        "--load-account",
        type=str,
        help="加载指定账号后退出（账号名称，如：18502542158）",
    )
    return parser.parse_args()


def handle_load_account_mode(account_name):
    """处理账号加载模式"""
    global ocr_helper

    logger.info("\n" + "=" * 60)
    logger.info("🔄 账号加载模式")
    logger.info("=" * 60 + "\n")
    logger.info(f"📱 目标账号: {account_name}")

    # 初始化设备和OCR
    from airtest.core.api import connect_device, auto_setup
    from ocr_helper import OCRHelper

    connect_device("Android:///")
    auto_setup(__file__)
    ocr_helper = OCRHelper(output_dir="output")

    # 切换账号
    try:
        switch_account(account_name)
        logger.info(f"✅ 成功加载账号: {account_name}")
        logger.info("=" * 60 + "\n")
    except Exception as e:
        logger.error(f"❌ 加载账号失败: {e}")
        sys.exit(1)


def initialize_configs(config_path):
    """初始化系统配置和用户配置"""
    global config_loader, system_config, zone_dungeons

    # 加载系统配置
    try:
        system_config = load_system_config()
    except Exception as e:
        logger.warning(f"⚠️ 加载系统配置失败: {e}，使用默认配置")
        system_config = None

    # 加载用户配置
    try:
        config_loader = load_config(config_path)
        zone_dungeons = config_loader.get_zone_dungeons()
    except Exception as e:
        logger.error(f"❌ 加载配置失败: {e}")
        sys.exit(1)


def show_progress_statistics(db):
    """显示进度统计信息

    Returns:
        tuple: (completed_count, total_selected_dungeons, total_dungeons)
    """
    # 清理旧记录
    db.cleanup_old_records(days_to_keep=7)

    # 显示今天已通关的副本
    completed_count = db.get_today_completed_count()
    if completed_count > 0:
        logger.info(f"📊 今天已通关 {completed_count} 个副本")
        completed_dungeons = db.get_today_completed_dungeons()
        for zone, dungeon in completed_dungeons[:5]:  # 只显示前5个
            logger.info(f"  ✅ {zone} - {dungeon}")
        if len(completed_dungeons) > 5:
            logger.info(f"  ... 还有 {len(completed_dungeons) - 5} 个")
        logger.info("")

    # 计算选定的副本总数
    if zone_dungeons is None:
        logger.error("❌ 区域副本配置未初始化")
        sys.exit(1)

    total_selected_dungeons = sum(
        sum(1 for d in dungeons if d.get("selected", True))
        for dungeons in zone_dungeons.values()
    )
    total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())

    logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本")
    logger.info(f"📊 选定: {total_selected_dungeons} 个副本")
    logger.info(f"📊 已完成: {completed_count} 个副本")

    # 检查是否所有选定的副本都已完成
    if completed_count >= total_selected_dungeons:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 今天所有选定的副本都已完成！")
        logger.info("=" * 60)
        logger.info("💤 无需执行任何操作，脚本退出")
        return completed_count, total_selected_dungeons, total_dungeons

    remaining_dungeons = total_selected_dungeons - completed_count
    logger.info(f"📊 剩余: {remaining_dungeons} 个副本待通关\n")

    return completed_count, total_selected_dungeons, total_dungeons


def initialize_device_and_ocr():
    """初始化设备连接和OCR助手"""
    global ocr_helper

    from airtest.core.api import connect_device, auto_setup
    from ocr_helper import OCRHelper

    connect_device("Android:///")
    auto_setup(__file__)
    ocr_helper = OCRHelper(output_dir="output")


def run_dungeon_traversal(db, total_dungeons):
    """执行副本遍历主循环

    Returns:
        int: 本次运行完成的副本数量
    """
    global config_loader, zone_dungeons

    if config_loader is None or zone_dungeons is None:
        logger.error("❌ 配置未初始化")
        sys.exit(1)

    daily_collect_finished = False
    dungeon_index = 0
    processed_dungeons = 0

    # 遍历所有区域
    for zone_idx, (zone_name, dungeons) in enumerate(zone_dungeons.items(), 1):
        logger.info(f"\n{'#' * 60}")
        logger.info(f"# 🌍 [{zone_idx}/{len(zone_dungeons)}] 区域: {zone_name}")
        logger.info(f"# 🎯 副本数: {len(dungeons)}")
        logger.info(f"{'#' * 60}")

        # 遍历副本
        for dungeon_dict in dungeons:
            # 在每个副本开始前检查停止信号
            if check_stop_signal():
                logger.info(f"\n📊 统计: 本次运行完成 {processed_dungeons} 个副本")
                logger.info("👋 已停止执行")
                back_to_main()
                return processed_dungeons

            dungeon_name = dungeon_dict["name"]
            is_selected = dungeon_dict["selected"]
            dungeon_index += 1

            # 检查是否选定该副本
            if not is_selected:
                logger.info(
                    f"⏭️ [{dungeon_index}/{total_dungeons}] 未选定，跳过: {dungeon_name}"
                )
                continue

            # 先检查是否已通关，如果已通关则跳过，不需要切换区域
            if db.is_dungeon_completed(zone_name, dungeon_name):
                logger.info(
                    f"⏭️ [{dungeon_index}/{total_dungeons}] 已通关，跳过: {dungeon_name}"
                )
                continue

            # 正式开始挂机 - 只在配置启用时执行
            if not daily_collect_finished and config_loader.is_daily_collect_enabled():
                daily_collect()
                daily_collect_finished = True

            open_map()
            if not switch_to_zone(zone_name):
                logger.warning(f"⏭️ 跳过区域: {zone_name}")
                continue

            # 完成副本后会回到主界面，需要重新打开地图
            if process_dungeon(
                dungeon_name, zone_name, dungeon_index, total_dungeons, db
            ):
                processed_dungeons += 1
                # 每完成3个副本就卖垃圾
                if processed_dungeons % 3 == 0:
                    sell_trashes()
                    back_to_main()

        logger.info(f"\n✅ 完成区域: {zone_name}")

    return processed_dungeons


def main():
    """主函数 - 副本自动遍历脚本入口"""
    global config_loader, system_config, zone_dungeons, ocr_helper

    # 1. 解析命令行参数
    args = parse_arguments()

    # 2. 显示欢迎信息（如果不是加载账号模式）
    if not args.load_account:
        logger.info("\n" + "=" * 60)
        logger.info("🎮 副本自动遍历脚本")
        logger.info("=" * 60 + "\n")

    # 3. 检查并启动模拟器（除非明确跳过）
    if not args.skip_emulator_check:
        if not check_and_start_emulator():
            logger.error("❌ 模拟器准备失败，脚本退出")
            sys.exit(1)
    else:
        logger.info("⚠️ 跳过模拟器检查（--skip-emulator-check）")

    # 4. 处理加载账号模式（如果指定）
    if args.load_account:
        handle_load_account_mode(args.load_account)
        return

    # 5. 初始化配置
    initialize_configs(args.config)

    # 6. 检查进度统计
    if config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)

    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        completed_count, total_selected_dungeons, total_dungeons = (
            show_progress_statistics(db)
        )

        # 如果所有副本都已完成，直接退出
        if completed_count >= total_selected_dungeons:
            return

    # 7. 初始化设备和OCR
    initialize_device_and_ocr()

    # 8. 选择角色（如果配置了职业）
    if config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)
    char_class = config_loader.get_char_class()
    if char_class:
        select_character(char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")

    # 9. 执行副本遍历
    if config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)

    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        run_dungeon_traversal(db, total_dungeons)

        # 10. 显示完成信息
        logger.info("\n" + "=" * 60)
        logger.info(f"🎉 全部完成！今天共通关 {db.get_today_completed_count()} 个副本")
        logger.info("=" * 60 + "\n")
        back_to_main()


if __name__ == "__main__":
    main()
