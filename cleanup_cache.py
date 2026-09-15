#!/usr/bin/env python3
"""
清理和重组缓存目录结构
"""

import argparse
import os
import shutil
import time


def cleanup_temp_dir(temp_dir=None, max_age_hours=24.0, logger=None):
    """删除 ``output/temp`` 下滞留时间超过 ``max_age_hours`` 的残留文件。

    正常流程中每张 OCR 临时截图用完即删（``delete_temp_screenshots=True``），
    本函数只兜底清理进程被中断（崩溃/强杀/沙箱拦截）时留下的文件。
    按文件修改时间判断，因此不会误删并发会话正在使用的新文件。

    Args:
        temp_dir: 临时目录路径，默认 ``output/temp``。
        max_age_hours: 判定为残留的最小滞留小时数。
        logger: 可选日志对象；未提供时使用 ``print`` 输出。

    Returns:
        ``(removed, failed, freed_bytes)`` 三元组。
    """
    if temp_dir is None:
        temp_dir = os.path.join("output", "temp")

    def _log(level, msg):
        if logger is not None:
            try:
                getattr(logger, level)(msg)
                return
            except Exception:
                pass
        print(msg)

    if not os.path.isdir(temp_dir):
        return 0, 0, 0

    deadline = time.time() - max_age_hours * 3600
    removed = 0
    failed = 0
    freed = 0

    for filename in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, filename)
        try:
            if not os.path.isfile(filepath):
                continue
            if os.path.getmtime(filepath) > deadline:
                continue
            size = os.path.getsize(filepath)
            os.remove(filepath)
            removed += 1
            freed += size
        except Exception as exc:
            failed += 1
            _log("warning", f"⚠️ 清理临时文件失败: {filename} - {exc}")

    if removed or failed:
        _log(
            "info",
            f"🧹 清理残留临时截图: 删除 {removed} 个 / 失败 {failed} 个，"
            f"释放 {freed / 1024 / 1024:.2f} MB",
        )
    return removed, failed, freed


def cleanup_output_directory(full_clean=False):
    """
    清理 output 目录，重组缓存结构
    
    Args:
        full_clean (bool): 是否执行完全清理（包括删除数据库）
    """
    print("=" * 60)
    print("清理和重组缓存目录结构")
    if full_clean:
        print("⚠️ 警告: 将执行完全清理，删除所有缓存数据库！")
    print("=" * 60)

    output_dir = "output"
    cache_dir = os.path.join(output_dir, "cache")
    temp_dir = os.path.join(output_dir, "temp")
    db_path = os.path.join(cache_dir, "cache.db")

    # 确保目录存在
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    # 0. 如果是完全清理，先删除数据库
    if full_clean and os.path.exists(db_path):
        try:
            print(f"\n🧨 正在删除缓存数据库: {db_path}")
            os.remove(db_path)
            print("✅ 缓存数据库已删除")
        except Exception as e:
            print(f"❌ 删除数据库失败: {e}")

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

    # 2. 清理旧的 cache 文件
    print("\n🗑️ 清理旧的缓存文件...")
    cache_files_removed = 0
    cache_files_failed = 0
    total_size_freed = 0

    # 如果数据库被删除了（或者不存在），所有缓存文件都应该被清理
    if not os.path.exists(db_path):
        print("  数据库不存在，将清理所有缓存文件...")
        files_to_keep = set()
    else:
        # 读取数据库，了解哪些文件应该保留
        # 注意：现在数据库只存哈希和JSON，不存文件路径，所以理论上 cache 目录下不应该有图片文件
        # 除非是旧版本的残留。这里我们保留 cache.db 和索引文件
        files_to_keep = {"cache.db", "cache_index.json"}

    print("  扫描 cache 目录中的所有文件...")
    all_files = os.listdir(cache_dir)
    print(f"  总文件数: {len(all_files)}")

    for filename in all_files:
        filepath = os.path.join(cache_dir, filename)

        # 始终保留数据库文件（如果它还没被删）
        if filename == "cache.db":
            continue

        # 如果文件不在保留列表中，删除它
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

    print(f"✅ 删除了 {cache_files_removed} 个文件")
    if cache_files_failed > 0:
        print(f"⚠️ 删除失败: {cache_files_failed} 个文件")
    if total_size_freed > 0:
        size_mb = total_size_freed / 1024 / 1024
        print(f"📊 释放空间: {size_mb:.2f} MB")

    # 3. 创建 temp 目录（如果不存在）
    print("\n📁 确保临时目录存在...")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 清理 temp 目录
    print("🧹 清理 temp 目录...")
    temp_removed = 0
    for filename in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
                temp_removed += 1
            elif os.path.isdir(filepath):
                shutil.rmtree(filepath)
                temp_removed += 1
        except Exception:
            pass
    print(f"✅ 清理了 {temp_removed} 个临时文件")

    # 4. 显示目录结构
    print("\n📊 新的目录结构:")
    print("output/")
    print("├── cache/        # 缓存目录（仅缓存数据库）")
    print("├── temp/         # 临时文件（已清空）")

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
    parser = argparse.ArgumentParser(description="清理 OCR 缓存工具")
    parser.add_argument("-f", "--full", action="store_true", help="执行完全清理（删除缓存数据库）")
    args = parser.parse_args()

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
        cleanup_output_directory(full_clean=args.full)
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        logger.critical(
            f"缓存清理工具异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}"
        )
        raise
