#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 Airtest 设备 URI 解析工具
"""

from tests.airtest_device_utils import (
    DEFAULT_AIRTEST_DEVICE_URI,
    build_airtest_device_uri_from_emulator,
    resolve_airtest_device_uri,
)


class TestBuildAirtestDeviceUriFromEmulator:
    def test_blank_returns_default(self):
        assert build_airtest_device_uri_from_emulator("   ") == DEFAULT_AIRTEST_DEVICE_URI

    def test_adb_serial_is_wrapped(self):
        assert build_airtest_device_uri_from_emulator("emulator-5554") == "Android:///emulator-5554"

    def test_host_port_is_wrapped(self):
        assert build_airtest_device_uri_from_emulator("127.0.0.1:5565") == "Android:///127.0.0.1:5565"

    def test_full_uri_is_passthrough(self):
        assert (
            build_airtest_device_uri_from_emulator("Android:///127.0.0.1:5555")
            == "Android:///127.0.0.1:5555"
        )


class TestResolveAirtestDeviceUri:
    def test_default(self):
        assert resolve_airtest_device_uri(env={}) == DEFAULT_AIRTEST_DEVICE_URI

    def test_device_uri_option_has_highest_priority(self):
        uri = resolve_airtest_device_uri(
            device_uri_opt=" Android:///emulator-1 ",
            emulator_opt="127.0.0.1:5555",
            env={
                "MINIWOW_DEVICE_URI": "Android:///from-env",
                "MINIWOW_EMULATOR": "127.0.0.1:5565",
            },
        )
        assert uri == "Android:///emulator-1"

    def test_emulator_option_builds_uri(self):
        uri = resolve_airtest_device_uri(
            device_uri_opt=None,
            emulator_opt="127.0.0.1:5565",
            env={},
        )
        assert uri == "Android:///127.0.0.1:5565"

    def test_env_device_uri(self):
        uri = resolve_airtest_device_uri(env={"MINIWOW_DEVICE_URI": "Android:///emulator-5556"})
        assert uri == "Android:///emulator-5556"

    def test_env_emulator_fallback(self):
        uri = resolve_airtest_device_uri(env={"MINIWOW_EMULATOR": "127.0.0.1:5585"})
        assert uri == "Android:///127.0.0.1:5585"

    def test_blank_env_is_ignored(self):
        uri = resolve_airtest_device_uri(env={"MINIWOW_DEVICE_URI": "   ", "MINIWOW_EMULATOR": "  "})
        assert uri == DEFAULT_AIRTEST_DEVICE_URI

