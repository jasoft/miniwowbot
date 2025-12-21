# simple_airtest_test.py
import logging
import sys

from airtest.core.api import *
from airtest.core.error import AirtestError

# Set up logging (optional but good for debugging)
logger = logging.getLogger("airtest.core.api")
# Set level to DEBUG to capture more detailed Airtest logs
logger.setLevel(logging.DEBUG)
# Ensure only one handler to prevent duplicate log messages
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(asctime)s][%(levelname)s]<%(logger_name)s> %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def run_test():
    try:
        print("尝试连接模拟器 127.0.0.1:5555...")

        # Connect to the device.
        # Format for connect_device: "Android://<uuid>?cap_method=JAVACAP&ori_method=ADBORI"
        # For local emulator, it's often "Android:///127.0.0.1:5555?cap_method=JAVACAP&ori_method=ADBORI"
        # Adding a timeout for connection
        connect_device("Android://127.0.0.1:5037/127.0.0.1:5555")

        print("成功连接模拟器。")

        # Perform a simple tap at a coordinate (e.g., center of screen for a common resolution)
        # Assuming a common resolution like 1280x720, center would be (640, 360)
        # This will fail if the screen is locked or an app is not in the foreground.
        print("尝试执行 tap (点击) 指令在 (358, 43)...")
        touch((358, 43))
        print("tap 指令执行成功。")

        # Optionally, take a screenshot to verify
        # snapshot(msg="After tap")

        print("测试完成。")

    except AirtestError as e:
        print(f"Airtest 错误发生: {e}")
        logger.exception(f"Airtest Error: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")
        logger.exception(f"General Error: {e}")


if __name__ == "__main__":
    # Initialize Airtest setup if needed, e.g., for report generation or specific environment setup.
    # For a simple test, direct calls are fine.
    # auto_setup(__file__)
    run_test()
