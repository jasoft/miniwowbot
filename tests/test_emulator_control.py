"""emulator_control 模块单元测试。"""

from __future__ import annotations

from emulator_control import match_mumu_vm_index, parse_emulator_port, parse_mumu_info_output


def test_parse_emulator_port_supports_airtest_style() -> None:
    """验证 Airtest 连接串也能正确提取端口。"""
    emulator = "Android://127.0.0.1:5037/192.168.1.150:5565"
    assert parse_emulator_port(emulator) == 5565


def test_parse_mumu_info_output_from_embedded_json() -> None:
    """验证带前后噪声的 MuMu 输出可解析。"""
    raw_text = """
    some logs...
    [
      {"index": "0", "adb_port": 5555},
      {"index": "1", "adb_port": 5565}
    ]
    done
    """
    parsed = parse_mumu_info_output(raw_text)
    assert len(parsed) == 2
    assert parsed[0]["index"] == "0"
    assert parsed[1]["adb_port"] == 5565


def test_match_mumu_vm_index_by_emulator_port() -> None:
    """验证可按端口把模拟器地址匹配到 MuMu 实例索引。"""
    instances = [
        {"index": "0", "adb_port": 5555},
        {"index": "1", "adb_port": 5565},
    ]
    assert match_mumu_vm_index(instances, "192.168.1.150:5565") == "1"

