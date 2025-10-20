#!/usr/bin/env python3
"""
测试清理后的缓存系统
"""

import os
import sys
import time
import shutil

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_helper import OCRHelper


def test_directory_structure():
    """测试新的目录结构"""
    print("=" * 60)
    print("测试新的目录结构")
    print("=" * 60)

    # 检查目录结构
    output_dir = "output"
    cache_dir = os.path.join(output_dir, "cache")
    temp_dir = os.path.join(output_dir, "temp")

    print("\n📁 目录结构检查:")
    print(f"  output/: {'✅' if os.path.exists(output_dir) else '❌'}")
    print(f"    cache/: {'✅' if os.path.exists(cache_dir) else '❌'}")
    print(
        f"      cache.db: {'✅' if os.path.exists(os.path.join(cache_dir, 'cache.db')) else '❌'}"
    )
    print(f"    temp/: {'✅' if os.path.exists(temp_dir) else '❌'}")

    # 统计文件
    cache_files = len(os.listdir(cache_dir)) if os.path.exists(cache_dir) else 0
    temp_files = len(os.listdir(temp_dir)) if os.path.exists(temp_dir) else 0

    print(f"\n📊 文件统计:")
    print(f"  cache 目录: {cache_files} 个文件")
    print(f"  temp 目录: {temp_files} 个文件")


def test_cache_functionality():
    """测试缓存功能"""
    print("\n" + "=" * 60)
    print("测试缓存功能")
    print("=" * 60)

    # 初始化 OCRHelper
    ocr = OCRHelper(
        output_dir="output",
        max_cache_size=10,
        hash_type="dhash",
        hash_threshold=10,
        resize_image=True,
        max_width=640,
    )

    # 查找测试图片
    test_images = []
    for filename in os.listdir("images/screenshots"):
        if filename.endswith(".png"):
            test_images.append(os.path.join("images/screenshots", filename))
            if len(test_images) >= 2:
                break

    if not test_images:
        print("❌ 没有找到测试图片")
        return

    print(f"\n✅ 找到 {len(test_images)} 张测试图片")

    # 测试缓存功能
    for img_path in test_images:
        print(f"\n📸 测试图片: {os.path.basename(img_path)}")

        # 第一次识别（无缓存）
        start_time = time.time()
        result = ocr.find_text_in_image(img_path, "设置", use_cache=True)
        elapsed1 = time.time() - start_time
        print(f"  首次识别: {elapsed1:.3f}秒")

        # 第二次识别（应该命中缓存）
        start_time = time.time()
        result = ocr.find_text_in_image(img_path, "设置", use_cache=True)
        elapsed2 = time.time() - start_time
        print(f"  缓存命中: {elapsed2:.3f}秒")

        if elapsed1 > 0:
            speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float("inf")
            print(f"  加速比: {speedup:.1f}x")

    # 测试区域缓存
    print("\n🔍 测试区域缓存:")
    img_path = test_images[0]
    for region in [[5], [7, 8, 9]]:
        print(f"\n  区域 {region}:")

        # 第一次
        start_time = time.time()
        ocr.find_text_in_image(img_path, "设置", regions=region, use_cache=True)
        elapsed1 = time.time() - start_time
        print(f"    首次: {elapsed1:.3f}秒")

        # 第二次
        start_time = time.time()
        ocr.find_text_in_image(img_path, "设置", regions=region, use_cache=True)
        elapsed2 = time.time() - start_time
        print(f"    缓存: {elapsed2:.3f}秒")


def test_temp_files():
    """测试临时文件管理"""
    print("\n" + "=" * 60)
    print("测试临时文件管理")
    print("=" * 60)

    ocr = OCRHelper(output_dir="output")

    # 测试截图功能
    temp_files_before = (
        len(os.listdir("output/temp")) if os.path.exists("output/temp") else 0
    )

    print(f"\n📸 测试截图功能...")
    print(f"  截图前 temp 目录文件数: {temp_files_before}")

    # 使用 capture_and_find_text（会生成临时文件）
    result = ocr.capture_and_find_text("设置", use_cache=False)

    temp_files_after = (
        len(os.listdir("output/temp")) if os.path.exists("output/temp") else 0
    )
    print(f"  截图后 temp 目录文件数: {temp_files_after}")

    # 清理临时文件
    if ocr.delete_temp_screenshots:
        print("\n🧹 清理临时文件...")
        # 这里可以手动清理 temp 目录
        # shutil.rmtree("output/temp")
        # os.makedirs("output/temp")
        print("  临时文件会在程序运行时自动清理")


def show_cache_stats():
    """显示缓存统计信息"""
    print("\n" + "=" * 60)
    print("缓存统计信息")
    print("=" * 60)

    cache_db_path = "output/cache/cache.db"
    if os.path.exists(cache_db_path):
        import sqlite3

        conn = sqlite3.connect(cache_db_path)
        cursor = conn.cursor()

        # 总条目数
        cursor.execute("SELECT COUNT(*) FROM cache_entries")
        total = cursor.fetchone()[0]
        print(f"\n📊 总缓存条目数: {total}")

        # 命中次数最多的
        cursor.execute("""
            SELECT image_path, hit_count
            FROM cache_entries
            ORDER BY hit_count DESC
            LIMIT 5
        """)
        print("\n🔥 最常访问的缓存:")
        for path, hits in cursor.fetchall():
            print(f"  {os.path.basename(path)}: {hits} 次")

        # 最近访问的
        cursor.execute("""
            SELECT image_path, last_access_time
            FROM cache_entries
            ORDER BY last_access_time DESC
            LIMIT 5
        """)
        print("\n🕒 最近访问的缓存:")
        for path, access_time in cursor.fetchall():
            import datetime

            dt = datetime.datetime.fromtimestamp(access_time)
            print(f"  {os.path.basename(path)}: {dt.strftime('%H:%M:%S')}")

        conn.close()
    else:
        print("\n❌ 缓存数据库不存在")


if __name__ == "__main__":
    # 运行所有测试
    test_directory_structure()
    test_cache_functionality()
    test_temp_files()
    show_cache_stats()

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
