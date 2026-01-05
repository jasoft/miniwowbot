#!/usr/bin/env python3
"""
示例：使用随机临时文件名的OCR截图识别
演示如何避免多脚本并行运行时的文件名冲突
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vibe_ocr import OCRHelper


def example_ocr_with_temp_file():
    """示例：使用随机临时文件名进行OCR识别"""

    # 创建OCR Helper实例
    # delete_temp_screenshots=True 表示使用完临时截图后会自动删除
    ocr = OCRHelper(
        output_dir="output",
        delete_temp_screenshots=True,  # 默认为True，会自动删除临时截图
    )

    print("示例1：使用随机临时文件名截图并查找文字")
    print("-" * 50)

    # 查找文字，不指定截图路径（将自动生成随机临时文件名）
    result = ocr.capture_and_find_text(
        target_text="开始",  # 要查找的文字
        confidence_threshold=0.5,  # 置信度阈值
        occurrence=1,  # 查找第一个匹配项
        regions=[1, 2, 3],  # 只在屏幕上方搜索
    )

    if result["found"]:
        print(f"✅ 找到文字: '{result['text']}'")
        print(f"   位置: {result['center']}")
        print(f"   置信度: {result['confidence']:.3f}")
    else:
        print("❌ 未找到指定文字")

    print("\n示例2：使用随机临时文件名截图并点击")
    print("-" * 50)

    # 查找并点击文字，不指定截图路径
    success = ocr.find_and_click_text(
        target_text="确定",
        confidence_threshold=0.5,
        regions=[5],  # 只在屏幕中央搜索
    )

    if success:
        print("✅ 成功找到并点击文字")
    else:
        print("❌ 未能找到或点击文字")

    print("\n示例3：指定特定的截图路径（不使用随机文件名）")
    print("-" * 50)

    # 仍然可以指定特定的截图路径
    specific_path = "output/my_screenshot.png"
    result = ocr.capture_and_find_text(
        target_text="设置", screenshot_path=specific_path
    )

    if result["found"]:
        print(f"✅ 找到文字: '{result['text']}'")
        print(f"   截图保存在: {specific_path}")
    else:
        print("❌ 未找到指定文字")

    print("\n临时文件说明:")
    print("-" * 50)
    print("1. 当不指定 screenshot_path 参数时，系统会自动生成随机文件名")
    print("2. 文件名格式: screenshot_时间戳_UUID.png")
    print("3. 文件保存在: output/temp/ 目录下")
    print("4. 这样可以避免多个脚本同时运行时的文件名冲突")
    print("5. 临时文件会保留，方便调试分析")


def cleanup_temp_files():
    """清理临时文件（可选）"""
    temp_dir = Path("output/temp")
    if temp_dir.exists():
        # 清理24小时前的文件
        cutoff_time = datetime.now() - timedelta(hours=24)
        cleaned_count = 0

        for file_path in temp_dir.iterdir():
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                    except Exception as e:
                        print(f"删除文件失败 {file_path}: {e}")

        if cleaned_count > 0:
            print(f"\n已清理 {cleaned_count} 个24小时前的临时文件")


if __name__ == "__main__":
    print("OCR截图识别示例 - 使用随机临时文件名")
    print("=" * 50)

    try:
        example_ocr_with_temp_file()

        # 询问是否清理旧文件
        response = input("\n是否清理24小时前的临时文件？(y/n): ")
        if response.lower() == "y":
            cleanup_temp_files()

    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback

        traceback.print_exc()
