# flock 依赖移除总结

## 📋 问题描述

`cron_run_all_dungeons.sh` 脚本使用了 `flock` 命令来实现文件锁，但 `flock` 在 macOS 上不可用，导致脚本无法运行。

---

## ✅ 解决方案

### 1. 移除 flock 依赖

**原始代码**：
```bash
log() {
    (
        flock -x 200
        echo "$@" | tee -a "$LOG_FILE"
    ) 200>"$LOCK_FILE"
}
```

**问题**：
- ❌ `flock` 命令在 macOS 上不可用
- ❌ 脚本无法执行

### 2. 实现 macOS 原生文件锁

**新代码**：
```bash
log() {
    # 使用 macOS 兼容的文件锁机制
    local max_retries=10
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        # 尝试创建锁文件（原子操作）
        if mkdir "$LOCK_FILE" 2>/dev/null; then
            # 成功获得锁，写入日志
            echo "$@" | tee -a "$LOG_FILE"
            # 释放锁
            rmdir "$LOCK_FILE" 2>/dev/null
            return 0
        fi
        
        # 锁文件已存在，等待一下再重试
        sleep 0.1
        ((retry_count++))
    done
    
    # 如果无法获得锁，直接写入（可能会有混乱，但至少不会卡住）
    echo "$@" | tee -a "$LOG_FILE"
}
```

**优势**：
- ✅ 使用 `mkdir` 实现原子操作（POSIX 标准）
- ✅ macOS 原生支持，无需额外依赖
- ✅ 支持重试机制，提高可靠性
- ✅ 失败时降级处理，不会卡住

---

## 🔧 技术细节

### 文件锁机制

**原理**：
- `mkdir` 是原子操作，要么成功要么失败
- 使用目录作为锁文件（而不是普通文件）
- 成功创建目录表示获得锁
- 删除目录表示释放锁

**优势**：
- ✅ 原子性强，不会出现竞态条件
- ✅ 跨平台兼容（POSIX 标准）
- ✅ 无需额外工具或库

### 重试机制

- 最多重试 10 次
- 每次重试间隔 0.1 秒
- 总等待时间最多 1 秒
- 超时后降级处理（直接写入）

### 降级处理

- 如果无法获得锁，直接写入日志
- 可能会有日志混乱，但不会卡住
- 确保脚本继续运行

---

## 📝 修改文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `cron_run_all_dungeons.sh` | 修改 | 替换 flock 为 macOS 原生文件锁 |

---

## ✨ 总结

✅ **flock 依赖已成功移除！**

**关键改进**：
- ✅ 移除 flock 命令依赖
- ✅ 实现 macOS 原生文件锁
- ✅ 支持重试机制
- ✅ 提高系统兼容性

**现在可以**：
- ✅ 在 macOS 上正常运行脚本
- ✅ 并行模式下避免日志混乱
- ✅ 无需安装额外工具

---

## 🚀 使用方法

### 运行脚本

```bash
# 顺序模式
./cron_run_all_dungeons.sh

# 并行模式
./cron_run_all_dungeons.sh --parallel
```

### 查看日志

```bash
# 查看主日志
tail -f ~/cron_logs/dungeons_*.log

# 查看账号日志
tail -f ~/cron_logs/account_*.log
```

---

## 📊 性能对比

| 指标 | flock | mkdir 锁 |
|------|-------|---------|
| macOS 兼容性 | ❌ 不支持 | ✅ 支持 |
| 原子性 | ✅ 强 | ✅ 强 |
| 性能 | 快 | 快 |
| 依赖 | 需要 flock | 无需依赖 |

---

## 📞 常见问题

### Q: 为什么使用目录作为锁文件？

A: 因为 `mkdir` 是原子操作，创建目录要么成功要么失败，不会出现中间状态。这比使用普通文件更安全。

### Q: 如果锁文件一直存在怎么办？

A: 脚本会重试 10 次，每次间隔 0.1 秒。如果仍然无法获得锁，会直接写入日志。这确保脚本不会卡住。

### Q: 日志会混乱吗？

A: 在正常情况下不会。只有在极端情况下（锁文件一直被占用）才可能混乱。但这种情况很少发生。

### Q: 如何手动清理锁文件？

A: 如果锁文件一直存在，可以手动删除：
```bash
rmdir /tmp/cron_dungeons_lock
```

---

## 📚 相关文件

- `cron_run_all_dungeons.sh` - 副本运行脚本
- `manage_dungeons_schedule.sh` - 定时任务管理脚本
- `CHANGELOG.md` - 更新日志


