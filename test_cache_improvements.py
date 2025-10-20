#!/usr/bin/env python3
"""
测试缓存改进功能
"""

import os
import sys
import time
import shutil

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def test_cache_performance():
    """测试缓存性能"""
    print("=" * 60)
    print("测试缓存改进功能")
    print("=" * 60)

    # 创建测试输出目录
    test_output_dir = "test_cache_output"
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)

    # 初始化 OCRHelper，使用较小的缓存大小便于测试
    ocr = OCRHelper(
        output_dir=test_output_dir,
        max_cache_size=5,  # 设置较小的缓存大小
        hash_type="dhash",  # 使用 dhash（最快）
        hash_threshold=10,  # 哈希距离阈值
        resize_image=True,
        max_width=640,
    )

    # 测试图片路径
    test_images = [
        "images/screenshots/Screenshot_20251008-155637.png",
        "images/screenshots/Screenshot_20251008-160246.png",
        "images/screenshots/Screenshot_20251008-161048.png",
    ]

    # 过滤存在的图片
    existing_images = [img for img in test_images if os.path.exists(img)]

    if not existing_images:
        print("❌ 没有找到测试图片，请确保 images/screenshots/ 目录下有测试图片")
        return

    print(f"\n✅ 找到 {len(existing_images)} 张测试图片")

    # 第一轮：无缓存（首次识别）
    print("\n📊 第一轮测试（无缓存）:")
    total_time_no_cache = 0
    for img_path in existing_images:
        start_time = time.time()
        result = ocr.find_text_in_image(
            img_path, "设置", confidence_threshold=0.5, use_cache=True
        )
        elapsed = time.time() - start_time
        total_time_no_cache += elapsed
        print(
            f"  - {os.path.basename(img_path)}: {elapsed:.3f}秒, 找到: {result.get('found', False)}"
        )

    print(f"\n总耗时（无缓存）: {total_time_no_cache:.3f}秒")

    # 第二轮：有缓存（应该更快）
    print("\n📊 第二轮测试（有缓存）:")
    total_time_with_cache = 0
    for img_path in existing_images:
        start_time = time.time()
        result = ocr.find_text_in_image(
            img_path, "设置", confidence_threshold=0.5, use_cache=True
        )
        elapsed = time.time() - start_time
        total_time_with_cache += elapsed
        print(
            f"  - {os.path.basename(img_path)}: {elapsed:.3f}秒, 找到: {result.get('found', False)}"
        )

    print(f"\n总耗时（有缓存）: {total_time_with_cache:.3f}秒")

    # 计算性能提升
    if total_time_no_cache > 0:
        improvement = (
            (total_time_no_cache - total_time_with_cache) / total_time_no_cache
        ) * 100
        print(f"\n🚀 性能提升: {improvement:.1f}%")

    # 测试区域缓存
    print("\n📊 测试区域缓存:")
    for img_path in existing_images[:1]:  # 只测试第一张图片
        for region in [[1], [2], [5], [1, 2, 3]]:
            start_time = time.time()
            result = ocr.find_text_in_image(
                img_path,
                "设置",
                confidence_threshold=0.5,
                use_cache=True,
                regions=region,
            )
            elapsed = time.time() - start_time
            print(
                f"  - 区域 {region}: {elapsed:.3f}秒, 找到: {result.get('found', False)}"
            )

            # 再次测试相同区域（应该命中缓存）
            start_time = time.time()
            result = ocr.find_text_in_image(
                img_path,
                "设置",
                confidence_threshold=0.5,
                use_cache=True,
                regions=region,
            )
            elapsed2 = time.time() - start_time
            print(
                f"    再次测试区域 {region}: {elapsed2:.3f}秒 (缓存: {'✅' if elapsed2 < elapsed * 0.5 else '❌'})"
            )

    # 显示缓存统计
    print("\n📊 缓存统计:")
    cache_db_path = os.path.join(test_output_dir, "cache", "cache.db")
    if os.path.exists(cache_db_path):
        import sqlite3

        conn = sqlite3.connect(cache_db_path)
        cursor = conn.cursor()

        # 获取总条目数
        cursor.execute("SELECT COUNT(*) FROM cache_entries")
        total_entries = cursor.fetchone()[0]
        print(f"  - 总缓存条目数: {total_entries}")

        # 获取命中次数最多的条目
        cursor.execute(
            "SELECT image_path, hit_count FROM cache_entries ORDER BY hit_count DESC LIMIT 3"
        )
        top_hits = cursor.fetchall()
        print("  - 命中次数最多的条目:")
        for path, hits in top_hits:
            print(f"    * {os.path.basename(path)}: {hits} 次")

        conn.close()

    # 清理测试目录
    print(f"\n🧹 清理测试目录: {test_output_dir}")
    shutil.rmtree(test_output_dir)

    print("\n✅ 测试完成！")


def test_hash_comparison():
    """测试不同哈希算法的性能"""
    print("\n" + "=" * 60)
    print("测试哈希算法性能")
    print("=" * 60)

    # 准备测试图片
    test_image = "images/screenshots/Screenshot_20251008-155637.png"
    if not os.path.exists(test_image):
        print("❌ 测试图片不存在")
        return

    hash_types = ["phash", "dhash", "ahash", "whash"]

    for hash_type in hash_types:
        print(f"\n测试 {hash_type}:")
        test_dir = f"test_{hash_type}"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

        ocr = OCRHelper(
            output_dir=test_dir,
            max_cache_size=10,
            hash_type=hash_type,
            hash_threshold=10,
            resize_image=True,
            max_width=640,
        )

        # 测试多次识别
        times = []
        for i in range(3):
            start_time = time.time()
            result = ocr.find_text_in_image(
                test_image, "设置", confidence_threshold=0.5, use_cache=True
            )
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"  第 {i + 1} 次: {elapsed:.3f}秒")

        avg_time = sum(times) / len(times)
        print(f"  平均耗时: {avg_time:.3f}秒")

        # 清理
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    # 安装必要的依赖
    print("检查依赖...")
    try:
        import imagehash
        import sqlite3
        from PIL import Image

        print("✅ 所有依赖已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install imagehash Pillow")
        sys.exit(1)

    # 运行测试
    test_cache_performance()
    test_hash_comparison()
