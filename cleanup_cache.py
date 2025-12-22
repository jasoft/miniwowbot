#!/usr/bin/env python3
"""
清理和重组缓存目录结构
"""

import os
import shutil
import sqlite3


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
    cache_files_failed = 0
    total_size_freed = 0
    db_path = os.path.join(cache_dir, "cache.db")

    # 读取数据库，了解哪些文件应该保留
    files_to_keep = {"cache.db", "cache_index.json"}
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ocr_cache'"
        )
        has_new_cache = cursor.fetchone() is not None
        if not has_new_cache:
            try:
                cursor.execute("SELECT image_path, json_path FROM cache_entries")
                for img_path, json_path in cursor.fetchall():
                    files_to_keep.add(os.path.basename(img_path))
                    files_to_keep.add(os.path.basename(json_path))
                print(f"  数据库中有 {len(files_to_keep)} 个文件需要保留")
            except sqlite3.Error:
                pass
        conn.close()
    # 删除不在数据库中的缓存文件
    print("  扫描 cache 目录中的所有文件...")
    all_files = os.listdir(cache_dir)
    print(f"  总文件数: {len(all_files)}")

    for filename in all_files:
        filepath = os.path.join(cache_dir, filename)

        # 只保留数据库和索引文件
        if filename in ["cache.db", "cache_index.json"]:
            continue

        # 如果文件不在数据库中，删除它
        if filename not in files_to_keep:
            try:
                if os.path.isfile(filepath):
                    file_size = os.path.getsize(filepath)
                    os.remove(filepath)
                    cache_files_removed += 1
                    total_size_freed += file_size
                elif os.path.isdir(filepath):
                    # 如果是目录，递归删除
                    shutil.rmtree(filepath)
                    cache_files_removed += 1
            except Exception as e:
                cache_files_failed += 1
                print(f"  ⚠️ 删除失败: {filename} - {e}")

    print(f"✅ 删除了 {cache_files_removed} 个孤立的缓存文件")
    if cache_files_failed > 0:
        print(f"⚠️ 删除失败: {cache_files_failed} 个文件")
    if total_size_freed > 0:
        size_mb = total_size_freed / 1024 / 1024
        print(f"📊 释放空间: {size_mb:.2f} MB")

    # 3. 创建 temp 目录（如果不存在）
    print("\n📁 确保临时目录存在...")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"✅ 临时目录: {temp_dir}")

    # 4. 显示目录结构
    print("\n📊 新的目录结构:")
    print("output/")
    print("├── cache/        # 缓存目录（仅缓存数据库）")
    print("├── temp/         # 临时文件（可随时删除）")

    # 统计文件数量
    cache_files = len(os.listdir(cache_dir)) if os.path.exists(cache_dir) else 0
    temp_files = len(os.listdir(temp_dir)) if os.path.exists(temp_dir) else 0

    print("\n📈 文件统计:")
    print(f"  - cache 目录: {cache_files} 个文件")
    print(f"  - temp 目录: {temp_files} 个文件")
    print(
        f"  - output 根目录: {len([f for f in os.listdir(output_dir) if f not in ['cache', 'temp']])} 个文件"
    )

    print("\n✅ 清理完成！")


if __name__ == "__main__":
    import logging

    # 初始化日志
    try:
        from logger_config import setup_logger_from_config

        logger = setup_logger_from_config(use_color=True)
    except Exception:
        # 如果无法导入日志配置，使用基础日志
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

    try:
        cleanup_output_directory()
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        logger.critical(
            f"缓存清理工具异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}"
        )
        raise
