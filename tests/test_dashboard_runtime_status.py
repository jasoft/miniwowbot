# -*- encoding=utf8 -*-

from __future__ import annotations

import os
import tempfile

from dashboard_runtime_status import (
    parse_adb_devices_output,
    parse_log_status,
    read_last_n_lines,
)


def test_parse_adb_devices_output_only_device_state():
    out = """List of devices attached
emulator-5554\tdevice
emulator-5556\toffline
127.0.0.1:5555\tdevice
"""
    devices = parse_adb_devices_output(out)
    assert "emulator-5554" in devices
    assert "127.0.0.1:5555" in devices
    assert "emulator-5556" not in devices


def test_parse_log_status_progress_and_complete_and_config():
    log = """
2026-02-07 08:00:00 INFO 🎮 当前配置: mage_main
2026-02-07 08:01:00 INFO 🎯 [1/5] 处理副本: 影牙城堡
2026-02-07 08:05:00 INFO ✅ 完成: 影牙城堡
2026-02-07 08:06:00 INFO 🎯 [2/5] 处理副本: 暴风城监狱
""".strip()

    status = parse_log_status(log)
    assert status.current_config == "mage_main"
    assert status.current_dungeon == "暴风城监狱"
    assert status.progress == "2/5"
    assert status.last_completed == "影牙城堡"
    assert status.has_error is False


def test_parse_log_status_error_flag():
    log = """
INFO Starting...
ERROR Something went wrong
INFO Still running
""".strip()
    status = parse_log_status(log)
    assert status.has_error is True


def test_read_last_n_lines_real_file():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            for i in range(10):
                fh.write(f"line{i}\n")

        text = read_last_n_lines(path, n=3)
        assert text == "line7\nline8\nline9"

        text_all = read_last_n_lines(path, n=30)
        assert len(text_all.splitlines()) == 10
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
