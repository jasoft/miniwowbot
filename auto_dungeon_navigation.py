"""
auto_dungeon 导航模块
"""

import logging
import os
import time
from datetime import datetime
from typing import List

from airtest.core.api import (
    keyevent,
    touch,
    wait,
    exists,
    snapshot,
)
from airtest.core.error import TargetNotFoundError

from auto_dungeon_utils import sleep
from auto_dungeon_ui import find_text_and_click_safe
from auto_dungeon_config import (
    ENTER_GAME_BUTTON_TEMPLATE,
    GIFTS_TEMPLATE,
    MAP_DUNGEON_TEMPLATE,
    LAST_OCCURRENCE,
)
from coordinates import (
    BACK_BUTTON,
    CLOSE_ZONE_MENU,
    MAP_BUTTON,
)

logger = logging.getLogger(__name__)

#: 游戏包名，用于判断游戏是否仍在前台。
GAME_PACKAGE = "com.ms.ysjyzr"

#: 最近一次截图失败的原因，供通知正文引用（``None`` 表示最近一次成功）
_last_screenshot_error: str | None = None


class GameNotForegroundError(TimeoutError):
    """游戏已不在前台，继续等待主界面没有意义。

    继承 :class:`TimeoutError` 是为了**复用** ``main_wrapper`` 已有的恢复路径：
    一旦探测到游戏被切到后台或已退出，唯一有效的恢复手段就是重新走一遍
    「关闭游戏 → 启动游戏 → 等角色选择界面」，而这恰好是 ``main_wrapper``
    捕获 :class:`TimeoutError` 后做的事。
    """


def get_last_screenshot_error() -> str | None:
    """返回最近一次 ``save_error_screenshot`` 失败的原因。

    推送里出现「截图失败」时，光知道失败没用，必须知道**为什么**。
    早期实现把异常记在 ``logger.debug`` 级，默认日志级别下直接看不见，
    于是「截图失败」变成一条无法排查的死信息。

    Returns:
        str | None: 失败原因；最近一次保存成功则为 ``None``。
    """
    return _last_screenshot_error


def _has_connected_device() -> bool:
    """判断 airtest 当前是否真的连着设备。

    Returns:
        bool: 有可用设备返回 ``True``。
    """
    try:
        from airtest.core.api import G

        return getattr(G, "DEVICE", None) is not None
    except Exception:  # pragma: no cover - 取不到就按「没设备」处理
        return False


def is_game_foreground(package: str = GAME_PACKAGE) -> bool | None:
    """判断游戏当前是否在前台。

    为什么需要它：``back_to_main`` 靠「点返回按钮 + 按系统返回键」退回主界面。
    一旦游戏已经不在前台（被切到桌面或其它 App），返回键**永远**回不到主界面，
    只能一路空等到超时。2026-09-25 实测：一次退出到桌面后 ``back_to_main``
    连环超时 18 次、白耗约 4.5 分钟，8 个日常任务全部误报失败，
    直到外层「超时重启」才恢复。

    Returns:
        bool | None: ``True`` 游戏在前台；``False`` **明确**不在前台（前台是
        别的应用）；``None`` 无法判定（没有设备或探测本身异常）。
        调用方**不要**把 ``None`` 当成 ``False`` —— 探测抖动不该触发重量级的
        重启动作，宁可退回「等超时」的老行为。
    """
    try:
        from airtest.core.api import G

        device = getattr(G, "DEVICE", None)
        if device is None:
            return None
        top = device.get_top_activity()
    except Exception as e:
        logger.warning(f"⚠️ 探测前台应用失败: {type(e).__name__}: {e}")
        return None

    if not top:
        return None

    top_package = top[0] if isinstance(top, (tuple, list)) else str(top)
    return bool(top_package) and top_package == package


def save_error_screenshot(operation_name: str) -> str:
    """保存错误截图到 log 目录，返回文件路径。

    失败时**不抛异常**（截图失败不该阻断主流程），但会：

    1. 在 WARNING 级记录真实原因（不再静默吞掉）；
    2. 把原因存进 :func:`get_last_screenshot_error`，让通知正文能带上它；
    3. 路径基于**项目根**而非当前工作目录 —— cron 的工作目录未必是项目根。

    Args:
        operation_name: 操作名，会拼进文件名。

    Returns:
        str: 截图绝对路径；失败时返回空字符串。
    """
    global _last_screenshot_error

    directory = ""
    try:
        from project_paths import resolve_project_path

        log_dir = str(resolve_project_path("log"))
        directory = log_dir
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.join(log_dir, f"error_{operation_name}_{timestamp}.png")

        if not _has_connected_device():
            _last_screenshot_error = "没有已连接的设备（airtest 未初始化或模拟器掉线）"
            logger.warning(f"⚠️ 保存错误截图失败: {_last_screenshot_error}")
            return ""

        snapshot(filename=filename)

        if not os.path.isfile(filename) or os.path.getsize(filename) == 0:
            _last_screenshot_error = "截图文件未生成或为空（设备可能已掉线）"
            logger.warning(f"⚠️ 保存错误截图失败: {_last_screenshot_error}，目标路径 {filename}")
            return ""

        _last_screenshot_error = None
        logger.debug(f"📸 错误截图已保存: {filename}")
        return filename
    except Exception as e:
        _last_screenshot_error = f"{type(e).__name__}: {e}"
        logger.warning(
            f"⚠️ 保存错误截图失败: {_last_screenshot_error}"
            + (f"，目标目录 {directory}" if directory else "")
        )
        return ""


def open_map() -> None:
    """打开地图"""
    back_to_main()
    touch(MAP_BUTTON)
    logger.info("🗺️ 打开地图")
    sleep(2, "等待地图加载完毕")


def is_on_map() -> bool:
    """检查是否在地图界面"""
    return exists(MAP_DUNGEON_TEMPLATE)


def is_main_world() -> bool:
    """检查是否在主世界"""
    try:
        result = wait(GIFTS_TEMPLATE, timeout=0.3, interval=0.1)
        return bool(result)
    except Exception:
        return False


def is_on_character_selection(timeout: int = 30) -> bool:
    """检查是否在角色选择界面。

    超时前会持续轮询。截图/OCR 这类**临时异常不再被当成"不在角色选择界面"**：
    过去一律 ``except Exception -> return False``，导致一旦截图抖动（minicap 失败、
    adb 瞬时不可用）就立刻判定"未在角色选择界面"，进而触发整个流程重启游戏，
    形成"在选人界面反复杀游戏重启"的死循环。现在这类异常会被记录并继续重试。

    Args:
        timeout: 最长等待秒数。

    Returns:
        True 表示已进入角色选择界面；False 表示超时仍未进入。
    """
    logger.info("🔍 等待进入角色选择界面...")
    deadline = time.time() + max(1, timeout)
    transient_errors: List[str] = []

    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            wait(ENTER_GAME_BUTTON_TEMPLATE, timeout=remaining, interval=0.1)
            if transient_errors:
                logger.info(
                    f"✅ 已进入角色选择界面（期间出现过 {len(transient_errors)} 次截图/识别异常，已恢复）"
                )
            return True
        except TargetNotFoundError:
            # 真正的"整段时间都没找到"：正常判定为不在该界面
            break
        except Exception as e:
            transient_errors.append(f"{type(e).__name__}: {e}")
            logger.warning(f"⚠️ 检测角色选择界面时出现临时异常，继续重试: {type(e).__name__}: {e}")
            time.sleep(1)

    if transient_errors:
        logger.error(
            f"❌ {timeout}s 内未检测到角色选择界面，"
            f"期间出现 {len(transient_errors)} 次截图/识别异常，最后一次: {transient_errors[-1]}"
        )
    return False


def back_to_main(
    max_duration: float = 15,
    backoff_interval: float = 0.2,
    foreground_check_interval: int = 3,
) -> None:
    """返回主界面。

    实现方式是「点返回按钮 + 按系统返回键」直到检测到主界面。这种「按键硬轰」
    在弹窗层数不明时会把游戏一路退出到 Android 桌面（系统返回键在游戏的根界面
    就是「退出应用」），此后无论再按多少次都回不到主界面，只能空等到超时。
    因此这里每隔 ``foreground_check_interval`` 次尝试探测一次游戏是否还活着，
    一旦**明确**不在前台就立刻失败，把 15 秒的空转 + 后续连环超时掐断。

    Args:
        max_duration: 最长等待秒数。
        backoff_interval: 每次尝试之间的间隔秒数。
        foreground_check_interval: 每多少次尝试探测一次游戏是否仍在前台；
            设为 ``0`` 或负数表示关闭探测。

    Raises:
        GameNotForegroundError: 探测到游戏已不在前台。
        TimeoutError: 在 ``max_duration`` 秒内仍未检测到主界面。
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

        if foreground_check_interval > 0 and attempt % foreground_check_interval == 0:
            if is_game_foreground() is False:
                message = (
                    f"back_to_main 中止：游戏已不在前台（等待 {elapsed:.1f} 秒后探测到），"
                    "继续按返回键也不可能回到主界面，需要重启游戏进程"
                )
                logger.error(message)
                raise GameNotForegroundError(message)

        attempt += 1

        for _ in range(3):
            try:
                touch(BACK_BUTTON)
            except Exception as e:
                logger.warning(f"⚠️ 发送返回点击失败: {e}")
                break
            sleep(0.1)

        if attempt % 3 == 0:
            try:
                keyevent("BACK")
            except Exception as e:
                logger.warning(f"⚠️ 系统返回键发送失败: {e}")

        sleep(backoff_interval)


def switch_to_zone(zone_name: str, max_attempts: int = 3) -> bool:
    """切换到指定区域，最多重试 ``max_attempts`` 次。

    每次尝试前都会确认「地图已打开」。2026-09-25 实测：地图没能打开时，
    三次尝试全都在非地图界面上盲等 OCR 超时（每次约 20 秒、共白耗 60 秒），
    最终该副本被整轮跳过，还连带触发了一整轮重试。重开地图约 2.5 秒，
    成本远低于盲等，所以宁可多开一次地图。

    Args:
        zone_name: 目标区域名称。
        max_attempts: 最大尝试次数。

    Returns:
        bool: 是否成功切换到目标区域。
    """
    for attempt in range(max_attempts):
        logger.info(f"\n{'=' * 50}")
        logger.info(f"🌍 切换区域: {zone_name} (第 {attempt + 1}/{max_attempts} 次尝试)")
        logger.info(f"{ '=' * 50}")

        if not is_on_map():
            logger.warning("⚠️ 当前不在地图界面，重新打开地图后再试")
            open_map()

        if not find_text_and_click_safe("切换区域", timeout=10):
            logger.warning("⚠️ 未找到「切换区域」按钮（可能地图未打开或界面异常）")

        if find_text_and_click_safe(zone_name, timeout=10, occurrence=2):
            logger.info(f"✅ 成功切换到: {zone_name}")
            touch(CLOSE_ZONE_MENU)
            return True

        logger.error(f"❌ 切换失败: {zone_name} (第 {attempt + 1}/{max_attempts} 次)")

        if attempt < max_attempts - 1:
            logger.info("🔄 准备重试（下一轮会先确认地图已打开）")

    logger.error(f"❌ 切换区域失败，已重试 {max_attempts} 次: {zone_name}")
    save_error_screenshot("switch_to_zone")
    return False


def focus_and_click_dungeon(dungeon_name: str, zone_name: str, max_attempts: int = 2) -> bool:
    """尝试聚焦到指定副本并点击"""
    for attempt in range(max_attempts):
        use_cache = attempt == 0
        result = find_text_and_click_safe(
            dungeon_name,
            timeout=6,
            occurrence=LAST_OCCURRENCE,
            use_cache=use_cache,
        )
        if result:
            return True
        logger.warning(f"⚠️ 未能找到副本: {dungeon_name} (第 {attempt + 1}/{max_attempts} 次尝试)")
        if attempt < max_attempts - 1:
            logger.info("🔄 重新打开地图并刷新区域后再试")
            open_map()
            if not switch_to_zone(zone_name):
                logger.warning(f"⚠️ 刷新区域失败: {zone_name}")
                continue
            sleep(1)
    save_error_screenshot("focus_and_click_dungeon")
    return False
