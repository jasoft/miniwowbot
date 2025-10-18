# 优雅停止执行指南

## 问题描述

当 `auto_dungeon.py` 在 cron 任务或后台运行时，无法使用 `Ctrl+C` 中断执行。如果需要停止正在运行的脚本，需要一个优雅的停止机制。

## 解决方案

已实现基于"停止信号文件"的优雅停止机制。脚本会在每个副本开始前检查停止信号，如果检测到停止信号，会在当前副本完成后优雅地退出。

## 停止机制工作原理

### 1. 停止信号文件
- 文件名: `.stop_dungeon`
- 位置: 项目根目录
- 作用: 当此文件存在时，脚本会在下一个副本开始前停止执行

### 2. 检查时机
脚本在以下时机检查停止信号：
- 每个副本开始前
- 确保当前副本能够完成，不会中途中断

### 3. 停止流程
1. 检测到停止文件
2. 显示停止信息和统计
3. 返回游戏主界面
4. 删除停止文件
5. 优雅退出

## 使用方法

### 方法 1: 使用停止脚本（推荐）

```bash
# 停止正在运行的 auto_dungeon.py
./stop_dungeon.sh
```

脚本会：
1. ✓ 检测正在运行的进程
2. ✓ 创建停止信号文件
3. ✓ 等待进程优雅停止（最多 30 秒）
4. ✓ 显示停止状态
5. ✓ 自动清理停止文件

**输出示例**:
```
========================================
停止 Auto Dungeon 执行
========================================

✓ 检测到正在运行的 auto_dungeon.py 进程

创建停止信号文件: .stop_dungeon
✓ 停止信号已发送

📝 脚本将在当前副本完成后优雅停止
⏳ 请等待几秒钟...

......
✅ 进程已成功停止
========================================
```

### 方法 2: 手动创建停止文件

```bash
# 在项目根目录创建停止文件
touch .stop_dungeon
```

脚本会在下一个副本开始前检测到并停止。

### 方法 3: Python 命令

```bash
# 使用 Python 创建停止文件
python3 -c "open('.stop_dungeon', 'w').close()"
```

### 方法 4: 远程停止（SSH）

```bash
# 通过 SSH 连接到服务器后
cd /path/to/project
./stop_dungeon.sh

# 或者
cd /path/to/project
touch .stop_dungeon
```

## 脚本输出示例

当检测到停止信号时，[`auto_dungeon.py`](../auto_dungeon.py:63) 会显示：

```
⛔ 检测到停止信号文件: .stop_dungeon
⛔ 正在优雅地停止执行...
✅ 已删除停止信号文件

📊 统计: 本次运行完成 5 个副本
👋 已停止执行
```

## 代码实现

### 检查函数

在 [`auto_dungeon.py`](../auto_dungeon.py:63) 中实现：

```python
STOP_FILE = ".stop_dungeon"  # 停止标记文件路径

def check_stop_signal():
    """
    检查是否存在停止信号文件

    Returns:
        bool: 如果存在停止文件返回 True，否则返回 False
    """
    if os.path.exists(STOP_FILE):
        logger.warning(f"\n⛔ 检测到停止信号文件: {STOP_FILE}")
        logger.warning("⛔ 正在优雅地停止执行...")
        # 删除停止文件
        try:
            os.remove(STOP_FILE)
            logger.info("✅ 已删除停止信号文件")
        except Exception as e:
            logger.error(f"❌ 删除停止文件失败: {e}")
        return True
    return False
```

### 主循环集成

在副本循环中的集成点：

```python
# 遍历副本
for dungeon_dict in dungeons:
    # 在每个副本开始前检查停止信号
    if check_stop_signal():
        logger.info(f"\n📊 统计: 本次运行完成 {processed_dungeons} 个副本")
        logger.info("👋 已停止执行")
        back_to_main()
        return

    # 继续处理副本...
```

## 强制停止（不推荐）

如果优雅停止失败或需要立即停止：

```bash
# 查找进程 ID
ps aux | grep auto_dungeon.py

# 强制停止（使用进程 ID）
kill -9 <PID>

# 或者使用 pkill
pkill -9 -f auto_dungeon.py
```

**注意**: 强制停止可能导致：
- 游戏停留在非主界面状态
- 数据库连接未正确关闭
- 临时文件未清理

## 在 Cron 中使用

### Cron 任务设置

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨2点运行）
0 2 * * * cd /path/to/project && ./run_all_dungeons.sh >> logs/cron.log 2>&1
```

### 停止 Cron 任务

```bash
# 方法 1: 使用停止脚本
cd /path/to/project
./stop_dungeon.sh

# 方法 2: 手动创建停止文件
cd /path/to/project
touch .stop_dungeon

# 方法 3: 远程 SSH
ssh user@server "cd /path/to/project && ./stop_dungeon.sh"
```

## 监控和日志

### 查看运行状态

```bash
# 检查进程是否运行
ps aux | grep auto_dungeon.py

# 或使用 pgrep
pgrep -f auto_dungeon.py

# 查看实时日志（如果有日志文件）
tail -f logs/cron.log
```

### 检查停止文件

```bash
# 检查停止文件是否存在
ls -la .stop_dungeon

# 清理残留的停止文件
rm -f .stop_dungeon
```

## 最佳实践

### 1. 使用停止脚本
始终使用 [`stop_dungeon.sh`](../stop_dungeon.sh:1) 而不是手动创建文件或强制停止。

### 2. 等待优雅停止
给脚本足够的时间完成当前副本（通常 1-2 分钟）。

### 3. 检查日志
停止后检查日志确认脚本正确退出。

### 4. 清理环境
如果强制停止，手动清理：
```bash
# 清理停止文件
rm -f .stop_dungeon

# 返回游戏主界面
# （需要手动操作或运行简单的返回脚本）
```

### 5. 定期监控
在 cron 任务中添加监控：
```bash
# 监控脚本（可选）
0 */4 * * * /path/to/check_status.sh
```

## 故障排除

### 1. 停止脚本无响应

**原因**: 进程可能卡住或崩溃

**解决方案**:
```bash
# 强制停止
pkill -9 -f auto_dungeon.py

# 清理停止文件
rm -f .stop_dungeon
```

### 2. 停止文件一直存在

**原因**: 脚本未正确删除文件

**解决方案**:
```bash
# 手动删除
rm -f .stop_dungeon

# 检查进程状态
ps aux | grep auto_dungeon.py
```

### 3. 停止后游戏状态异常

**原因**: 停止时机不当或强制停止

**解决方案**:
- 手动返回游戏主界面
- 重启游戏
- 下次运行会自动恢复

### 4. Cron 任务中无法停止

**原因**: 权限或路径问题

**解决方案**:
```bash
# 使用绝对路径
cd /absolute/path/to/project
./stop_dungeon.sh

# 或者
touch /absolute/path/to/project/.stop_dungeon
```

## 自动化示例

### 定时停止任务

```bash
#!/bin/bash
# auto_stop.sh - 在指定时间自动停止

TARGET_HOUR=8  # 早上8点停止

current_hour=$(date +%H)

if [ $current_hour -ge $TARGET_HOUR ]; then
    cd /path/to/project
    ./stop_dungeon.sh
    echo "$(date): 自动停止执行" >> logs/auto_stop.log
fi
```

### Cron 定时停止

```bash
# 每天早上8点自动停止
0 8 * * * cd /path/to/project && ./stop_dungeon.sh
```

## 相关文件

- 主脚本: [`auto_dungeon.py`](../auto_dungeon.py:1)
- 停止脚本: [`stop_dungeon.sh`](../stop_dungeon.sh:1)
- 停止检查函数: [`auto_dungeon.py:check_stop_signal()`](../auto_dungeon.py:63)
- Cron 运行脚本: [`cron_run_all_dungeons.sh`](../cron_run_all_dungeons.sh:1)

## 安全注意事项

1. **不要在副本进行中强制停止** - 可能导致游戏状态异常
2. **使用优雅停止** - 始终优先使用停止信号机制
3. **检查进程状态** - 停止后确认进程已完全退出
4. **清理残留文件** - 定期检查并清理 `.stop_dungeon` 文件
5. **日志监控** - 保留停止操作的日志记录

## 扩展功能

如果需要更多控制，可以扩展停止机制：

### 暂停/恢复功能

```python
PAUSE_FILE = ".pause_dungeon"

def check_pause_signal():
    while os.path.exists(PAUSE_FILE):
        logger.info("⏸️  已暂停，等待恢复...")
        time.sleep(5)
```

### 远程控制接口

可以考虑添加 HTTP API 或 WebSocket 接口实现远程控制。

## 总结

优雅停止机制提供了一个安全、可靠的方式来中断长时间运行的 cron 任务，避免了强制停止可能带来的问题。使用 [`stop_dungeon.sh`](../stop_dungeon.sh:1) 脚本是最推荐的停止方法。
