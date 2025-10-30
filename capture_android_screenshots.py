#!/usr/bin/env python3
"""
安卓模拟器自动截图脚本
用于 YOLO 训练数据集收集
每隔3秒自动截取安卓模拟器屏幕截图并保存
"""

import subprocess
import time
from datetime import datetime
from pathlib import Path

# 导入 EmulatorManager 以获取 Airtest 内置的 ADB
try:
    from emulator_manager import EmulatorManager

    _emulator_manager = EmulatorManager()
    _adb_path = _emulator_manager.adb_path
except Exception as e:
    print(f"⚠️ 无法初始化 EmulatorManager: {e}，将使用系统 adb")
    _adb_path = "adb"


class AndroidScreenshotCapture:
    def __init__(self, output_dir="yolo_training_images", interval=3):
        """
        初始化截图捕获器

        Args:
            output_dir: 输出目录路径
            interval: 截图间隔（秒）
        """
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.screenshot_count = 0

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ 输出目录: {self.output_dir.absolute()}")

    def check_adb_connection(self):
        """检查 ADB 连接是否正常"""
        try:
            result = subprocess.run(
                [_adb_path, "devices"], capture_output=True, text=True, check=True
            )

            # 解析设备列表
            lines = result.stdout.strip().split("\n")[1:]  # 跳过第一行标题
            devices = [
                line.split()[0] for line in lines if line.strip() and "device" in line
            ]

            if not devices:
                print("❌ 错误: 未检测到安卓设备/模拟器")
                print("请确保:")
                print("  1. 模拟器已启动")
                print("  2. ADB 已安装并在 PATH 中")
                print("  3. 运行 'adb devices' 确认设备连接")
                return False

            print(f"✓ 检测到设备: {', '.join(devices)}")
            if len(devices) > 1:
                print(f"⚠️  警告: 检测到多个设备，将使用第一个设备: {devices[0]}")

            return True

        except FileNotFoundError:
            print("❌ 错误: 未找到 adb 命令")
            print("请安装 Android SDK Platform Tools 或确保 adb 在 PATH 中")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ ADB 命令执行失败: {e}")
            return False

    def capture_screenshot(self):
        """
        截取屏幕截图并保存到本地

        Returns:
            bool: 截图是否成功
        """
        try:
            # 生成文件名（使用时间戳和计数器）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}_{self.screenshot_count:04d}.png"
            filepath = self.output_dir / filename

            # 设备上的临时截图路径
            device_screenshot_path = "/sdcard/screenshot_temp.png"

            # 在设备上截图
            subprocess.run(
                [_adb_path, "shell", "screencap", "-p", device_screenshot_path],
                check=True,
                capture_output=True,
            )

            # 从设备拉取截图到本地
            subprocess.run(
                [_adb_path, "pull", device_screenshot_path, str(filepath)],
                check=True,
                capture_output=True,
            )

            # 删除设备上的临时文件
            subprocess.run(
                [_adb_path, "shell", "rm", device_screenshot_path],
                check=False,  # 即使删除失败也继续
                capture_output=True,
            )

            self.screenshot_count += 1
            file_size = filepath.stat().st_size / 1024  # KB
            print(f"✓ [{self.screenshot_count:04d}] {filename} ({file_size:.1f} KB)")

            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ 截图失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 未预期的错误: {e}")
            return False

    def run(self):
        """运行截图循环"""
        print("\n" + "=" * 60)
        print("安卓模拟器自动截图工具 - YOLO 训练数据集收集")
        print("=" * 60)

        # 检查 ADB 连接
        if not self.check_adb_connection():
            return

        print("\n配置:")
        print(f"  截图间隔: {self.interval} 秒")
        print(f"  输出目录: {self.output_dir.absolute()}")
        print("\n开始截图... (按 Ctrl+C 停止)\n")

        try:
            while True:
                success = self.capture_screenshot()

                if not success:
                    print("⚠️  截图失败，等待下次尝试...")

                # 等待指定的间隔时间
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("✓ 截图已停止")
            print(f"✓ 总共捕获: {self.screenshot_count} 张截图")
            print(f"✓ 保存位置: {self.output_dir.absolute()}")
            print("=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="安卓模拟器自动截图工具 - 用于 YOLO 训练数据收集"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="yolo_training_images",
        help="输出目录路径 (默认: yolo_training_images)",
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=3.0, help="截图间隔秒数 (默认: 3)"
    )

    args = parser.parse_args()

    # 创建截图捕获器并运行
    capturer = AndroidScreenshotCapture(output_dir=args.output, interval=args.interval)
    capturer.run()


if __name__ == "__main__":
    main()
