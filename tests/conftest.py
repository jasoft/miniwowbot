# -*- encoding=utf8 -*-

import pytest

from tests.airtest_device_utils import resolve_airtest_device_uri


def pytest_addoption(parser):
    group = parser.getgroup("miniwow")
    group.addoption(
        "--device-uri",
        action="store",
        default=None,
        help=(
            "Airtest 设备 URI（例如 Android:/// 或 Android:///127.0.0.1:5555）。"
            "也可通过环境变量 MINIWOW_DEVICE_URI / AIRTEST_DEVICE_URI 指定。"
        ),
    )
    group.addoption(
        "--emulator",
        action="store",
        default=None,
        help=(
            "模拟器 adb 序列或 host:port（例如 127.0.0.1:5555 / emulator-5554）。"
            "会自动转换为 Android:///<value>；也支持直接传完整 Airtest URI。"
            "也可通过环境变量 MINIWOW_EMULATOR / AIRTEST_EMULATOR 指定。"
        ),
    )


@pytest.fixture(scope="session")
def airtest_device_uri(request) -> str:
    return resolve_airtest_device_uri(
        device_uri_opt=request.config.getoption("--device-uri"),
        emulator_opt=request.config.getoption("--emulator"),
    )

