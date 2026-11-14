"""
auto_dungeon 导航模块
"""

import logging
import os
import tempfile
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

#: 等待角色选择界面时的心跳间隔（秒）。必须显著小于编排器的日志停滞阈值
#: （cron_run_all_dungeons.LOG_IDLE_TIMEOUT_SECONDS = 180），否则看门狗会把
#: 「正在正常等待游戏启动」的会话判成僵死，连模拟器一起杀掉重启。
CHARACTER_SELECTION_HEARTBEAT_SECONDS = 30

#: 等待角色选择界面时，单次 ``wait`` 的轮询切片（秒）。
#:
#: airtest 的 ``wait(template, timeout=T)`` 会在 T 秒内**整段阻塞**，中途既不打日志
#: 也不会回到调用方。若把整个超时一次性交给它（``timeout=remaining``），等待期间
#: 日志文件零增长，而编排器 ``cron_run_all_dungeons`` 把会话日志的 ``(mtime, size)``
#: 当作「会话是否还活着」的**唯一**信号 —— 超过 ``LOG_IDLE_TIMEOUT_SECONDS``(180 秒)
#: 就判定僵死，杀掉会话并重启模拟器。
#:
#: 2026-10-01 06:06:22.264 实测：静默 **180.07 秒**后由本函数自己超时，与阈值擦边，
#: 纯属侥幸没被看门狗选中；当天会话日志里 ``等待角色选择界面中...`` 出现 **0 次**，
#: 即"心跳代码存在但永远执行不到"。切成小片后每片返回一次，心跳才有机会落盘。
CHARACTER_SELECTION_POLL_SLICE_SECONDS = 1.0

#: 等待角色选择界面时，探测「游戏是否仍在前台」的间隔（秒）。
CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS = 5.0

#: 连续多少次「明确探测到游戏不在前台」就提前结束等待。
#:
#: 2026-10-10 06:05~06:35 实测（法师小号实例 Pie64_1，已下线）：游戏进程每次都被正常拉起
#: （``Player.log`` 里 ``com.ms.ysjyzr`` 的 socket 一次不落），但顶层 Activity 反复
#: 被 BlueStacks launcher 夺回 —— 当天该实例 **20 次**前台切换（对照 main 仅 2 次）、
#: **6 次** SystemUI 重启（对照 main 0 次），且每次 launcher 前台的 ``callingPackage``
#: 都是预装的应用宝 ``com.tencent.android.qqdownloader``。本函数当时只会一路盲等到
#: 180 秒超时：9 次超时白耗约 27 分钟，并把一次**实例异常**放大成
#: 「3 次配置重试 × 3 次应用重启 = 9 条告警」，直到编排器重启该实例才在 1 分钟内恢复。
#:
#: 取 4 次（约 20 秒）而不是 1 次，是为了不和真实的画面过渡打架：实测健康轮次里
#: ``start_app`` 后约 5~6 秒游戏才把 Activity 显示到前台。
CHARACTER_SELECTION_FOREGROUND_LOST_LIMIT = 4

#: 判定「画面未铺满整屏」时，**黑带**（整行几乎全黑）占全屏横带的比例阈值。
#:
#: 2026-11-13 06:06~06:09 实测：模拟器冷启动（guest 06:06:00 才开始启动、06:06:09
#: 才 ``Ready``），脚本 06:06:23 就启动了游戏。随后游戏渲染 surface 的**尺寸错乱**：
#: 屏幕上半 480px 纯黑（行均值 0.00），角色选择界面被压进下半 800px，画面整体
#: 垂直压缩到约 60%。脚本自己落下的错误截图里，那一屏的「进入游戏」按钮红色区域
#: 是 **257x28**（宽高比 9.18），而模板 ``images/enter_game_button.png`` 是
#: **200x50**（宽高比 4.00）—— 形状被压扁，模板匹配最高只有 **0.37**，远低于阈值，
#: 于是 180 秒都不命中，白耗 3 分钟后靠「超时重启」重开游戏才在 16 秒进入界面。
#:
#: 这类"画面没铺满屏幕"与"全黑"是**两种不同的东西**：全黑 = 还在加载，值得再等
#: （见 :data:`BLANK_SCREEN_MEAN_THRESHOLD`）；**半屏黑 = 渲染尺寸已经错了，等多久
#: 都不会自己变好**，唯一有效的恢复是重开游戏。
SCREEN_BROKEN_DARK_BAND_RATIO = 0.30

#: 单条横带被视为「黑带」的平均亮度阈值（0~255）。
SCREEN_BROKEN_BAND_MEAN_THRESHOLD = 8.0

#: 把屏幕沿纵向切成多少条横带做统计。
SCREEN_BROKEN_BAND_COUNT = 16

#: 连续多少次探测到「画面渲染不完整」才提前结束等待。
#:
#: 取 4 次（配合 5 秒间隔约 20 秒）：既要压住"游戏正在切换场景、某一帧刚好是黑边"
#: 的瞬态，又要比 180 秒的盲等快一个数量级。2026-11-13 的异常状态持续了整整
#: 180 秒（重启游戏后 16 秒即正常），20 秒足以抓住它。
SCREEN_BROKEN_LIMIT = 4

#: 等待角色选择界面时，探测「画面是否铺满整屏」的间隔（秒）。
SCREEN_BROKEN_CHECK_INTERVAL_SECONDS = 5.0

#: 刚进入「等待角色选择界面」后的**加载宽限期**（秒），期内不做渲染判据探测。
#:
#: 2026-11-14 实测：本函数共探测 3 次「画面渲染不完整」，**3 次全是假的**，且全部落在
#: 「启动游戏」后 6~13 秒内 —— 06:07:23 启动、06:07:32 与 06:07:36 连续两次判黑，
#: 06:07:49（+26 秒）模板命中；06:24:30 启动、06:24:36 判黑一次，06:24:45（+16 秒）
#: 命中。两次都没有重启游戏，`render_broken_streak` 被随后的 ``False`` 清零。
#:
#: 机理：游戏刚被拉起时渲染 surface 还没按实际窗口尺寸铺开（冷启动时要等 guest
#: 把窗口尺寸回调打完），这一阶段**不是全黑**（splash / loading 图有内容），于是
#: 被判据当成"半屏黑 = surface 尺寸错乱"。也就是说 :func:`screen_render_is_broken`
#: 在启动阶段**无法区分「还在铺画面」与「尺寸真的错了」** —— 而后者恰恰是它唯一
#: 该管的事（2026-11-13 那次的特征是该状态持续了整整 180 秒）。
#:
#: 危险性在于余量太薄：今天两次启动分别在 **+16 秒 / +26 秒** 才进角色选择，其中
#: 一次已连续判黑 2 次；只要加载再慢几秒就会凑满 ``SCREEN_BROKEN_LIMIT``（4 次），
#: 把**正常启动**当成渲染错乱去重启游戏 —— 这正是判据本身要防的反向误杀。
#:
#: 取 20 秒的依据：实测"判黑窗口"结束于启动后 14~17 秒，取 20 秒把正常加载整段
#: 排除在外，同时把 2026-11-13 那类真故障的发现时间从 180 秒压到约 20+15=35 秒
#: （远小于编排器 180 秒的日志停滞阈值，不会招来看门狗）。
SCREEN_BROKEN_GRACE_SECONDS = 20.0

#: 最近一次截图失败的原因，供通知正文引用（``None`` 表示最近一次成功）
_last_screenshot_error: str | None = None


class GameNotForegroundError(TimeoutError):
    """游戏已不在前台，继续等待主界面没有意义。

    继承 :class:`TimeoutError` 是为了**复用** ``main_wrapper`` 已有的恢复路径：
    一旦探测到游戏被切到后台或已退出，唯一有效的恢复手段就是重新走一遍
    「关闭游戏 → 启动游戏 → 等角色选择界面」，而这恰好是 ``main_wrapper``
    捕获 :class:`TimeoutError` 后做的事。
    """


class ScreenRenderBrokenError(TimeoutError):
    """画面渲染不完整（大片黑边 / 画面被压扁），继续等待不可能自愈。

    与 :class:`GameNotForegroundError` 同理继承 :class:`TimeoutError`，以便**复用**
    ``main_wrapper`` 已有的「关闭游戏 → 启动游戏 → 等角色选择界面」恢复路径：
    渲染 surface 尺寸错了，只有重开游戏（重建 surface）才会恢复。

    判据见 :data:`SCREEN_BROKEN_DARK_BAND_RATIO`。
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


def describe_foreground() -> str:
    """返回当前前台应用的 ``包名/Activity`` 描述，用于诊断「游戏卡在哪个画面」。

    与 :func:`is_game_foreground` 共用 ``get_top_activity`` 探测，区别是它**永不抛异常**
    且返回可读字符串而不是三态布尔 —— 唯一用途是写进等待超时的日志里，供事后定位。

    为什么需要它：2026-10-01 06:06~06:35 法师小号实例（已下线）连续 9 次「启动游戏后 180 秒内未
    进入角色选择界面」，但脚本侧**没有任何画面信息**，只能靠 BlueStacks 的 Player.log
    反推"游戏一直停在同一画面"。把前台应用记进日志后，下次一眼就能看出卡在哪。

    Returns:
        str: 形如 ``com.ms.ysjyzr/org.cocos2dx.javascript.AppActivity``；
        无法判定时返回 ``unknown`` 或 ``unknown(<异常类型>)``。
    """
    try:
        from airtest.core.api import G

        device = getattr(G, "DEVICE", None)
        if device is None:
            return "unknown"
        top = device.get_top_activity()
    except Exception as e:  # noqa: BLE001 - 纯诊断，任何异常都不该影响主流程
        return f"unknown({type(e).__name__})"

    if not top:
        return "unknown"
    if isinstance(top, (tuple, list)):
        return "/".join(str(part) for part in top if part)
    return str(top)


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


#: 判定「画面全黑」的平均亮度阈值（0~255）。
#:
#: 2026-10-08 06:06 实测：法师小号实例（已下线）冷启动时，游戏在「判定已进入角色选择界面」
#: 与「OCR 查找职业」之间发生了场景切换（模拟器广告退出 + 音频停止 + 转屏，
#: Player.log 显示 06:06:50.023 ``SplitAdsExitComplete``、06:06:52.688
#: ``PlaybackStopped``、06:06:55.020 ``hcallOnOrientationChangedClbk``）。这 3~5 秒内
#: airtest 截图整幅几乎全黑 —— 对脚本自己落下的错误截图做离线像素分析：除顶部
#: 调试条外 **99.99% 的像素是 RGB(0,0,0)**，通道均值 0.18。OCR 自然读不到任何文字，
#: 于是被误报成「未找到职业: 法师」，进而把整个配置炸掉重跑一轮（约 1 分钟）。
#:
#: 黑屏的含义是 **"画面还没渲染出来"**，而不是 **"画面上没有这个文字"** ——
#: 两者该走完全不同的处理路径（前者等待恢复，后者才该放弃）。
BLANK_SCREEN_MEAN_THRESHOLD = 8.0


def _snapshot_grayscale():
    """截图并返回灰度像素数组。

    刻意复用 ``snapshot(filename=...)`` + PIL 这条**已验证可用**的截图链路
    （与 :func:`save_error_screenshot` 一致），而不是 ``device.snapshot()`` 的数组
    返回值 —— 后者在不同 airtest / 模拟器组合下返回类型并不统一。临时文件用完即删。

    任何异常都返回 ``None``：本函数只服务**辅助判据**，不能因为诊断本身失败而
    改变主流程行为。

    Returns:
        numpy.ndarray | None: 灰度二维数组；无设备、截图失败或解析失败时返回 ``None``。
    """
    if not _has_connected_device():
        return None

    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        snapshot(filename=tmp_path)

        if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) == 0:
            return None

        from PIL import Image
        import numpy as np

        with Image.open(tmp_path).convert("L") as image:
            return np.asarray(image, dtype=np.uint8).copy()
    except Exception as e:  # noqa: BLE001 - 纯辅助判据，任何异常都不该影响主流程
        logger.debug(f"灰度截图失败（按无法判定处理）: {type(e).__name__}: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:  # pragma: no cover - 清理失败无需处理
                pass


def screenshot_is_blank(threshold: float = BLANK_SCREEN_MEAN_THRESHOLD) -> bool:
    """判断当前画面是否几乎全黑（游戏正在切换场景 / 加载 / 广告过渡）。

    动机见 :data:`BLANK_SCREEN_MEAN_THRESHOLD`：黑屏时 OCR 必然读不到任何文字，
    调用方若把它当成"目标文字不存在"，就会误判并触发不必要的重量级恢复。

    任何异常都按「不是黑屏」处理（返回 ``False``）：本函数只是**辅助判据**，
    不能因为诊断本身失败而改变主流程行为。

    Args:
        threshold: 平均亮度阈值（0~255），画面均值低于它即判为全黑。

    Returns:
        bool: 画面几乎全黑返回 ``True``；画面正常或无法判定返回 ``False``。
    """
    pixels = _snapshot_grayscale()
    if pixels is None:
        return False

    mean_brightness = float(pixels.mean())
    if mean_brightness < threshold:
        logger.debug(f"🌑 检测到黑屏帧（平均亮度 {mean_brightness:.2f} < {threshold}）")
        return True
    return False


def screen_render_is_broken(
    dark_band_ratio_threshold: float = SCREEN_BROKEN_DARK_BAND_RATIO,
) -> bool | None:
    """判断当前画面是否「渲染不完整」—— 大片黑边、画面被压扁。

    为什么需要它：2026-11-13 06:06~06:09，角色选择界面**其实已经画出来了**
    （错误截图里"选择角色"标题、8 个职业图标、"进入游戏"按钮全都可读），但
    上半屏 480px 是纯黑、界面被压进下半 800px，整体垂直压缩到约 60%。于是
    「进入游戏」按钮的红色区域变成 257x28（宽高比 9.18），与模板的 200x50
    （宽高比 4.00）对不上，模板匹配最高只有 0.37 —— ``wait`` 整整 180 秒都不命中。
    脚本当时对"画面已经坏了"毫无感知，只能盲等超时。

    判据设计（与"全黑"严格区分）：

    * 整屏平均亮度低于 :data:`BLANK_SCREEN_MEAN_THRESHOLD` ⇒ 这是**还在加载**，
      返回 ``False``，交给调用方继续等（不该当成渲染错误）。
    * 否则把屏幕纵向切成 :data:`SCREEN_BROKEN_BAND_COUNT` 条横带，统计平均亮度
      低于 :data:`SCREEN_BROKEN_BAND_MEAN_THRESHOLD` 的横带占比；达到
      ``dark_band_ratio_threshold`` 即判为渲染不完整。

    三态返回与 :func:`is_game_foreground` 一致：只有**明确**判出错才返回 ``True``，
    无法判定（无设备 / 截图失败）一律 ``None``，调用方不得把 ``None`` 当 ``True``。

    Args:
        dark_band_ratio_threshold: 黑带占比阈值，达到即判为渲染不完整。

    Returns:
        bool | None: ``True`` 渲染不完整；``False`` 画面正常（含"全黑加载中"）；
        ``None`` 无法判定。
    """
    pixels = _snapshot_grayscale()
    if pixels is None:
        return None

    mean_brightness = float(pixels.mean())
    if mean_brightness < BLANK_SCREEN_MEAN_THRESHOLD:
        # 全黑 = 还在加载，语义上不是"渲染坏了"，交给原有超时逻辑。
        return False

    height = pixels.shape[0]
    band_height = height // SCREEN_BROKEN_BAND_COUNT
    if band_height < 1:
        return None

    dark_bands = 0
    for index in range(SCREEN_BROKEN_BAND_COUNT):
        band = pixels[index * band_height : (index + 1) * band_height]
        if float(band.mean()) < SCREEN_BROKEN_BAND_MEAN_THRESHOLD:
            dark_bands += 1

    ratio = dark_bands / SCREEN_BROKEN_BAND_COUNT
    if ratio >= dark_band_ratio_threshold:
        logger.debug(
            f"🖼️ 画面渲染不完整：黑带 {dark_bands}/{SCREEN_BROKEN_BAND_COUNT} "
            f"（{ratio:.0%}），整屏均值 {mean_brightness:.1f}"
        )
        return True
    return False


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

    等待被切成 ``CHARACTER_SELECTION_POLL_SLICE_SECONDS`` 秒的小片，每片结束后回到
    本函数检查是否已超时、并按 ``CHARACTER_SELECTION_HEARTBEAT_SECONDS`` 打心跳 ——
    详见该常量的说明。**不要**改回 ``wait(timeout=remaining)``：那会让整段等待静默，
    并把阻塞上限顶到看门狗阈值之上。

    等待期间还会按 ``CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS`` 探测游戏
    是否仍在前台：**曾经看到过游戏在前台、随后又连续 ``CHARACTER_SELECTION_FOREGROUND_LOST_LIMIT``
    次明确探测到它不在前台**时，直接抛 :class:`GameNotForegroundError` 提前结束等待 ——
    此时角色选择界面不可能出现，盲等 180 秒纯属浪费（2026-10-10 实测白耗约 27 分钟）。

    另按 ``SCREEN_BROKEN_CHECK_INTERVAL_SECONDS`` 探测**画面是否铺满整屏**：连续
    ``SCREEN_BROKEN_LIMIT`` 次判为"大片黑边 / 画面被压扁"时抛
    :class:`ScreenRenderBrokenError`。2026-11-13 06:06~06:09 实测：界面其实已经画出来了，
    但渲染 surface 尺寸错乱（上半屏 480px 纯黑、画面垂直压缩到约 60%），「进入游戏」
    按钮形状变形导致模板匹配最高只有 0.37，脚本盲等满 180 秒才靠超时重启恢复。
    首次探测推迟到 ``SCREEN_BROKEN_GRACE_SECONDS`` 之后 —— 游戏刚启动的加载阶段
    surface 还没铺开，此时判"渲染错乱"是假阳性（2026-11-14 实测 3 次全假）。

    超时未命中时会落一张错误截图（并记录超时瞬间的前台应用），让"游戏卡在哪个画面"
    有据可查，而不是只能靠模拟器日志反推。

    Args:
        timeout: 最长等待秒数。

    Returns:
        True 表示已进入角色选择界面；False 表示超时仍未进入。

    Raises:
        GameNotForegroundError: 游戏曾被看到在前台、之后又明确被顶到后台（继承
            ``TimeoutError``，会走 ``main_wrapper`` 已有的「重启游戏」恢复路径）。
        ScreenRenderBrokenError: 画面渲染不完整（大片黑边），继续等待不可能自愈
            （同样继承 ``TimeoutError``，复用同一条恢复路径）。
    """
    logger.info(f"🔍 等待进入角色选择界面...(最长 {timeout} 秒)")
    start_time = time.time()
    deadline = start_time + max(1, timeout)
    transient_errors: List[str] = []
    last_heartbeat = start_time
    last_foreground_check = start_time
    last_render_check = start_time
    seen_game_foreground = False
    foreground_lost_streak = 0
    render_broken_streak = 0

    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            wait(
                ENTER_GAME_BUTTON_TEMPLATE,
                timeout=min(remaining, CHARACTER_SELECTION_POLL_SLICE_SECONDS),
                interval=0.1,
            )
            if transient_errors:
                logger.info(
                    f"✅ 已进入角色选择界面（期间出现过 {len(transient_errors)} 次截图/识别异常，已恢复）"
                )
            return True
        except TargetNotFoundError:
            # 这一小片没命中只说明"还没进界面"，继续下一片；整体是否超时由 deadline 判定。
            # 注意：这里**不能** break —— airtest 的 wait 在整段找不到目标时抛的就是本异常，
            # 一旦 break，循环下方的超时日志与心跳将永远执行不到（2026-10-01 实测）。
            pass
        except Exception as e:
            transient_errors.append(f"{type(e).__name__}: {e}")
            logger.warning(f"⚠️ 检测角色选择界面时出现临时异常，继续重试: {type(e).__name__}: {e}")
            time.sleep(1)

        # 心跳：wait() 每片只阻塞一小段，这里按期留痕。编排器把「日志文件 180 秒
        # 无更新」当作会话僵死的唯一信号，漏打心跳会让正常等待被误杀。
        now = time.time()
        if now - last_heartbeat >= CHARACTER_SELECTION_HEARTBEAT_SECONDS:
            last_heartbeat = now
            logger.info(f"🔍 等待角色选择界面中...（已等待 {now - start_time:.0f} 秒）")

        # 前台感知：游戏「曾经在过前台」之后又被别的应用顶掉时，继续盲等毫无意义 ——
        # 角色选择界面不可能出现，唯一有效的恢复是重走「关游戏 → 开游戏」，而那正是
        # main_wrapper 捕获 TimeoutError 后做的事。这里直接抛 GameNotForegroundError
        # 复用该路径，把 180 秒的盲等压缩到约 20 秒。
        #
        # 必须先「见过游戏在前台」：刚 start_app 的几秒内顶层 Activity 还是 launcher
        # （真机实测约 5~6 秒），一上来就判「不在前台」会把**正常启动**也误杀。
        # ``None`` 不计数：探测本身失败（无设备 / get_top_activity 抖动）不该触发任何
        # 恢复动作，宁可按老行为等满超时。
        if now - last_foreground_check >= CHARACTER_SELECTION_FOREGROUND_CHECK_INTERVAL_SECONDS:
            last_foreground_check = now
            state = is_game_foreground()
            if state is True:
                seen_game_foreground = True
                foreground_lost_streak = 0
            elif state is False and seen_game_foreground:
                foreground_lost_streak += 1
                if foreground_lost_streak >= CHARACTER_SELECTION_FOREGROUND_LOST_LIMIT:
                    message = (
                        f"游戏已被顶到后台：连续 {foreground_lost_streak} 次探测都显示游戏不在前台"
                        f"（当前前台: {describe_foreground()}），继续等待不可能出现角色选择界面，"
                        "提前结束等待以复用「超时 → 重启游戏」的恢复路径"
                    )
                    logger.error(f"❌ {message}")
                    save_error_screenshot("character_selection_foreground_lost")
                    raise GameNotForegroundError(message)

        # 渲染感知：前台是对的，但**画面本身没铺满屏幕**（大片黑边 / 整体被压扁）时，
        # 模板永远匹配不上 —— 等多久都不会自己变好，因为渲染 surface 的尺寸已经错了。
        # 2026-11-13 实测：界面内容全都画出来了，仅因上半屏 480px 纯黑、画面垂直压缩到
        # 约 60%，「进入游戏」按钮从 200x50 变成 257x28，模板匹配最高 0.37，盲等 180 秒。
        # 这里同样复用「超时 → 重启游戏」的恢复路径（重开游戏会重建 surface）。
        #
        # 前 ``SCREEN_BROKEN_GRACE_SECONDS`` 秒**不做探测**：游戏刚被拉起时 surface 还在
        # 按窗口尺寸重排，这一阶段画面本来就可能"半屏黑"，此时判"渲染错乱"是假阳性
        # （2026-11-14 实测 3 次探测全假，均在启动后 6~13 秒内，随后自行恢复）。
        #
        # ``None``（无设备 / 截图失败）不计数也不清零：诊断本身失败时不该改变任何行为。
        if now - start_time >= SCREEN_BROKEN_GRACE_SECONDS:
            if now - last_render_check >= SCREEN_BROKEN_CHECK_INTERVAL_SECONDS:
                last_render_check = now
                broken = screen_render_is_broken()
                if broken is True:
                    render_broken_streak += 1
                    logger.warning(
                        f"⚠️ 画面渲染不完整（第 {render_broken_streak}/{SCREEN_BROKEN_LIMIT} 次探测），"
                        f"前台: {describe_foreground()}"
                    )
                    if render_broken_streak >= SCREEN_BROKEN_LIMIT:
                        message = (
                            f"画面渲染不完整：连续 {render_broken_streak} 次探测都发现大片黑边 / "
                            "画面被压扁（渲染 surface 尺寸错乱），模板匹配不可能命中，"
                            "提前结束等待以复用「超时 → 重启游戏」的恢复路径"
                        )
                        logger.error(f"❌ {message}")
                        save_error_screenshot("character_selection_render_broken")
                        raise ScreenRenderBrokenError(message)
                elif broken is False:
                    render_broken_streak = 0

    detail = ""
    if transient_errors:
        detail = (
            f"，期间出现 {len(transient_errors)} 次截图/识别异常，最后一次: {transient_errors[-1]}"
        )
    logger.error(
        f"❌ {timeout}s 内未检测到角色选择界面{detail}；" f"超时瞬间前台: {describe_foreground()}"
    )
    save_error_screenshot("character_selection_timeout")
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
