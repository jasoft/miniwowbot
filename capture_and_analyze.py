#!/usr/bin/env python3
"""
安卓模拟器自动截图并使用 Roboflow 分析脚本
实时检测游戏中的目标元素
"""

import subprocess
import time
import base64
import json
from datetime import datetime
from pathlib import Path
import requests


class RoboflowAnalyzer:
    """Roboflow 计算机视觉分析器"""

    def __init__(self, api_key, workspace, workflow_id):
        """
        初始化 Roboflow 分析器

        Args:
            api_key: Roboflow API 密钥
            workspace: 工作空间名称
            workflow_id: 工作流 ID
        """
        self.api_key = api_key
        self.workspace = workspace
        self.workflow_id = workflow_id
        self.api_url = (
            f"https://serverless.roboflow.com/{workspace}/workflows/{workflow_id}"
        )

    def analyze_image(self, image_path):
        """
        使用 Roboflow 分析图片

        Args:
            image_path: 图片文件路径

        Returns:
            dict: 分析结果，包含检测到的对象
        """
        try:
            # 读取并编码图片
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

            # 准备请求
            payload = {
                "api_key": self.api_key,
                "inputs": {"image": {"type": "base64", "value": encoded_image}},
            }

            # 发送请求到 Roboflow
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Roboflow API 错误: {e}")
            return None
        except Exception as e:
            print(f"  ⚠️  分析失败: {e}")
            return None


class AndroidScreenshotAnalyzer:
    """安卓截图与分析器"""

    def __init__(
        self,
        output_dir="analyzed_screenshots",
        interval=3,
        enable_roboflow=False,
        roboflow_config=None,
    ):
        """
        初始化截图分析器

        Args:
            output_dir: 输出目录路径
            interval: 截图间隔（秒）
            enable_roboflow: 是否启用 Roboflow 分析
            roboflow_config: Roboflow 配置字典
        """
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.screenshot_count = 0
        self.enable_roboflow = enable_roboflow

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        self.images_dir = self.output_dir / "images"
        self.results_dir = self.output_dir / "results"
        self.images_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)

        # 初始化 Roboflow 分析器
        self.roboflow = None
        if enable_roboflow and roboflow_config:
            self.roboflow = RoboflowAnalyzer(
                api_key=roboflow_config["api_key"],
                workspace=roboflow_config["workspace"],
                workflow_id=roboflow_config["workflow_id"],
            )
            print("✓ Roboflow 分析已启用")

        print(f"✓ 输出目录: {self.output_dir.absolute()}")
        print(f"  - 图片: {self.images_dir.relative_to(self.output_dir)}/")
        print(f"  - 结果: {self.results_dir.relative_to(self.output_dir)}/")

    def check_adb_connection(self):
        """检查 ADB 连接是否正常"""
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, check=True
            )

            lines = result.stdout.strip().split("\n")[1:]
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
            print("请安装 Android SDK Platform Tools")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ ADB 命令执行失败: {e}")
            return False

    def capture_screenshot(self):
        """
        截取屏幕截图并保存到本地

        Returns:
            Path: 截图文件路径，失败返回 None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}_{self.screenshot_count:04d}.png"
            filepath = self.images_dir / filename

            device_screenshot_path = "/sdcard/screenshot_temp.png"

            # 在设备上截图
            subprocess.run(
                ["adb", "shell", "screencap", "-p", device_screenshot_path],
                check=True,
                capture_output=True,
            )

            # 从设备拉取截图
            subprocess.run(
                ["adb", "pull", device_screenshot_path, str(filepath)],
                check=True,
                capture_output=True,
            )

            # 删除设备上的临时文件
            subprocess.run(
                ["adb", "shell", "rm", device_screenshot_path],
                check=False,
                capture_output=True,
            )

            self.screenshot_count += 1
            file_size = filepath.stat().st_size / 1024
            print(f"✓ [{self.screenshot_count:04d}] {filename} ({file_size:.1f} KB)")

            return filepath

        except subprocess.CalledProcessError as e:
            print(f"❌ 截图失败: {e}")
            return None
        except Exception as e:
            print(f"❌ 未预期的错误: {e}")
            return None

    def analyze_and_save_results(self, image_path):
        """
        分析图片并保存结果

        Args:
            image_path: 图片路径
        """
        if not self.roboflow:
            return

        print("  🔍 正在使用 Roboflow 分析...")

        result = self.roboflow.analyze_image(image_path)

        if result:
            # 保存分析结果
            result_filename = image_path.stem + "_result.json"
            result_filepath = self.results_dir / result_filename

            with open(result_filepath, "w", encoding="utf-8") as f:
                json.dump(result, indent=2, fp=f)

            # 解析并显示检测结果
            self.display_detection_summary(result)
        else:
            print("  ❌ 分析失败")

    def display_detection_summary(self, result):
        """
        显示检测结果摘要

        Args:
            result: Roboflow API 响应结果
        """
        try:
            outputs = result.get("outputs", [])
            if not outputs:
                print("  ℹ️  未检测到任何对象")
                return

            predictions = outputs[0].get("predictions", {}).get("predictions", [])

            if not predictions:
                print("  ℹ️  未检测到任何对象")
                return

            # 按类别统计
            class_counts = {}
            for pred in predictions:
                class_name = pred.get("class", "unknown")
                confidence = pred.get("confidence", 0)

                if class_name not in class_counts:
                    class_counts[class_name] = {"count": 0, "confidences": []}

                class_counts[class_name]["count"] += 1
                class_counts[class_name]["confidences"].append(confidence)

            print(f"  ✓ 检测到 {len(predictions)} 个对象:")
            for class_name, data in class_counts.items():
                avg_confidence = sum(data["confidences"]) / len(data["confidences"])
                print(
                    f"    - {class_name}: {data['count']} 个 (平均置信度: {avg_confidence:.2%})"
                )

        except Exception as e:
            print(f"  ⚠️  解析结果时出错: {e}")

    def run(self):
        """运行截图和分析循环"""
        print("\n" + "=" * 70)
        print("安卓模拟器自动截图与分析工具")
        if self.enable_roboflow:
            print("✓ Roboflow 实时分析已启用")
        print("=" * 70)

        if not self.check_adb_connection():
            return

        print("\n配置:")
        print(f"  截图间隔: {self.interval} 秒")
        print(f"  输出目录: {self.output_dir.absolute()}")
        print(f"  Roboflow 分析: {'已启用' if self.enable_roboflow else '未启用'}")
        print("\n开始截图... (按 Ctrl+C 停止)\n")

        try:
            while True:
                # 截图
                image_path = self.capture_screenshot()

                if image_path and self.enable_roboflow:
                    # 使用 Roboflow 分析
                    self.analyze_and_save_results(image_path)

                # 等待间隔
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("✓ 截图已停止")
            print(f"✓ 总共捕获: {self.screenshot_count} 张截图")
            print(f"✓ 保存位置: {self.output_dir.absolute()}")
            if self.enable_roboflow:
                print(f"  - 图片: {self.images_dir}/")
                print(f"  - 分析结果: {self.results_dir}/")
            print("=" * 70)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="安卓模拟器自动截图与 Roboflow 分析工具"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="analyzed_screenshots",
        help="输出目录路径 (默认: analyzed_screenshots)",
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=3.0, help="截图间隔秒数 (默认: 3)"
    )
    parser.add_argument(
        "--enable-roboflow", action="store_true", help="启用 Roboflow 实时分析"
    )
    parser.add_argument(
        "--api-key", default="w6oOUMB3dpmlpFSXv8t5", help="Roboflow API 密钥"
    )
    parser.add_argument("--workspace", default="soj-demo", help="Roboflow 工作空间名称")
    parser.add_argument(
        "--workflow-id",
        default="find-targetarrows-taskavailables-gobuttons-and-taskcompletes",
        help="Roboflow 工作流 ID",
    )

    args = parser.parse_args()

    # 准备 Roboflow 配置
    roboflow_config = None
    if args.enable_roboflow:
        roboflow_config = {
            "api_key": args.api_key,
            "workspace": args.workspace,
            "workflow_id": args.workflow_id,
        }

    # 创建截图分析器并运行
    analyzer = AndroidScreenshotAnalyzer(
        output_dir=args.output,
        interval=args.interval,
        enable_roboflow=args.enable_roboflow,
        roboflow_config=roboflow_config,
    )
    analyzer.run()


if __name__ == "__main__":
    main()
