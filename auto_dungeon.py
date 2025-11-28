__author__ = "Airtest"
import sys
import os
import logging
import argparse
import requests
import urllib.parse
import time
from typing import Optional
from wrapt_timeout_decorator import timeout as timeout_decorator


from airtest.core.api import (
    wait,
    sleep,
    touch,
    swipe,
    Template,
    stop_app,
    start_app,
    connect_device,
    auto_setup,
    keyevent,
    text,
    shell,
    log,
    exists,
)
from airtest.core.settings import Settings as ST
from airtest.core.error import TargetNotFoundError
from tqdm import tqdm
from transitions import Machine, MachineError

# 设置 Airtest 日志级别
airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)

ST.FIND_TIMEOUT = 10  # type: ignore[assignment]
ST.FIND_TIMEOUT_TMP = 0.1  # type: ignore[assignment]

# 导入通用日志配置模块
from logger_config import setup_logger_from_config, update_all_loki_labels  # noqa: E402
from project_paths import resolve_project_path  # noqa: E402

# 导入自定义的数据库模块和配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DungeonProgressDB  # noqa: E402
from config_loader import load_config  # noqa: E402
from system_config_loader import load_system_config  # noqa: E402
from emulator_manager import EmulatorManager  # noqa: E402
from error_dialog_monitor import ErrorDialogMonitor  # noqa: E402
from coordinates import (  # noqa: E402
    DEPLOY_CONFIRM_BUTTON,
    ONE_KEY_DEPLOY,
    ONE_KEY_REWARD,
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

SETTINGS_TEMPLATE = Template(
    str(resolve_project_path("images", "settings_button.png")),
    resolution=(720, 1280),
    record_pos=(0.426, -0.738),
)

GIFTS_TEMPLATE = Template(
    str(resolve_project_path("images", "gifts_button.png")),
    resolution=(720, 1280),
    record_pos=(0.428, -0.424),
)

MAP_DUNGEON_TEMPLATE = Template(
    str(resolve_project_path("images", "map_dungeon.png")),
    resolution=(720, 1280),
    record_pos=(0.35, 0.422),
)

ENTER_GAME_BUTTON_TEMPLATE = Template(
    str(resolve_project_path("images", "enter_game_button.png")),
    resolution=(720, 1280),
)

CLICK_INTERVAL = 1
STOP_FILE = str(resolve_project_path(".stop_dungeon"))  # 停止标记文件路径

# 配置彩色日志（从系统配置文件加载 Loki 配置）
logger = setup_logger_from_config(use_color=True)

# 设置 OCRHelper 的日志级别
logging.getLogger("ocr_helper").setLevel(logging.INFO)


# 全局变量，将在 main 函数中初始化
config_loader = None
system_config = None
zone_dungeons = None
ocr_helper = None
emulator_manager = None
target_emulator = None  # 目标模拟器名称
config_name = None  # 配置文件名称（用于 Loki 标签）
error_dialog_monitor = None  # 全局错误对话框监控器


def check_and_start_emulator(emulator_name: Optional[str] = None):
    """
    检查模拟器状态并在需要时启动
    支持指定特定的模拟器实例

    Args:
        emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'，如果为 None 则使用默认行为

    Returns:
        bool: 准备成功返回True，失败返回False
    """
    global emulator_manager, target_emulator

    logger.info("\n" + "=" * 60)
    if emulator_name:
        logger.info(f"🔍 检查模拟器状态: {emulator_name}")
        target_emulator = emulator_name
    else:
        logger.info("🔍 检查BlueStacks模拟器状态")
    logger.info("=" * 60)

    # 初始化模拟器管理器
    if emulator_manager is None:
        emulator_manager = EmulatorManager()

    # 如果指定了模拟器名称，使用管理器启动
    if emulator_name:
        # 获取设备列表，检查 emulator_name 是否存在
        devices = emulator_manager.get_adb_devices()
        if emulator_name not in devices:
            logger.warning(f"⚠️ 模拟器 {emulator_name} 不在设备列表中")
            logger.info(f"   可用设备: {list(devices.keys()) if devices else '无'}")
            logger.info("🚀 尝试启动对应的 BlueStacks 实例...")

            # 尝试启动对应的 BlueStacks 实例
            if not emulator_manager.start_bluestacks_instance(emulator_name):
                error_msg = f"❌ 无法启动模拟器 {emulator_name} 对应的 BlueStacks 实例"
                logger.error(error_msg)
                # 发送 Bark 通知
                send_bark_notification(
                    "副本助手 - 错误",
                    f"无法启动模拟器 {emulator_name} 对应的 BlueStacks 实例",
                    level="timeSensitive",
                )
                return False
            logger.info(f"✅ 模拟器 {emulator_name} 已启动, 等待60秒...")
            sleep(60)  # 等待模拟器启动完毕
        else:
            logger.info(f"✅ 模拟器 {emulator_name} 已在设备列表中")

        if not emulator_manager.start_bluestacks_instance(emulator_name):
            logger.error(f"❌ 无法启动模拟器: {emulator_name}")
            # 发送 Bark 通知
            send_bark_notification(
                "副本助手 - 错误",
                f"无法启动模拟器: {emulator_name}",
                level="timeSensitive",
            )
            return False
    else:
        # 原有逻辑：检查并启动默认模拟器
        if emulator_manager.check_bluestacks_running():
            logger.info("✅ BlueStacks模拟器已在运行")
        else:
            logger.info("⚠️ BlueStacks模拟器未运行")
            if not emulator_manager.start_bluestacks():
                logger.error("❌ 无法启动BlueStacks模拟器")
                return False

    # 无论模拟器是否刚启动，都执行adb devices
    if not emulator_manager.ensure_adb_connection():
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


def timer_decorator(func):
    """
    装饰器：计算函数的执行时间

    专门用于需要监控执行时间的函数，特别是 is_main_world() 这种频繁调用的函数

    :param func: 要装饰的函数
    :return: 包装后的函数
    """
    from functools import wraps
    import logging

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_time = time.perf_counter() - start_time

        # 使用函数所在模块的 logger
        func_logger = logging.getLogger(func.__module__)

        # 根据执行时间使用不同的日志级别和表情符号
        if elapsed_time < 0.01:
            func_logger.debug(
                f"⚡ {func.__name__} 执行时间: {elapsed_time:.4f}秒 (< 10ms)"
            )
        elif elapsed_time < 0.5:
            func_logger.debug(f"⏱️ {func.__name__} 执行时间: {elapsed_time:.4f}秒")
        elif elapsed_time < 1.0:
            func_logger.warning(
                f"🐌 {func.__name__} 执行时间: {elapsed_time:.4f}秒 (> 500ms)"
            )
        else:
            func_logger.warning(
                f"🐢 {func.__name__} 执行时间: {elapsed_time:.4f}秒 (> 1s)"
            )

        return result

    return wrapper


@timer_decorator
@timeout_decorator(30, timeout_exception=TimeoutError)
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


@timer_decorator
def text_exists(
    texts,
    similarity_threshold: float = 0.7,
    use_cache: bool = True,
    regions=None,
):
    """检查当前界面上给定文本列表中的任意一个是否存在。

    Args:
        texts: 文本列表（数组），按优先级从高到低排列；
               如果传入的是单个字符串，则会自动转换为只包含该字符串的列表。
        similarity_threshold: 相似度阈值 (0-1)。
        use_cache: 是否使用 OCR 缓存。
        regions: 要搜索的区域列表 (1-9)，None 表示全屏搜索。

    Returns:
        dict | None: 如果找到任意一个文本，返回 OCR 结果字典（包含 center/text 等字段）；
                      如果都未找到，返回 None。
    """

    # 检查 ocr_helper 是否已初始化
    if ocr_helper is None:
        logger.error("❌ OCR助手未初始化，无法判断文本是否存在")
        return None

    # 规范化输入为列表
    if isinstance(texts, str):
        texts_to_check = [texts]
    else:
        try:
            texts_to_check = list(texts) if texts is not None else []
        except TypeError:
            # 不可迭代的输入，直接当作单个字符串处理
            texts_to_check = [str(texts)]

    if not texts_to_check:
        logger.warning("⚠️ text_exists 收到空的文本列表，直接返回 None")
        return None

    region_desc = f" [区域{regions}]" if regions else ""
    logger.debug(f"🔍 text_exists 检查文本列表: {texts_to_check}{region_desc}")

    # 依次按给定顺序检查每一个文本，找到第一个立即返回
    for candidate in texts_to_check:
        result = ocr_helper.capture_and_find_text(
            candidate,
            confidence_threshold=similarity_threshold,
            occurrence=1,
            use_cache=use_cache,
            regions=regions,
        )

        if result and result.get("found"):
            center = result.get("center")
            logger.info(
                f"✅ text_exists 找到文本: {candidate}{region_desc} at {center}"
            )
            return result

    logger.info(f"🔍 text_exists 未找到任何目标文本: {texts_to_check}{region_desc}")
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

        region_desc = f" [区域{regions}]" if regions else ""
        logger.info(f"✅ 成功点击: {text}{region_desc} at {center}")
        sleep(CLICK_INTERVAL)  # 每个点击后面停顿一下等待界面刷新
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
        if find_text_and_click_safe(word, timeout=3, use_cache=False, regions=[8]):
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
        encoded_title = urllib.parse.quote(title, safe="")
        encoded_message = urllib.parse.quote(message, safe="")

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


@timeout_decorator(5, timeout_exception=TimeoutError)
def is_main_world():
    """
    检查是否在主世界，并输出执行时间

    优化说明：
    - 使用 timeout=0.5 秒而不是默认的 ST.FIND_TIMEOUT（通常为 10 秒）
    - 这个函数被频繁调用（在 auto_combat 和 back_to_main 中的循环中）
    - 如果图片不存在，快速返回 False 而不是等待 3+ 秒
    - 如果图片存在，通常会在 0.1-0.3 秒内找到
    """
    try:
        # 使用 wait() 而不是 exists()，因为 wait() 支持 timeout 参数
        # wait() 会在找到目标或超时后返回
        result = wait(GIFTS_TEMPLATE, timeout=0.3, interval=0.1)
        return bool(result)
    except Exception:
        # 超时或其他异常，说明图片不存在
        return False


def open_map():
    back_to_main()

    touch(MAP_BUTTON)
    logger.info("🗺️ 打开地图")
    sleep(CLICK_INTERVAL)


def is_on_map():
    return exists(MAP_DUNGEON_TEMPLATE)


@timeout_decorator(300, timeout_exception=TimeoutError)
def auto_combat(completed_dungeons=0, total_dungeons=0):
    """自动战斗，带进度条显示

    Args:
        completed_dungeons: 已完成的副本数
        total_dungeons: 总需要完成的副本数
    """
    logger.info("⚔️ 开始自动战斗")
    find_text_and_click_safe("战斗", regions=[8])

    # 使用 wait() 而不是 exists()，避免无限期卡住
    autocombat_template = Template(
        str(resolve_project_path("images", "autocombat_flag.png")),
        record_pos=(-0.001, -0.299),
        resolution=(720, 1280),
    )
    try:
        builtin_auto_combat_activated = bool(
            wait(autocombat_template, timeout=2, interval=0.1)
        )
    except Exception:
        builtin_auto_combat_activated = False

    logger.info(f"内置自动战斗: {builtin_auto_combat_activated}")

    # 使用进度条显示战斗进度
    # 如果提供了副本数信息，显示副本进度；否则显示时间进度
    if total_dungeons > 0:
        # 显示副本进度：已完成/总数
        desc = f"⚔️ 战斗进度 [{completed_dungeons}/{total_dungeons}]"
        bar_format = "{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        total_value = total_dungeons
    else:
        # 显示时间进度（向后兼容）
        desc = "⚔️ 战斗进度"
        bar_format = "{desc} |{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]"
        total_value = 60

    with tqdm(
        total=total_value,
        desc=desc,
        unit="" if total_dungeons > 0 else "s",
        ncols=80,
        bar_format=bar_format,
        initial=completed_dungeons if total_dungeons > 0 else 0,
    ) as pbar:
        start_time = time.time()
        last_update = start_time

        while not is_main_world():
            if check_stop_signal():
                pbar.close()
                raise KeyboardInterrupt("检测到停止信号，退出自动战斗")

            # 更新进度条
            current_time = time.time()

            # 每 0.5 秒更新一次进度条
            if current_time - last_update >= 0.5:
                if total_dungeons > 0:
                    # 副本进度模式：不需要更新（副本数在完成后更新）
                    pass
                else:
                    # 时间进度模式：更新时间
                    update_amount = current_time - last_update
                    pbar.update(update_amount)
                last_update = current_time

            if builtin_auto_combat_activated:
                sleep(1)
                continue

            positions = SKILL_POSITIONS.copy()
            touch(positions[4])
            sleep(0.5)

        # 战斗完成
        if total_dungeons > 0:
            # 副本进度模式：更新到已完成+1
            pbar.update(1)
        else:
            # 时间进度模式：更新进度条到 100%
            remaining = total_value - (time.time() - start_time)
            if remaining > 0:
                pbar.update(remaining)
        pbar.close()
    logger.info("✅ 战斗完成")


def is_on_character_selection(timeout=30):
    """
    检查当前是否位于角色选择界面，模板识别失败时回退到 OCR
    """
    try:
        wait(ENTER_GAME_BUTTON_TEMPLATE, timeout=timeout, interval=0.1)
        return True
    except TargetNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"检测角色选择界面时发生异常: {e}")

    return False


@timeout_decorator(300, timeout_exception=TimeoutError)
def select_character(char_class):
    """
    选择角色

    Args:
        char_class: 角色职业名称（如：战士、法师、刺客等）
    """
    logger.info(f"⚔️ 选择角色: {char_class}")

    global error_dialog_monitor
    if error_dialog_monitor:
        error_dialog_monitor.handle_once()

    in_character_selection = is_on_character_selection(timeout=120)
    # 使用异常处理替代 assert，便于上层捕获和处理错误
    if not in_character_selection:
        logger.error("❌ 未在角色选择界面，无法选择角色")
        raise RuntimeError("未在角色选择界面，无法选择角色")

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
        raise RuntimeError(f"无法找到职业: {char_class}")

    find_text_and_click("进入游戏")
    wait_for_main()


@timeout_decorator(300, timeout_exception=TimeoutError)
def wait_for_main(timeout=300):
    """
    等待回到主界面
    如果 5 分钟（300秒）还没执行结束，则中断执行并发送通知

    注意：添加了 @timeout_decorator(310) 装饰器，确保即使内部逻辑卡住，
    也能被外层的 timeout 机制中断。310秒的装饰器超时比内部300秒的超时稍长，
    这样可以确保内部的超时逻辑先触发。
    """

    logger.info("⏳ 等待战斗结束...")
    start_time = time.time()
    try:
        result = wait(GIFTS_TEMPLATE, timeout=timeout, interval=0.5)
        if result:
            elapsed = time.time() - start_time
            logger.info(f"✅ 战斗结束，用时 {elapsed:.1f} 秒")
    except Exception as e:
        logger.error(f"⏱️ 等待 GIFTS_TEMPLATE 超时或出错: {e}")
        raise TimeoutError("等待主界面超时")


def switch_to_zone(zone_name):
    """切换到指定区域"""
    logger.info(f"\n{'=' * 50}")
    logger.info(f"🌍 切换区域: {zone_name}")
    logger.info(f"{'=' * 50}")

    find_text_and_click_safe("切换区域", timeout=10)

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
            touch((462, 958))  # 出售按钮
            sleep(1)
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
        find_text("进入游戏", timeout=120, regions=[5])
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


@timeout_decorator(60, timeout_exception=TimeoutError)
def back_to_main(max_duration=15, backoff_interval=0.2):
    """
    返回主界面。即使 Airtest 底层调用阻塞，也依旧通过手动计时与兜底手段
    保证最终会超时报错。

    Args:
        max_duration (float): 允许的最大等待时间，单位：秒。默认 55
        backoff_interval (float): 每轮操作结束后的休眠时间，单位：秒
    """
    logger.info("🔙 返回主界面")
    start_time = time.time()
    attempt = 0

    while True:
        if is_main_world():
            logger.info("✅ 已回到主界面")
            return

        elapsed = time.time() - start_time
        if elapsed >= max_duration:
            message = f"back_to_main 超时，已等待 {elapsed:.1f} 秒仍未检测到主界面"
            logger.error(message)
            raise TimeoutError(message)

        attempt += 1

        for _ in range(3):
            try:
                touch(BACK_BUTTON)
            except Exception as e:
                logger.warning(f"⚠️ 发送返回点击失败: {e}")
                break
            sleep(0.1)

        # 每三轮尝试一次系统返回键，进一步保证能触发 UI 返回
        if attempt % 3 == 0:
            try:
                keyevent("BACK")
            except Exception as e:
                logger.warning(f"⚠️ 系统返回键发送失败: {e}")

        # 偶尔直接调用 ADB 指令，避免 Airtest 卡死
        if attempt % 5 == 0:
            try:
                shell("input keyevent 4")
            except Exception as e:
                logger.debug(f"ADB 返回指令失败: {e}")

        sleep(backoff_interval)


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

    @timeout_decorator(300, timeout_exception=TimeoutError)
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

            # 7. 领取 taptap 奖励
            # self._checkin_taptap()

            # 8. 领取邮件
            self._receive_mails()

            self.logger.info("=" * 60)
            self.logger.info("✅ 每日收集操作全部完成")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"❌ 每日收集操作失败: {e}")
            raise

    def _small_cookie(self):
        """领取各种主题奖励"""
        logger.info("领取各种主题奖励[海盗船,冰封王座]")
        back_to_main()
        find_text_and_click("活动", regions=[3])

    def _checkin_taptap(self):
        """签到 taptap,领一些礼品"""
        logger.info("签到 taptap")
        keyevent("HOME")
        find_text_and_click("签到", regions=[1])
        sleep(5)
        find_text_and_click_safe("去签到", regions=[5], timeout=20)
        find_text_and_click_safe("立即签到", regions=[8, 9], timeout=20)
        find_text_and_click_safe("复制", regions=[6, 9], timeout=20)
        start_app("com.ms.ysjyzr")
        sleep(5)
        back_to_main()
        switch_to("战斗")
        send_button = find_text_and_click("发送", regions=[9])
        touch((send_button["center"][0] - 100, send_button["center"][1]))
        shell("input keyevent 279")
        text("")
        touch(send_button["center"])

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

            back_to_main()
        else:
            self.logger.warning("⚠️ 未找到随从按钮，跳过派遣操作")

        # 招募
        find_text_and_click("酒馆", regions=[7])
        res = find_text(
            "招募10次",
            regions=[8, 9],
            occurrence=9,
            raise_exception=False,
            use_cache=False,
        )
        if res:
            for _ in range(4):
                touch(res["center"])
                sleep(1)
        back_to_main()

        # 符文
        find_text_and_click("符文", regions=[9])
        find_text_and_click("抽取十次", regions=[8, 9], use_cache=False)
        back_to_main()

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
        if find_text_and_click_safe(floor_name, regions=[regions[0]], use_cache=False):
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
            res = find_text("开启10次", regions=[8, 9], use_cache=False, timeout=5)
            if res:
                for _ in range(6):
                    touch(res["center"])
                    sleep(0.2)
                    click_back()
            back_to_main()
            self.logger.info("✅ 打开宝箱成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到宝箱: {e}")
            back_to_main()

    def _receive_mails(self):
        """
        领取邮件
        """
        self.logger.info("✉️ 信件 开始领取邮件")
        back_to_main()
        try:
            find_text_and_click("主城", regions=[9])
            find_text_and_click("邮箱", regions=[5])
            res = find_text("一键领取", regions=[8, 9], timeout=5)
            if res:
                for _ in range(3):
                    touch(res["center"])
                    sleep(1)
            back_to_main()
            self.logger.info("✅ 领取邮件成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到一键领取: {e}")
            back_to_main()

    # 保留原始函数名作为向后兼容
    def daily_collect(self):
        """
        向后兼容的函数名
        """
        self.collect_daily_rewards()


class AutoDungeonStateMachine:
    """使用 transitions 管理副本执行状态"""

    STATES = [
        "character_selection",
        "main_menu",
        "dungeon_selection",
        "dungeon_battle",
        "reward_claim",
        "sell_loot",
    ]

    def __init__(self, config_loader):
        self.config_loader = config_loader
        self.current_zone = None
        self.active_dungeon = None
        self.state = None
        self.machine = Machine(
            model=self,
            states=self.STATES,
            initial="character_selection",
            auto_transitions=False,
            send_event=True,
            queued=True,
        )
        self._register_transitions()

    def _register_transitions(self):
        self.machine.add_transition(
            trigger="trigger_select_character",
            source="character_selection",
            dest="main_menu",
            before="_on_select_character",
        )
        self.machine.add_transition(
            trigger="ensure_main_menu",
            source="*",
            dest="main_menu",
            before="_on_return_to_main",
        )
        self.machine.add_transition(
            trigger="prepare_dungeon",
            source="main_menu",
            dest="dungeon_selection",
            conditions="_prepare_dungeon_selection",
        )
        self.machine.add_transition(
            trigger="start_battle",
            source="dungeon_selection",
            dest="dungeon_battle",
            conditions="_start_battle_sequence",
        )
        self.machine.add_transition(
            trigger="complete_battle",
            source="dungeon_battle",
            dest="reward_claim",
            before="_on_reward_state",
        )
        self.machine.add_transition(
            trigger="claim_rewards",
            source="main_menu",
            dest="reward_claim",
            before="_on_reward_state",
        )
        self.machine.add_transition(
            trigger="return_to_main",
            source=["reward_claim", "dungeon_selection"],
            dest="main_menu",
            before="_on_return_to_main",
        )
        self.machine.add_transition(
            trigger="start_selling",
            source="main_menu",
            dest="sell_loot",
            before="_on_sell_loot",
        )
        self.machine.add_transition(
            trigger="finish_selling",
            source="sell_loot",
            dest="main_menu",
            before="_on_return_to_main",
        )

    def _safe_trigger(self, trigger_name, **kwargs):
        try:
            trigger = getattr(self, trigger_name)
            return trigger(**kwargs)
        except (AttributeError, MachineError) as exc:
            logger.error(f"⚠️ 状态机触发失败: {trigger_name} - {exc}")
            return False

    def select_character_state(self, char_class=None):
        if char_class:
            self._safe_trigger("trigger_select_character", char_class=char_class)
            return self.state == "main_menu"
        return self.ensure_main()

    def ensure_main(self):
        self._safe_trigger("ensure_main_menu")
        return self.state == "main_menu"

    def prepare_dungeon_state(self, zone_name, dungeon_name, max_attempts=3):
        self._safe_trigger(
            "prepare_dungeon",
            zone_name=zone_name,
            dungeon_name=dungeon_name,
            max_attempts=max_attempts,
        )
        return self.state == "dungeon_selection"

    def start_battle_state(self, dungeon_name, completed_dungeons=0, total_dungeons=0):
        self._safe_trigger(
            "start_battle",
            dungeon_name=dungeon_name,
            completed_dungeons=completed_dungeons,
            total_dungeons=total_dungeons,
        )
        return self.state == "dungeon_battle"

    def complete_battle_state(self):
        self._safe_trigger("complete_battle", reward_type="battle")
        return self.state == "reward_claim"

    def claim_daily_rewards(self):
        self._safe_trigger("claim_rewards", reward_type="daily_collect")
        return self.state == "reward_claim"

    def return_to_main_state(self):
        self._safe_trigger("return_to_main")
        return self.state == "main_menu"

    def sell_loot(self):
        self._safe_trigger("start_selling")
        return self.state == "sell_loot"

    def finish_sell_loot(self):
        self._safe_trigger("finish_selling")
        return self.state == "main_menu"

    # ----- 状态动作方法 -----
    def _on_select_character(self, event):
        char_class = event.kwargs.get("char_class")
        if not char_class:
            logger.warning("⚠️ 未提供职业信息，保持在主界面")
            return
        logger.info(f"🎭 状态机: 选择职业 {char_class}")
        select_character(char_class)

    def _prepare_dungeon_selection(self, event):
        zone_name = event.kwargs.get("zone_name")
        dungeon_name = event.kwargs.get("dungeon_name")
        max_attempts = event.kwargs.get("max_attempts", 3)

        if not zone_name or not dungeon_name:
            logger.warning("⚠️ 状态机缺少区域或副本信息，无法进入选取状态")
            return False

        logger.info(f"🗺️ 状态机: 前往区域 {zone_name}，寻找副本 {dungeon_name}")
        open_map()
        if self.current_zone != zone_name:
            if not switch_to_zone(zone_name):
                logger.warning(f"⚠️ 状态机无法切换到区域: {zone_name}")
                return False
            self.current_zone = zone_name

        success = focus_and_click_dungeon(
            dungeon_name, zone_name, max_attempts=max_attempts
        )

        if success:
            self.active_dungeon = dungeon_name
        else:
            logger.warning(f"⚠️ 状态机无法定位副本: {dungeon_name}")

        return success

    def _start_battle_sequence(self, event):
        dungeon_name = event.kwargs.get("dungeon_name") or self.active_dungeon
        completed = event.kwargs.get("completed_dungeons", 0)
        total = event.kwargs.get("total_dungeons", 0)

        if not dungeon_name:
            logger.warning("⚠️ 状态机未记录当前副本，无法进入战斗")
            return False

        if not click_free_button():
            logger.info(f"ℹ️ 副本 {dungeon_name} 今日已完成或无免费次数")
            return False

        logger.info(f"⚔️ 状态机: 进入副本战斗 - {dungeon_name}")
        find_text_and_click_safe("战斗", regions=[8])
        auto_combat(completed_dungeons=completed, total_dungeons=total)
        return True

    def _on_reward_state(self, event):
        reward_type = event.kwargs.get("reward_type", "battle")

        if reward_type == "daily_collect":
            logger.info("🎁 状态机: 执行每日领取流程")
            try:
                daily_collect()
            except Exception as exc:
                logger.error(f"❌ 每日领取失败: {exc}")
                raise
        else:
            logger.info("🎁 状态机: 处理副本奖励")

    def _on_return_to_main(self, event):
        logger.info("🏠 状态机: 返回主界面")
        back_to_main()
        self.current_zone = None
        self.active_dungeon = None

    def _on_sell_loot(self, event):
        logger.info("🧹 状态机: 卖出垃圾道具")
        sell_trashes()


# 创建全局实例，保持向后兼容
daily_collect_manager = DailyCollectManager(config_loader)


@timeout_decorator(300, timeout_exception=TimeoutError)
def daily_collect():
    """
    领取每日挂机奖励
    保持向后兼容的函数包装器
    """
    global daily_collect_manager

    if config_loader is None:
        raise RuntimeError("配置加载器未初始化，无法执行每日收集")

    # 确保使用最新的配置
    if daily_collect_manager.config_loader != config_loader:
        daily_collect_manager = DailyCollectManager(config_loader)

    config_name = config_loader.get_config_name() or "default"

    with DungeonProgressDB(config_name=config_name) as db:
        if db.is_daily_collect_completed():
            logger.info("⏭️ 今日每日收集已完成，跳过重复执行")
            return False

        daily_collect_manager.collect_daily_rewards()
        db.mark_daily_collect_completed()
        logger.info("💾 已记录今日每日收集完成")
        return True


def focus_and_click_dungeon(dungeon_name, zone_name, max_attempts=2):
    """
    尝试聚焦到指定副本并点击，必要时重新刷新地图

    Args:
        dungeon_name (str): 副本名称
        zone_name (str): 区域名称
        max_attempts (int): 最大尝试次数

    Returns:
        bool: 是否成功点击副本入口
    """
    for attempt in range(max_attempts):
        use_cache = attempt == 0
        result = find_text_and_click_safe(
            dungeon_name,
            timeout=6,
            occurrence=9,
            use_cache=use_cache,
        )
        if result:
            return True

        logger.warning(
            f"⚠️ 未能找到副本: {dungeon_name} (第 {attempt + 1}/{max_attempts} 次尝试)"
        )

        if attempt < max_attempts - 1:
            logger.info("🔄 重新打开地图并刷新区域后再试")
            open_map()
            if not switch_to_zone(zone_name):
                logger.warning(f"⚠️ 刷新区域失败: {zone_name}")
                continue
            sleep(1)

    return False


@timeout_decorator(300, timeout_exception=TimeoutError)
def process_dungeon(
    dungeon_name,
    zone_name,
    index,
    total,
    db,
    completed_dungeons=0,
    remaining_dungeons=0,
    state_machine=None,
):
    """处理单个副本, 返回是否成功完成

    Args:
        dungeon_name: 副本名称
        zone_name: 区域名称
        index: 当前副本在所有副本中的索引
        total: 总副本数
        db: 数据库实例
        completed_dungeons: 已完成的副本数（用于进度条显示）
        remaining_dungeons: 需要完成的副本总数（用于进度条显示）

    注意：调用此函数前应该已经检查过是否已通关
    """
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

    if state_machine is None:
        logger.error("❌ 状态机未初始化，无法处理副本")
        return False

    if not state_machine.prepare_dungeon_state(
        zone_name=zone_name, dungeon_name=dungeon_name, max_attempts=3
    ):
        state_machine.ensure_main()
        return False

    battle_started = state_machine.start_battle_state(
        dungeon_name=dungeon_name,
        completed_dungeons=completed_dungeons,
        total_dungeons=remaining_dungeons,
    )

    if not battle_started:
        logger.warning("⚠️ 无免费按钮，标记为已完成")
        db.mark_dungeon_completed(zone_name, dungeon_name)
        click_back()
        state_machine.return_to_main_state()
        return True

    logger.info(f"✅ 完成: {dungeon_name}")
    state_machine.complete_battle_state()

    # 记录通关状态
    db.mark_dungeon_completed(zone_name, dungeon_name)

    sleep(CLICK_INTERVAL)
    state_machine.return_to_main_state()
    return True


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
    parser.add_argument(
        "--emulator",
        type=str,
        help="指定模拟器网络地址（如：127.0.0.1:5555），用于多模拟器场景",
    )
    parser.add_argument(
        "-e",
        "--env",
        type=str,
        action="append",
        dest="env_overrides",
        help="环境变量覆盖，格式为 key=value（可多次使用，如 -e enable_daily_collect=false -e enable_quick_afk=true）",
    )
    return parser.parse_args()


def handle_load_account_mode(account_name, emulator_name: Optional[str] = None):
    """
    处理账号加载模式

    Args:
        account_name: 账号名称
        emulator_name: 模拟器名称，如 'emulator-5554'
    """
    global ocr_helper, emulator_manager, target_emulator

    logger.info("\n" + "=" * 60)
    logger.info("🔄 账号加载模式")
    logger.info("=" * 60 + "\n")
    logger.info(f"📱 目标账号: {account_name}")
    if emulator_name:
        logger.info(f"📱 目标模拟器: {emulator_name}")

    # 初始化设备和OCR
    from ocr_helper import OCRHelper

    # 确定连接字符串
    if emulator_name:
        target_emulator = emulator_name
        if emulator_manager is None:
            emulator_manager = EmulatorManager()

        # 获取设备列表，检查 emulator_name 是否存在
        devices = emulator_manager.get_adb_devices()
        if emulator_name not in devices:
            logger.warning(f"⚠️ 模拟器 {emulator_name} 不在设备列表中")
            logger.info(f"   可用设备: {list(devices.keys()) if devices else '无'}")
            logger.info("🚀 尝试启动对应的 BlueStacks 实例...")

            # 尝试启动对应的 BlueStacks 实例
            if not emulator_manager.start_bluestacks_instance(emulator_name):
                error_msg = f"❌ 无法启动模拟器 {emulator_name} 对应的 BlueStacks 实例"
                logger.error(error_msg)
                # 发送 Bark 通知
                send_bark_notification(
                    "副本助手 - 错误",
                    f"无法启动模拟器 {emulator_name} 对应的 BlueStacks 实例",
                    level="timeSensitive",
                )
                sys.exit(1)
        else:
            logger.info(f"✅ 模拟器 {emulator_name} 已在设备列表中")

        connection_string = emulator_manager.get_emulator_connection_string(
            emulator_name
        )
        logger.info(f"   连接字符串: {connection_string}")
    else:
        connection_string = "Android:///"

    # 关键：先连接设备，再调用 auto_setup
    # 这样可以避免 auto_setup 重新初始化导致其他设备断开
    auto_setup(__file__, logdir=True)

    connect_device(connection_string)

    ocr_helper = OCRHelper(
        max_cache_size=200,  # 最大缓存条目数
        hash_type="dhash",  # 哈希算法
        hash_threshold=10,  # 汉明距离阈值
    )

    # 切换账号
    try:
        switch_account(account_name)
        logger.info(f"✅ 成功加载账号: {account_name}")
        logger.info("=" * 60 + "\n")
    except Exception as e:
        logger.error(f"❌ 加载账号失败: {e}")
        sys.exit(1)


def apply_env_overrides(env_overrides):
    """
    应用命令行环境变量覆盖

    Args:
        env_overrides: 环境变量覆盖列表，格式为 ['key=value', ...]

    Returns:
        dict: 解析后的覆盖字典
    """
    overrides = {}
    if not env_overrides:
        return overrides

    for override in env_overrides:
        if "=" not in override:
            logger.warning(f"⚠️ 无效的环境变量格式: {override}，应为 key=value")
            continue

        key, value = override.split("=", 1)
        key = key.strip()
        value = value.strip()

        # 将字符串值转换为适当的类型
        if value.lower() == "true":
            overrides[key] = True
        elif value.lower() == "false":
            overrides[key] = False
        elif value.isdigit():
            overrides[key] = int(value)
        else:
            overrides[key] = value

        logger.info(f"📝 环境变量覆盖: {key} = {overrides[key]}")

    return overrides


def initialize_configs(config_path, env_overrides=None):
    """初始化系统配置和用户配置

    Args:
        config_path: 配置文件路径
        env_overrides: 环境变量覆盖列表，格式为 ['key=value', ...]
    """
    global config_loader, system_config, zone_dungeons, config_name, logger

    # 加载系统配置
    try:
        system_config = load_system_config()
    except Exception as e:
        logger.warning(f"⚠️ 加载系统配置失败: {e}，使用默认配置")
        system_config = None

    # 加载用户配置
    try:
        config_loader = load_config(config_path)

        # 获取配置文件名称，用于 Loki 标签
        config_name = config_loader.get_config_name()

        # 重新初始化日志，添加配置文件名称标签
        logger = setup_logger_from_config(
            use_color=True, loki_labels={"config": config_name}
        )

        # 更新所有已创建的日志记录器的 Loki 标签
        # 这样 emulator_manager, ocr_helper 等模块的日志也会包含 config 标签
        update_all_loki_labels({"config": config_name})

        # 应用环境变量覆盖
        if env_overrides:
            overrides = apply_env_overrides(env_overrides)
            for key, value in overrides.items():
                if hasattr(config_loader, key):
                    logger.info(f"🔄 覆盖配置: {key} = {value}")
                    setattr(config_loader, key, value)
                else:
                    logger.warning(f"⚠️ 配置中不存在属性: {key}")

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

    # 汇总所有待通关的副本，便于日志展示详细名单
    remaining_dungeons_detail = []
    for zone_name, dungeons in zone_dungeons.items():
        for dungeon in dungeons:
            if not dungeon.get("selected", True):
                continue
            if not db.is_dungeon_completed(zone_name, dungeon["name"]):
                remaining_dungeons_detail.append((zone_name, dungeon["name"]))

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

    remaining_dungeons = len(remaining_dungeons_detail)
    logger.info(f"📊 剩余: {remaining_dungeons} 个副本待通关")
    if remaining_dungeons_detail:
        logger.info("📋 待通关副本清单:")
        for zone_name, dungeon_name in remaining_dungeons_detail:
            logger.info(f"  • {zone_name} - {dungeon_name}")
    logger.info("")

    return completed_count, total_selected_dungeons, total_dungeons


def initialize_device_and_ocr(emulator_name: Optional[str] = None):
    """
    初始化设备连接和OCR助手
    支持多个模拟器同时连接，不会断开其他模拟器

    Args:
        emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'，如果为 None 则使用默认连接
    """
    global ocr_helper, emulator_manager, target_emulator

    from ocr_helper import OCRHelper

    # 确定连接字符串
    if emulator_name:
        target_emulator = emulator_name
        if emulator_manager is None:
            emulator_manager = EmulatorManager()

        # 获取设备列表，检查 emulator_name 是否存在
        devices = emulator_manager.get_adb_devices()
        if emulator_name not in devices:
            logger.warning(f"⚠️ 模拟器 {emulator_name} 不在设备列表中")
            logger.info(f"   可用设备: {list(devices.keys()) if devices else '无'}")
            logger.info("🚀 尝试启动对应的 BlueStacks 实例...")

            # 尝试启动对应的 BlueStacks 实例
            if not emulator_manager.start_bluestacks_instance(emulator_name):
                error_msg = f"❌ 无法启动模拟器 {emulator_name} 对应的 BlueStacks 实例"
                logger.error(error_msg)
                # 发送 Bark 通知
                send_bark_notification(
                    "副本助手 - 错误",
                    f"无法启动模拟器 {emulator_name} 对应的 BlueStacks 实例",
                    level="timeSensitive",
                )
                raise RuntimeError(f"无法启动模拟器 {emulator_name}")
        else:
            logger.info(f"✅ 模拟器 {emulator_name} 已在设备列表中")

        connection_string = emulator_manager.get_emulator_connection_string(
            emulator_name
        )
        logger.info(f"📱 连接到模拟器: {emulator_name}")
        logger.info(f"   连接字符串: {connection_string}")
    else:
        connection_string = "Android:///"
        logger.info("📱 使用默认连接字符串")

    # 连接设备（Airtest 支持多设备连接，不会断开其他设备）
    try:
        # 关键：先连接设备，再调用 auto_setup
        # 这样可以避免 auto_setup 重新初始化导致其他设备断开
        auto_setup(__file__, logdir=True)
        logger.info("自动配置设备中...")
        connect_device(connection_string)
        logger.info("   ✅ 成功连接到设备")

    except Exception as e:
        logger.error(f"   ❌ 连接设备失败: {e}")
        raise

    if ocr_helper is None:
        ocr_helper = OCRHelper(output_dir="output")


def count_remaining_selected_dungeons(db):
    """统计未完成的选定副本数量"""
    global config_loader, zone_dungeons

    if config_loader is None or zone_dungeons is None:
        logger.warning("⚠️ 配置未初始化，无法计算剩余副本")
        return 0

    remaining = 0
    for zone_name, dungeons in zone_dungeons.items():
        for dungeon_dict in dungeons:
            if not dungeon_dict.get("selected", True):
                continue
            if not db.is_dungeon_completed(zone_name, dungeon_dict["name"]):
                remaining += 1
    return remaining


@timeout_decorator(7200, timeout_exception=TimeoutError)  # 2 小时超时
def run_dungeon_traversal(db, total_dungeons, state_machine):
    """执行副本遍历主循环

    Returns:
        int: 本次运行完成的副本数量
    """
    global config_loader, zone_dungeons

    if config_loader is None or zone_dungeons is None or state_machine is None:
        logger.error("❌ 配置未初始化")
        sys.exit(1)

    daily_collect_finished = db.is_daily_collect_completed()
    if daily_collect_finished and config_loader.is_daily_collect_enabled():
        logger.info("⏭️ 今日每日收集任务已完成，跳过 daily_collect 步骤")
    dungeon_index = 0
    processed_dungeons = 0

    # 计算需要完成的副本总数（排除已完成和未选定的副本）
    remaining_dungeons = count_remaining_selected_dungeons(db)

    logger.info(f"📊 需要完成的副本总数: {remaining_dungeons}")

    # 获取今天已完成的副本数
    completed_today = db.get_today_completed_count()
    logger.info(f"📊 今天已完成的副本数: {completed_today}")

    state_machine.ensure_main()

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
                state_machine.ensure_main()
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
                if state_machine.claim_daily_rewards():
                    daily_collect_finished = True
                    state_machine.return_to_main_state()

            # 完成副本后会回到主界面，需要状态机重新处理
            if process_dungeon(
                dungeon_name,
                zone_name,
                dungeon_index,
                total_dungeons,
                db,
                completed_today + processed_dungeons,
                remaining_dungeons,
                state_machine=state_machine,
            ):
                processed_dungeons += 1
                # 每完成3个副本就卖垃圾
                if processed_dungeons % 3 == 0:
                    if state_machine.sell_loot():
                        state_machine.finish_sell_loot()
                    else:
                        sell_trashes()
                        back_to_main()
                        state_machine.ensure_main()

        logger.info(f"\n✅ 完成区域: {zone_name}")

    return processed_dungeons


def main_wrapper():
    """主函数包装器 - 处理超时和重启逻辑"""
    global \
        config_loader, \
        system_config, \
        zone_dungeons, \
        ocr_helper, \
        logger, \
        error_dialog_monitor

    max_restarts = 10  # 最大重启次数
    restart_count = 0

    while restart_count < max_restarts:
        try:
            if error_dialog_monitor is None:
                error_dialog_monitor = ErrorDialogMonitor(logger)
            error_dialog_monitor.start()

            main()
            # 正常完成，退出循环
            return

        except TimeoutError as e:
            restart_count += 1
            logger.error(f"\n❌ 检测到超时错误: {e}")
            logger.error("⏱️ 操作超时，可能是网络错误或识别失败导致的卡死")
            log("超时错误" + str(e), snapshot=True)

            if restart_count < max_restarts:
                logger.warning(
                    f"\n🔄 正在重启程序... (第 {restart_count}/{max_restarts} 次重启)"
                )
                logger.warning("💡 建议检查网络连接和游戏状态")

                # 发送通知
                send_bark_notification(
                    "副本助手 - 超时重启",
                    f"程序因超时重启 ({restart_count}/{max_restarts})\n错误: {str(e)}",
                    level="timeSensitive",
                )

                # 清理全局变量
                config_loader = None
                system_config = None
                zone_dungeons = None
                ocr_helper = None

                # 等待一段时间后重启
                time.sleep(5)

                # 重新执行main函数
                continue
            else:
                logger.error(f"\n❌ 已达到最大重启次数 ({max_restarts})，程序退出")
                send_bark_notification(
                    "副本助手 - 严重错误",
                    f"程序因多次超时失败退出\n重启次数: {restart_count}\n最后错误: {str(e)}",
                    level="timeSensitive",
                )
                sys.exit(1)

        except KeyboardInterrupt:
            logger.info("\n\n⛔ 用户中断，程序退出")
            sys.exit(0)

        except Exception as e:
            logger.error(f"\n❌ 发生未预期的错误: {e}")
            import traceback

            error_traceback = traceback.format_exc()
            logger.error(error_traceback)

            # 发送 critical 日志，触发 Grafana 告警
            logger.critical(
                f"脚本异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}"
            )

            send_bark_notification(
                "副本助手 - 错误", f"程序发生错误: {str(e)}", level="timeSensitive"
            )
            sys.exit(1)
        finally:
            if error_dialog_monitor:
                error_dialog_monitor.stop()
                error_dialog_monitor = None


def main():
    """主函数 - 副本自动遍历脚本入口"""
    global config_loader, system_config, zone_dungeons, ocr_helper, logger

    # 1. 解析命令行参数
    args = parse_arguments()

    # 2. 显示欢迎信息（如果不是加载账号模式）
    if not args.load_account:
        logger.info("\n" + "=" * 60)
        logger.info("🎮 副本自动遍历脚本")
        logger.info("=" * 60 + "\n")

    # 3. 处理加载账号模式（如果指定）
    if args.load_account:
        # 加载账号模式需要先启动模拟器
        if not args.skip_emulator_check:
            if not check_and_start_emulator(args.emulator):
                logger.error("❌ 模拟器准备失败，脚本退出")
                sys.exit(1)
        handle_load_account_mode(args.load_account, args.emulator)
        return

    # 4. 初始化配置
    initialize_configs(args.config, args.env_overrides)

    # 5. 检查进度统计 - 决定是否需要启动模拟器
    if config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)

    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        completed_count, total_selected_dungeons, total_dungeons = (
            show_progress_statistics(db)
        )

        # 如果所有副本都已完成，直接退出（无需启动模拟器）
        if completed_count >= total_selected_dungeons:
            logger.info("✅ 无需启动模拟器，脚本退出")
            return

    # 6. 检查并启动模拟器（只在有需要完成的副本时执行）
    logger.info("\n🔍 检测到有未完成的副本，准备启动模拟器...")
    if not args.skip_emulator_check:
        if not check_and_start_emulator(args.emulator):
            logger.error("❌ 模拟器准备失败，脚本退出")
            sys.exit(1)
    else:
        logger.info("⚠️ 跳过模拟器检查（--skip-emulator-check）")

    # 7. 初始化设备和OCR
    initialize_device_and_ocr(args.emulator)

    state_machine = AutoDungeonStateMachine(config_loader)

    # 启动游戏
    logger.info("启动游戏...")
    stop_app("com.ms.ysjyzr")
    sleep(2)
    start_app("com.ms.ysjyzr")

    # 等待进入角色选择界面
    if is_on_character_selection(120):
        logger.info("已在角色选择界面")
    # 8. 选择角色（如果配置了职业）
    if config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)
    char_class = config_loader.get_char_class()
    if char_class:
        logger.info(f"开始选择角色: {char_class}")
        state_machine.select_character_state(char_class=char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")
        state_machine.ensure_main()

    # 9. 执行副本遍历
    if config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)

    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        iteration = 1
        while True:
            logger.info(f"\n🔁 开始第 {iteration} 轮副本遍历…")
            run_dungeon_traversal(db, total_dungeons, state_machine)

            remaining_after_run = count_remaining_selected_dungeons(db)
            if remaining_after_run <= 0:
                break

            logger.warning(
                f"⚠️ 第 {iteration} 轮结束后仍有 {remaining_after_run} 个副本未完成，准备继续"
            )
            iteration += 1

        # 10. 显示完成信息
        logger.info("\n" + "=" * 60)
        logger.info(f"🎉 全部完成！今天共通关 {db.get_today_completed_count()} 个副本")
        logger.info("=" * 60 + "\n")
        state_machine.ensure_main()


if __name__ == "__main__":
    main_wrapper()
