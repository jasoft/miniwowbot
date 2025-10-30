# 定时任务管理脚本更新总结

## 📋 更新内容

`manage_dungeons_schedule.sh` 脚本已更新，现在支持使用 `--parallel` 参数运行副本任务。

---

## ✅ 主要改动

### 1. 新增 `install` 命令

**功能**：安装定时任务（使用 launchd + --parallel）

**使用方法**：
```bash
./manage_dungeons_schedule.sh install
```

**说明**：
- 创建 launchd 配置文件
- 配置每天早上 6:05 自动运行副本（并行模式）
- 配置每天凌晨 2:00 自动清理旧日志
- 自动加载任务

### 2. 更新 `test` 命令

**改进**：现在使用 `--parallel` 参数运行副本任务

**使用方法**：
```bash
./manage_dungeons_schedule.sh test
```

**说明**：
- 直接调用 `cron_run_all_dungeons.sh --parallel`
- 支持并行运行多个账号
- 实时显示运行日志

### 3. 更新帮助信息

**新增命令说明**：
- `install` - 安装定时任务（使用 launchd + --parallel）
- `test` - 手动运行一次副本任务（使用 --parallel）

---

## 🔧 技术细节

### launchd 配置

新的 launchd 配置使用以下参数：

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>/Users/weiwang/Projects/异世界勇者.air/helper/cron_run_all_dungeons.sh --parallel</string>
</array>
```

**优势**：
- ✅ 支持并行运行多个账号
- ✅ 提高运行效率
- ✅ 减少总运行时间

### 日志配置

```xml
<key>StandardOutPath</key>
<string>/Users/weiwang/cron_logs/launchd_dungeons_stdout.log</string>
<key>StandardErrorPath</key>
<string>/Users/weiwang/cron_logs/launchd_dungeons_stderr.log</string>
```

**说明**：
- 标准输出日志：`launchd_dungeons_stdout.log`
- 标准错误日志：`launchd_dungeons_stderr.log`
- 账号日志：`account_{phone}_{timestamp}.log`

---

## 📝 使用指南

### 首次安装

```bash
# 1. 安装定时任务
./manage_dungeons_schedule.sh install

# 2. 检查状态
./manage_dungeons_schedule.sh status

# 3. 手动测试
./manage_dungeons_schedule.sh test
```

### 日常操作

```bash
# 查看任务状态
./manage_dungeons_schedule.sh status

# 查看最近的日志
./manage_dungeons_schedule.sh logs

# 手动运行一次
./manage_dungeons_schedule.sh test

# 停止任务
./manage_dungeons_schedule.sh stop

# 重启任务
./manage_dungeons_schedule.sh restart

# 清理旧日志
./manage_dungeons_schedule.sh clean-logs
```

### 卸载任务

```bash
./manage_dungeons_schedule.sh uninstall
```

---

## 🚀 并行运行的优势

### 性能提升

| 指标 | 顺序模式 | 并行模式 |
|------|--------|--------|
| 运行时间 | 较长 | 较短 |
| 资源利用 | 低 | 高 |
| 账号数量 | 1 个 | 多个 |

### 并行参数说明

`--parallel` 参数会：
- ✅ 同时启动多个模拟器
- ✅ 并行加载多个账号
- ✅ 并行运行多个副本脚本
- ✅ 减少总运行时间

---

## 📊 文件变更

| 文件 | 变更 | 说明 |
|------|------|------|
| `manage_dungeons_schedule.sh` | 修改 | 添加 install 命令，更新 test 命令 |

---

## ✨ 总结

✅ **定时任务管理脚本已成功更新！**

**关键改进**：
- ✅ 新增 `install` 命令，一键安装定时任务
- ✅ 更新 `test` 命令，支持 `--parallel` 参数
- ✅ 自动配置 launchd 使用并行模式
- ✅ 改进日志管理和清理

**现在可以**：
- ✅ 一键安装定时任务
- ✅ 每天早上 6:05 自动运行副本（并行模式）
- ✅ 手动测试副本任务（并行模式）
- ✅ 自动清理旧日志

---

## 📞 常见问题

### Q: 如何验证定时任务是否正确安装？

A: 运行以下命令：
```bash
./manage_dungeons_schedule.sh status
```

### Q: 如何查看运行日志？

A: 运行以下命令：
```bash
./manage_dungeons_schedule.sh logs
```

### Q: 如何手动运行一次副本任务？

A: 运行以下命令：
```bash
./manage_dungeons_schedule.sh test
```

### Q: 如何卸载定时任务？

A: 运行以下命令：
```bash
./manage_dungeons_schedule.sh uninstall
```

---

## 📚 相关文件

- `manage_dungeons_schedule.sh` - 定时任务管理脚本
- `cron_run_all_dungeons.sh` - 副本运行脚本（支持 --parallel 参数）
- `auto_dungeon.py` - 副本自动化脚本


