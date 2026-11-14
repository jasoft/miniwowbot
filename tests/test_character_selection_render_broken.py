"""回归测试：等待角色选择界面时必须能识破「画面渲染不完整」。

背景（2026-11-13 06:05 那轮真机故障）：
    模拟器处于**关机**状态，06:05:47 起 ADB 连接重试，guest 06:06:00 才开始启动、
    06:06:09 才 ``Ready``，脚本 06:06:23 就启动了游戏。随后游戏渲染 surface 的**尺寸
    错乱**：屏幕上半 480px 纯黑（行均值 0.00），角色选择界面被压进下半 800px，整体
    垂直压缩到约 60%。

    关键点：**界面其实已经画出来了** —— 脚本自己落的
    ``error_character_selection_timeout_20261113_060923_836053.png`` 里，「选择角色」
    标题、8 个职业图标、法师 Lv.115、「进入游戏」按钮全都可读。但按钮的红色区域是
    **257x28**（宽高比 9.18），而模板 ``images/enter_game_button.png`` 是 **200x50**
    （宽高比 4.00）—— 形状被压扁，模板匹配最高只有 **0.37**，远低于阈值。

    于是 ``is_on_character_selection`` 整整盲等 180 秒（06:06:23→06:09:23），
    靠 ``main_wrapper`` 的「超时重启」重开游戏，06:09:32→06:09:48 **16 秒**就进去了。
    业务无损（mage 11/11、warrior 11/11），但白耗 3 分钟 + 一条误导性告警。

本文件锁死的不变量：
    1. 连续探测到「大片黑边」时必须**提前结束等待**（而不是烧满 timeout）；
    2. 提前结束时抛 ``ScreenRenderBrokenError``（继承 ``TimeoutError``，
       才能复用 ``main_wrapper`` 已有的「关游戏 → 开游戏」恢复路径）；
    3. 提前结束时必须落错误截图（否则下次又只能靠 Player.log 反推）；
    4. **"全黑"不得被当成"渲染坏了"** —— 全黑是还在加载，语义完全不同，
       误判会让正常的加载过程多挨一次重启。
    5. **启动后的加载宽限期内不得探测** —— 加载态同样是"半屏黑"，2026-11-14 实测
       3 次探测全假；余量薄到"加载再慢几秒就会误重启正常启动"。

反证设计（重要）：
    本文件所有对**新增符号**（常量 / 判据函数 / 异常类）的打桩都带 ``create=True``，
    取值也一律走 ``getattr`` 兜底 —— 否则在旧代码上会以
    ``AttributeError: ... does not have the attribute ...`` 失败，那是**机械失败**，
    只证明"符号不存在"，证明不了"行为缺失"（技能里记过这个坑）。
    新符号由 :func:`_require_render_probe` 显式断言，失败信息直接说明缺的是哪个行为。
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

import pytest
from airtest.core.error import TargetNotFoundError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon_navigation as nav  # noqa: E402

#: 旧代码里没有这个异常类。取 ``TimeoutError`` 兜底，让它「改前」的失败落在
#: ``DID NOT RAISE``（行为缺失）而不是 ``ImportError``/``AttributeError``（机械失败）。
ScreenRenderBrokenError = getattr(nav, "ScreenRenderBrokenError", TimeoutError)

#: 伪造的前台应用，证明日志确实带上了它。
FAKE_FOREGROUND = "com.ms.ysjyzr/org.cocos2dx.javascript.AppActivity"


class _NeverMatchWait:
    """伪造 airtest 的 ``wait``：永远找不到目标。

    必须抛**生产同款异常类型** ``airtest.core.error.TargetNotFoundError`` ——
    桩抛自定义异常会让「新分支是否可达」被错误地验证成真的
    （2026-10-01 就是被这个假测试骗过一次）。
    """

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        time.sleep(0.01)
        raise TargetNotFoundError("模拟：进入游戏按钮模板未命中")


def _require_render_probe():
    """取出「画面渲染不完整」判据函数。

    旧代码没有它时以 ``AssertionError`` 失败，失败信息直接点明缺的是哪个行为
    （而不是让 ``patch`` 抛 ``AttributeError`` —— 那属于机械失败）。
    """
    probe = getattr(nav, "screen_render_is_broken", None)
    assert probe is not None, "行为缺失：navigation 未提供「画面渲染不完整」判据"
    return probe


def _synthetic_screen(height: int, dark_rows: int, bright: int = 180):
    """构造一张合成灰度图：顶部 ``dark_rows`` 行全黑，其余为亮色。

    Args:
        height: 图像高度（像素）。
        dark_rows: 顶部黑行数。
        bright: 非黑区域亮度。

    Returns:
        numpy.ndarray: 单通道灰度二维数组。
    """
    import numpy as np

    image = np.full((height, 720), bright, dtype=np.uint8)
    if dark_rows > 0:
        image[:dark_rows, :] = 0
    return image


def _patched_environment(fake_wait, render_result, save_mock=None):
    """组装等待函数的测试环境。

    Args:
        fake_wait: 替换 ``wait`` 的桩。
        render_result: ``screen_render_is_broken`` 的返回值。
        save_mock: 需要断言时传入自己的 ``save_error_screenshot`` 桩；默认新建一个。

    Returns:
        list: ``patch.object`` 上下文管理器列表，调用方用 ``ExitStack`` 组合。
    """
    if save_mock is None:
        save_mock = patch.object(nav, "save_error_screenshot", return_value="", create=True)
    return [
        patch.object(nav, "wait", fake_wait),
        patch.object(nav, "CHARACTER_SELECTION_POLL_SLICE_SECONDS", 0.01),
        # 以下是新增符号：必须 create=True，才能让旧代码也跑起来。
        patch.object(nav, "SCREEN_BROKEN_CHECK_INTERVAL_SECONDS", 0.02, create=True),
        patch.object(nav, "SCREEN_BROKEN_LIMIT", 3, create=True),
        # 宽限期置 0 = 立刻开始探测，本文件其余用例都只关心「探测到之后」的行为。
        patch.object(nav, "SCREEN_BROKEN_GRACE_SECONDS", 0.0, create=True),
        patch.object(nav, "screen_render_is_broken", return_value=render_result, create=True),
        save_mock,
        patch.object(nav, "is_game_foreground", return_value=True),
        patch.object(nav, "describe_foreground", return_value=FAKE_FOREGROUND),
    ]


def test_render_broken_aborts_wait_early():
    """连续判为「渲染不完整」时必须提前结束等待，而不是烧满 timeout。

    改前：函数只会一路 ``wait`` 到 deadline，然后返回 ``False`` ——
    今天真机就是白等了 180 秒。改后：约 ``SCREEN_BROKEN_LIMIT`` 次探测后抛异常。

    失败点落在 ``pytest.raises`` 的 ``DID NOT RAISE``（行为缺失），非机械失败。
    """
    from contextlib import ExitStack

    fake_wait = _NeverMatchWait()
    with ExitStack() as stack:
        for ctx in _patched_environment(fake_wait, True):
            stack.enter_context(ctx)
        with pytest.raises(ScreenRenderBrokenError):
            nav.is_on_character_selection(timeout=5)

    # 机制断言：必须真的提前退出。改前会跑满 5 秒 / 0.01 秒切片 ≈ 数百次。
    assert (
        fake_wait.calls < 50
    ), f"未提前结束等待：wait 被调用 {fake_wait.calls} 次，说明仍然在盲等（改前行为）"


def test_render_broken_saves_error_screenshot():
    """提前结束等待时必须落一张错误截图，供事后定位。"""
    from contextlib import ExitStack

    with ExitStack() as stack:
        shot = stack.enter_context(
            patch.object(nav, "save_error_screenshot", return_value="", create=True)
        )
        for ctx in _patched_environment(_NeverMatchWait(), True, save_mock=shot):
            stack.enter_context(ctx)
        with pytest.raises(ScreenRenderBrokenError):
            nav.is_on_character_selection(timeout=5)

    shot.assert_called_once()
    operation = shot.call_args.args[0] if shot.call_args.args else ""
    assert (
        "render_broken" in operation
    ), f"错误截图的 operation 名应可定位到「渲染不完整」，实际为 {operation!r}"


def test_render_broken_none_does_not_abort():
    """探测返回 ``None``（无设备/截图失败）时不得触发任何恢复动作。

    与 ``is_game_foreground`` 的三态约定一致：诊断本身失败不该改变主流程，
    宁可退回「等满超时」的老行为。这是**不误杀**方向的守卫。
    """
    from contextlib import ExitStack

    with ExitStack() as stack:
        for ctx in _patched_environment(_NeverMatchWait(), None):
            stack.enter_context(ctx)
        result = nav.is_on_character_selection(timeout=1)

    assert result is False, "探测无法判定时应正常超时返回 False，而不是抛异常"


def test_screen_render_is_broken_detects_half_black_screen():
    """判据本体：上半屏全黑、下半屏正常 ⇒ 渲染不完整。

    尺寸按今天真机截图的真实比例构造（720x1280，上部 480 行黑，
    即 480/1280 = 37.5% 黑带）。
    """
    probe = _require_render_probe()
    shot = _synthetic_screen(height=1280, dark_rows=480)
    with patch.object(nav, "_snapshot_grayscale", return_value=shot, create=True):
        assert probe() is True


def test_screen_render_is_broken_ignores_full_black_frame():
    """全黑画面是「还在加载」，不是渲染错误 —— 必须返回 False。

    这条与上一条互为反向守卫：若把全黑也判成 True，正常的冷启动加载会被
    反复重启（比原来的盲等更糟）。
    """
    probe = _require_render_probe()
    shot = _synthetic_screen(height=1280, dark_rows=1280)
    with patch.object(nav, "_snapshot_grayscale", return_value=shot, create=True):
        assert probe() is False


def test_screen_render_is_broken_returns_none_without_frame():
    """拿不到截图时必须返回 ``None``（无法判定），不能猜。"""
    probe = _require_render_probe()
    with patch.object(nav, "_snapshot_grayscale", return_value=None, create=True):
        assert probe() is None


def test_screen_render_is_broken_accepts_normal_frame():
    """正常铺满的画面不得被误判。"""
    probe = _require_render_probe()
    shot = _synthetic_screen(height=1280, dark_rows=0)
    with patch.object(nav, "_snapshot_grayscale", return_value=shot, create=True):
        assert probe() is False


def test_render_probe_skipped_during_loading_grace():
    """游戏刚启动的加载宽限期内，不得做渲染判据探测。

    背景（2026-11-14 06:05 那轮）：11-13 新增的渲染判据当天共探测 3 次，**3 次全是
    假阳性**，且都落在「启动游戏」后 6~13 秒 —— 冷启动时 surface 还在按窗口尺寸重排，
    画面本来就可能"半屏黑"，随后自行恢复（+16 秒 / +26 秒进入角色选择）。真正危险的
    是余量：其中一次已连续判黑 2 次，加载再慢几秒就会凑满 ``SCREEN_BROKEN_LIMIT``，
    把**正常启动**当成渲染错乱去重启游戏。

    构造：宽限期 10 秒 > 超时 1 秒，整个等待期都在宽限期内；判据桩恒返回 ``True``。
    旧代码会在第一次探测后开始连续计数并提前抛异常 —— 本条用例即以
    ``pytest.fail`` 明确指出"加载期不该提前结束等待"（行为缺失，不是机械失败）。
    改后应当一次都不探测，正常超时返回 ``False``。
    """
    from contextlib import ExitStack
    from unittest.mock import MagicMock

    probe = MagicMock(return_value=True)
    with ExitStack() as stack:
        for ctx in _patched_environment(_NeverMatchWait(), True):
            stack.enter_context(ctx)
        # 后进先生效：这两条覆盖 _patched_environment 里的同名桩。
        stack.enter_context(patch.object(nav, "screen_render_is_broken", probe, create=True))
        stack.enter_context(patch.object(nav, "SCREEN_BROKEN_GRACE_SECONDS", 10.0, create=True))
        try:
            result = nav.is_on_character_selection(timeout=1)
        except ScreenRenderBrokenError as exc:
            pytest.fail(f"加载宽限期内不该判为渲染错乱并提前结束等待（旧行为）：{exc}")

    assert result is False, "宽限期跑满仍未命中时应正常超时返回 False"
    assert probe.call_count == 0, (
        f"加载宽限期内不应做渲染探测，实际探测了 {probe.call_count} 次"
        "（启动阶段的半屏黑是加载态，不是 surface 尺寸错乱）"
    )
    # 常量守护：宽限期 + 检测窗口仍须远小于编排器 180 秒的日志停滞阈值，
    # 否则"推迟探测"本身就会把发现真故障的时间顶到看门狗阈值之上。
    grace = getattr(nav, "SCREEN_BROKEN_GRACE_SECONDS", None)
    assert grace is not None, "行为缺失：navigation 未提供「加载宽限期」常量"
    total = grace + nav.SCREEN_BROKEN_LIMIT * nav.SCREEN_BROKEN_CHECK_INTERVAL_SECONDS
    assert total < 180, f"宽限期+检测窗口 {total} 秒不应逼近看门狗阈值 180 秒"


def test_render_check_constants_are_below_watchdog_threshold():
    """常量守护：检测窗口必须远小于编排器 180 秒的日志停滞阈值。

    否则「提前结束等待」本身就会变成新的看门狗误杀源。
    """
    interval = getattr(nav, "SCREEN_BROKEN_CHECK_INTERVAL_SECONDS", None)
    limit = getattr(nav, "SCREEN_BROKEN_LIMIT", None)
    ratio = getattr(nav, "SCREEN_BROKEN_DARK_BAND_RATIO", None)
    band_threshold = getattr(nav, "SCREEN_BROKEN_BAND_MEAN_THRESHOLD", None)
    band_count = getattr(nav, "SCREEN_BROKEN_BAND_COUNT", None)

    assert interval is not None and limit is not None, "行为缺失：渲染检测常量未定义"
    window = interval * limit
    assert window < 180, f"渲染检测窗口 {window} 秒不应逼近看门狗阈值 180 秒"
    assert 0 < ratio < 1
    assert 0 < band_threshold < 255
    assert band_count >= 4
