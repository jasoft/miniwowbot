"""回归测试：``ensure_connected`` 的重试日志不能自相矛盾。

历史问题：``adb connect`` 返回成功（日志已打「[ADB] 已连接」）但设备的
``adb devices`` 状态还不是 ``device``（冷启动未就绪）时，分支里统一记成
「连接失败，尝试启动模拟器...」。两行日志互相打架，排查时会被误读成
「模拟器被启动了两次」（10-18 / 10-21 两次体检都踩到）。

修复后：按 ``connect()`` 的真实返回值区分两种文案，启动命令的调用行为不变。
"""

from unittest.mock import patch

from emulator_manager import EmulatorConnectionManager


class _Recorder:
    """最小 logger 替身，只记录 info 级别消息。"""

    def __init__(self):
        self.messages = []

    def info(self, message, *args, **kwargs):
        self.messages.append(str(message))

    def warning(self, message, *args, **kwargs):
        self.messages.append(str(message))

    def error(self, message, *args, **kwargs):
        self.messages.append(str(message))

    def debug(self, message, *args, **kwargs):
        self.messages.append(str(message))

    def text(self) -> str:
        return "\n".join(self.messages)


def _build_manager(recorder: _Recorder) -> EmulatorConnectionManager:
    manager = EmulatorConnectionManager(start_cmd="start.cmd")
    manager.logger = recorder
    return manager


@patch("time.sleep")
def test_connect_ok_but_state_not_ready_does_not_say_connect_failed(_mock_sleep):
    """connect 成功、设备状态未就绪时，不应记「连接失败」。"""
    recorder = _Recorder()
    manager = _build_manager(recorder)

    with (
        patch.object(manager, "is_connected", return_value=False),
        patch.object(manager, "connect", return_value=True) as mock_connect,
        patch.object(manager, "_run_start_cmd", return_value=True) as mock_start,
    ):
        result = manager.ensure_connected("192.168.1.150:5555", max_retries=3)

    assert result is False
    text = recorder.text()
    assert "adb connect 成功但设备状态未就绪" in text
    assert "连接失败，尝试启动模拟器" not in text
    # 行为未变：仍然每个重试周期执行一次幂等启动命令
    assert mock_connect.call_count == 3
    assert mock_start.call_count == 2


@patch("time.sleep")
def test_connect_failed_keeps_connect_failed_message(_mock_sleep):
    """connect 真失败时，仍应记「连接失败，尝试启动模拟器」。"""
    recorder = _Recorder()
    manager = _build_manager(recorder)

    with (
        patch.object(manager, "is_connected", return_value=False),
        patch.object(manager, "connect", return_value=False),
        patch.object(manager, "_run_start_cmd", return_value=True),
    ):
        result = manager.ensure_connected("192.168.1.150:5555", max_retries=2)

    assert result is False
    assert "连接失败，尝试启动模拟器" in recorder.text()
