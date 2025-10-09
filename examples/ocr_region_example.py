"""
OCR 区域搜索功能示例

演示如何使用区域搜索功能来加快OCR识别速度
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ocr_helper import OCRHelper


def main():
    """主函数"""
    print("=" * 60)
    print("OCR 区域搜索功能示例")
    print("=" * 60)

    # 创建 OCR Helper 实例
    ocr = OCRHelper(output_dir="output")

    print("\n区域编号说明：")
    print("  1 2 3")
    print("  4 5 6")
    print("  7 8 9")
    print()
    print("重要：多个区域会自动合并成一个连续的矩形进行OCR")
    print("例如：[1,2,3] 会合并成整个上部，[7,8,9] 会合并成整个底部")
    print()

    # 示例1: 在整个屏幕中搜索（默认行为）
    print("示例1: 在整个屏幕中搜索文字")
    print("-" * 60)
    result = ocr.capture_and_find_text(
        "设置", confidence_threshold=0.6, screenshot_path="/tmp/full_screen.png"
    )
    if result["found"]:
        print(f"✅ 找到文字: {result['text']}")
        print(f"   位置: {result['center']}")
        print(f"   置信度: {result['confidence']:.2f}")
    else:
        print("❌ 未找到文字")

    # 示例2: 只在屏幕右上角搜索（区域3）
    print("\n示例2: 只在屏幕右上角搜索（区域3）")
    print("-" * 60)
    result = ocr.capture_and_find_text(
        "设置",
        confidence_threshold=0.6,
        screenshot_path="/tmp/region_3.png",
        regions=[3],  # 只搜索右上角
    )
    if result["found"]:
        print(f"✅ 找到文字: {result['text']}")
        print(f"   位置: {result['center']}")
        print(f"   置信度: {result['confidence']:.2f}")
    else:
        print("❌ 未找到文字")

    # 示例3: 在屏幕上半部分搜索（区域1, 2, 3）
    print("\n示例3: 在屏幕上半部分搜索（区域1, 2, 3）")
    print("-" * 60)
    result = ocr.capture_and_find_text(
        "返回",
        confidence_threshold=0.6,
        screenshot_path="/tmp/top_half.png",
        regions=[1, 2, 3],  # 搜索上半部分
    )
    if result["found"]:
        print(f"✅ 找到文字: {result['text']}")
        print(f"   位置: {result['center']}")
        print(f"   置信度: {result['confidence']:.2f}")
    else:
        print("❌ 未找到文字")

    # 示例4: 在屏幕中心区域搜索（区域5）
    print("\n示例4: 在屏幕中心区域搜索（区域5）")
    print("-" * 60)
    result = ocr.capture_and_find_text(
        "确定",
        confidence_threshold=0.6,
        screenshot_path="/tmp/center.png",
        regions=[5],  # 只搜索中心区域
    )
    if result["found"]:
        print(f"✅ 找到文字: {result['text']}")
        print(f"   位置: {result['center']}")
        print(f"   置信度: {result['confidence']:.2f}")
    else:
        print("❌ 未找到文字")

    # 示例5: 在屏幕底部搜索（区域7, 8, 9）
    print("\n示例5: 在屏幕底部搜索（区域7, 8, 9）")
    print("-" * 60)
    result = ocr.capture_and_find_text(
        "免费",
        confidence_threshold=0.6,
        screenshot_path="/tmp/bottom.png",
        regions=[7, 8, 9],  # 搜索底部
    )
    if result["found"]:
        print(f"✅ 找到文字: {result['text']}")
        print(f"   位置: {result['center']}")
        print(f"   置信度: {result['confidence']:.2f}")
    else:
        print("❌ 未找到文字")

    # 示例6: 使用区域搜索并点击
    print("\n示例6: 使用区域搜索并点击")
    print("-" * 60)
    success = ocr.find_and_click_text(
        "进入游戏",
        confidence_threshold=0.6,
        screenshot_path="/tmp/click_region.png",
        regions=[5, 8],  # 在中心和中下区域搜索
    )
    if success:
        print("✅ 成功找到并点击")
    else:
        print("❌ 未找到文字，无法点击")

    print("\n" + "=" * 60)
    print("性能提示：")
    print("- 使用区域搜索可以大大减少OCR识别时间")
    print("- 如果知道文字大概在哪个位置，指定具体区域可以提升3-9倍速度")
    print("- 区域越小，识别速度越快")
    print("- 可以同时指定多个区域，如 regions=[1, 2, 3] 表示搜索上半部分")
    print("=" * 60)


if __name__ == "__main__":
    main()
