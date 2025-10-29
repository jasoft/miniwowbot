from airtest.core.api import sleep, touch, connect_device, auto_setup, device
import argparse


def test_multi_emu(emu_name):
    """测试多设备同时连接"""
    # 连接第一个模拟器
    auto_setup(__file__)
    connect_device(f"Android://127.0.0.1:5037/{emu_name}")
    while True:
        touch((500, 500))
        sleep(1)
    # 连接第二个模拟器


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test multi emulator connection.")
    parser.add_argument("emu_name", help="Emulator device name, e.g., emulator-5554")
    args = parser.parse_args()

    test_multi_emu(args.emu_name)
