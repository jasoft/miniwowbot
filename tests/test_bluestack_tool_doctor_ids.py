#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bluestack-tool.py doctor 子命令的实例选择测试。

锁定「诊断实例必须跟随 emulators.json」：单账号化后只保留 warrior
主账号，doctor 不能再硬编码拉起 ["1", "2"] 把已下线的多开实例
（mage_alt / Pie64_1 / 5565）拉起来。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent / "scripts" / "bluestack-tool.py"
spec = importlib.util.spec_from_file_location("bluestack_tool", _SCRIPT)
bluestack_tool = importlib.util.module_from_spec(spec)
sys.modules["bluestack_tool"] = bluestack_tool
spec.loader.exec_module(bluestack_tool)
bt = bluestack_tool


class TestResolveDoctorInstanceIds:
    """测试 resolve_doctor_instance_ids 的实例解析。"""

    def test_single_main_account_session(self) -> None:
        """只剩主账号会话时只诊断实例 1，绝不带上已下线的多开实例。"""
        sessions = [{"name": "main", "emulator": "192.168.1.150:5555"}]
        assert bt.resolve_doctor_instance_ids(sessions) == ["1"]

    def test_localhost_serial_form(self) -> None:
        """127.0.0.1 写法与 192.168.1.150 等价，同样识别为实例 1。"""
        sessions = [{"name": "main", "emulator": "127.0.0.1:5555"}]
        assert bt.resolve_doctor_instance_ids(sessions) == ["1"]

    def test_empty_sessions_falls_back_to_main(self) -> None:
        """配置缺失/为空时回退主实例，不再默认拉起多开实例。"""
        assert bt.resolve_doctor_instance_ids([]) == ["1"]

    def test_multi_instance_sessions_keep_order(self) -> None:
        """多开场景（如未来恢复小号）仍按 DEFAULT_INSTANCES 顺序解析。"""
        sessions = [
            {"name": "main", "emulator": "192.168.1.150:5555"},
            {"name": "alt", "emulator": "192.168.1.150:5565"},
        ]
        assert bt.resolve_doctor_instance_ids(sessions) == ["1", "2"]

    def test_unrelated_session_does_not_match(self) -> None:
        """会话地址与任何实例端口都对不上时回退主实例。"""
        sessions = [{"name": "x", "emulator": "10.0.0.9:9999"}]
        assert bt.resolve_doctor_instance_ids(sessions) == ["1"]


class TestCmdDoctorUsesConfiguredSessions:
    """锁住调用点：cmd_doctor 必须实际使用解析出的实例。

    只测 ``resolve_doctor_instance_ids`` 不够 —— 调用点换回硬编码
    ``["1", "2"]`` 时函数测试依然全绿。这里打桩 start/stop/adb，
    端到端断言 cmd_doctor 只拉起配置里的实例。
    """

    def _run_doctor(self, monkeypatch, tmp_path, sessions):
        """在 tmp_path 下放一份 emulators.json 并跑一次 cmd_doctor。"""
        import argparse
        import json
        from types import SimpleNamespace

        (tmp_path / "emulators.json").write_text(
            json.dumps({"sessions": sessions}), encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(bt, "resolve_adb_path", lambda _p: "adb")
        monkeypatch.setattr(bt, "resolve_bluestacks_player_path", lambda _p: "player")
        monkeypatch.setattr(
            bt.subprocess,
            "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="alive", stderr=""),
        )
        started: list[str] = []
        stopped: list[str] = []
        monkeypatch.setattr(bt, "cmd_start", lambda a: started.append(a.id) or bt.EXIT_OK)
        monkeypatch.setattr(bt, "cmd_stop", lambda a: stopped.append(a.id) or 0)
        args = argparse.Namespace(
            id=None,
            no_wait=False,
            no_stop=False,
            timeout=5,
            adb=None,
            player=None,
            format="table",
        )
        ret = bt.cmd_doctor(args)
        return ret, started, stopped

    def test_doctor_only_starts_configured_instance(self, monkeypatch, tmp_path) -> None:
        """只剩主账号会话时，doctor 只启动/停止实例 1。"""
        ret, started, stopped = self._run_doctor(
            monkeypatch,
            tmp_path,
            [{"name": "main", "emulator": "192.168.1.150:5555"}],
        )
        assert ret == bt.EXIT_OK
        assert started == ["1"], f"doctor 拉起的实例应为 ['1']，实际 {started}"
        assert stopped == ["1"]

    def test_doctor_falls_back_to_main_when_config_missing(self, monkeypatch, tmp_path) -> None:
        """emulators.json 缺失时也只诊断主实例，不碰多开实例。"""
        ret, started, stopped = self._run_doctor(monkeypatch, tmp_path, [])
        assert ret == bt.EXIT_OK
        assert started == ["1"]
        assert stopped == ["1"]
