#!/usr/bin/env python3
"""
清理 OCR 缓存脚本：删除命中率低于前 50 名的缓存条目
"""

import os
import sqlite3
import sys
from pathlib import Path


def cleanup_low_hitrate_cache(cache_dir="output/cache", top_n=50):
    """
    删除命中率低于前 N 名的缓存条目
    
    Args:
        cache_dir (str): 缓存目录路径
        top_n (int): 保留命中率最高的前 N 个条目，默认 50
    """
    print("=" * 70)
    print(f"清理 OCR 缓存：删除命中率低于前 {top_n} 名的条目")
    print("=" * 70)
    
    db_path = os.path.join(cache_dir, "cache.db")
    
    if not os.path.exists(db_path):
        print(f"❌ 缓存数据库不存在: {db_path}")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 获取总缓存条目数
            cursor.execute("SELECT COUNT(*) FROM cache_entries")
            total_count = cursor.fetchone()[0]
            print(f"\n📊 缓存统计:")
            print(f"  - 总条目数: {total_count}")
            
            if total_count == 0:
                print("  - 缓存为空，无需清理")
                return True
            
            # 2. 获取前 N 名的命中率阈值
            cursor.execute(f"""
                SELECT hit_count FROM cache_entries
                ORDER BY hit_count DESC
                LIMIT 1 OFFSET {top_n - 1}
            """)
            result = cursor.fetchone()
            
            if result is None:
                # 缓存条目少于 top_n
                threshold = 0
                print(f"  - 缓存条目少于 {top_n}，将保留所有条目")
                return True
            
            threshold = result[0]
            print(f"  - 前 {top_n} 名的命中率阈值: {threshold}")
            
            # 3. 获取要删除的条目
            cursor.execute(f"""
                SELECT id, image_path, json_path, hit_count
                FROM cache_entries
                WHERE hit_count < ?
                ORDER BY hit_count ASC
            """, (threshold,))
            
            to_delete = cursor.fetchall()
            delete_count = len(to_delete)
            
            if delete_count == 0:
                print(f"  - 无需删除的条目")
                return True
            
            print(f"\n🗑️ 待删除条目:")
            print(f"  - 数量: {delete_count}")
            
            # 统计要删除的文件大小
            total_size = 0
            for entry_id, img_path, json_path, hit_count in to_delete:
                if os.path.exists(img_path):
                    total_size += os.path.getsize(img_path)
                if os.path.exists(json_path):
                    total_size += os.path.getsize(json_path)
            
            print(f"  - 总大小: {total_size / 1024 / 1024:.2f} MB")
            
            # 4. 显示前 10 个要删除的条目
            print(f"\n📋 前 10 个要删除的条目:")
            for i, (entry_id, img_path, json_path, hit_count) in enumerate(to_delete[:10]):
                print(f"  {i+1}. hit_count={hit_count}, image={os.path.basename(img_path)}")
            
            if delete_count > 10:
                print(f"  ... 还有 {delete_count - 10} 个条目")
            
            # 5. 确认删除
            print(f"\n⚠️ 确认删除 {delete_count} 个缓存条目? (y/n): ", end="")
            response = input().strip().lower()
            
            if response != 'y':
                print("❌ 已取消删除操作")
                return False
            
            # 6. 执行删除
            print(f"\n🔄 正在删除缓存条目...")
            deleted_files = 0
            failed_files = 0
            
            for entry_id, img_path, json_path, hit_count in to_delete:
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                        deleted_files += 1
                    if os.path.exists(json_path):
                        os.remove(json_path)
                        deleted_files += 1
                except Exception as e:
                    print(f"  ⚠️ 删除失败: {img_path} - {e}")
                    failed_files += 1
            
            # 7. 从数据库删除记录
            cursor.execute(f"""
                DELETE FROM cache_entries
                WHERE hit_count < ?
            """, (threshold,))
            
            conn.commit()
            
            # 8. 显示结果
            print(f"\n✅ 删除完成:")
            print(f"  - 删除的文件: {deleted_files}")
            print(f"  - 删除失败: {failed_files}")
            print(f"  - 删除的数据库记录: {delete_count}")
            
            # 9. 显示清理后的统计
            cursor.execute("SELECT COUNT(*) FROM cache_entries")
            remaining_count = cursor.fetchone()[0]
            print(f"\n📊 清理后统计:")
            print(f"  - 剩余条目数: {remaining_count}")
            print(f"  - 删除比例: {delete_count / total_count * 100:.1f}%")
            
            return True
            
    except Exception as e:
        print(f"❌ 清理缓存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 支持命令行参数
    top_n = 50
    cache_dir = "output/cache"
    
    if len(sys.argv) > 1:
        try:
            top_n = int(sys.argv[1])
        except ValueError:
            print(f"❌ 无效的参数: {sys.argv[1]}")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        cache_dir = sys.argv[2]
    
    success = cleanup_low_hitrate_cache(cache_dir, top_n)
    sys.exit(0 if success else 1)

