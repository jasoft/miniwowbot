#!/usr/bin/env python3
"""
清理和重组缓存目录结构
"""

import os
import shutil
import sqlite3
from pathlib import Path


def cleanup_output_directory():
    """清理 output 目录，重组缓存结构"""
    print("=" * 60)
    print("清理和重组缓存目录结构")
    print("=" * 60)

    output_dir = "output"
    cache_dir = os.path.join(output_dir, "cache")
    temp_dir = os.path.join(output_dir, "temp")

    # 确保目录存在
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # 1. 移动所有 JSON 文件到 cache 目录
    print("\n📁 移动 JSON 文件到 cache 目录...")
    json_files_moved = 0
    for filename in os.listdir(output_dir):
        if filename.endswith("_res.json") and not filename.startswith("cache_"):
            src = os.path.join(output_dir, filename)
            dst = os.path.join(cache_dir, filename)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.move(src, dst)
                json_files_moved += 1
                print(f"  移动: {filename}")
    print(f"✅ 移动了 {json_files_moved} 个 JSON 文件")

    # 2. 清理旧的 cache 文件（保留数据库）
    print("\n🗑️ 清理旧的缓存文件...")
    cache_files_removed = 0
    db_path = os.path.join(cache_dir, "cache.db")

    # 读取数据库，了解哪些文件应该保留
    files_to_keep = set()
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT image_path, json_path FROM cache_entries")
        for img_path, json_path in cursor.fetchall():
            files_to_keep.add(os.path.basename(img_path))
            files_to_keep.add(os.path.basename(json_path))
        conn.close()
        print(f"  数据库中有 {len(files_to_keep)} 个文件需要保留")

    # 删除不在数据库中的缓存文件
    for filename in os.listdir(cache_dir):
        filepath = os.path.join(cache_dir, filename)
        if filename in ["cache.db", "cache_index.json"]:
            continue
        if filename.startswith("region_") and filename.endswith(".png"):
            # 保留区域缓存文件
            continue
        if filename not in files_to_keep:
            try:
                os.remove(filepath)
                cache_files_removed += 1
            except:
                pass
    print(f"✅ 删除了 {cache_files_removed} 个孤立的缓存文件")

    # 3. 创建 temp 目录（如果不存在）
    print("\n📁 确保临时目录存在...")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"✅ 临时目录: {temp_dir}")

    # 4. 显示目录结构
    print("\n📊 新的目录结构:")
    print(f"output/")
    print(f"├── cache/        # 缓存目录（包含图片、JSON、数据库）")
    print(f"├── temp/         # 临时文件（可随时删除）")

    # 统计文件数量
    cache_files = len(os.listdir(cache_dir)) if os.path.exists(cache_dir) else 0
    temp_files = len(os.listdir(temp_dir)) if os.path.exists(temp_dir) else 0

    print(f"\n📈 文件统计:")
    print(f"  - cache 目录: {cache_files} 个文件")
    print(f"  - temp 目录: {temp_files} 个文件")
    print(
        f"  - output 根目录: {len([f for f in os.listdir(output_dir) if f not in ['cache', 'temp']])} 个文件"
    )

    print("\n✅ 清理完成！")


if __name__ == "__main__":
    cleanup_output_directory()
