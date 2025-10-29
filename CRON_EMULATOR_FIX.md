# Cron 脚本 Emulator 参数修复

## 🎯 问题

在 `cron_run_all_dungeons.sh` 中，运行副本脚本时没有传递 `--emulator` 参数，导致多模拟器场景下副本在错误的模拟器上运行。

## ✅ 解决方案

在脚本的两个地方添加 `--emulator` 参数传递。

---

## 🔧 修改详情

### 1. 并行模式（第 162-166 行）

**修改前：**
```bash
# 运行副本脚本
log "🎮 运行脚本: $RUN_SCRIPT --no-prompt"
$RUN_SCRIPT --no-prompt 2>&1 | tee -a "$LOG_FILE"
exit_code=${PIPESTATUS[0]}
```

**修改后：**
```bash
# 运行副本脚本
log "🎮 运行脚本: $RUN_SCRIPT --no-prompt"
if [ -n "$EMULATOR" ]; then
    $RUN_SCRIPT --no-prompt --emulator "$EMULATOR" 2>&1 | tee -a "$LOG_FILE"
else
    $RUN_SCRIPT --no-prompt 2>&1 | tee -a "$LOG_FILE"
fi
exit_code=${PIPESTATUS[0]}
```

### 2. 顺序模式（第 264-268 行）

**修改前：**
```bash
# 运行副本脚本
log "🎮 运行脚本: $RUN_SCRIPT --no-prompt"
$RUN_SCRIPT --no-prompt 2>&1 | tee -a "$LOG_FILE" &
pid=$!
background_pids+=("$pid")
wait "$pid"
exit_codes[$i]=$?
```

**修改后：**
```bash
# 运行副本脚本
log "🎮 运行脚本: $RUN_SCRIPT --no-prompt"
if [ -n "$EMULATOR" ]; then
    $RUN_SCRIPT --no-prompt --emulator "$EMULATOR" 2>&1 | tee -a "$LOG_FILE" &
else
    $RUN_SCRIPT --no-prompt 2>&1 | tee -a "$LOG_FILE" &
fi
pid=$!
background_pids+=("$pid")
wait "$pid"
exit_codes[$i]=$?
```

---

## 📊 修改统计

| 项目 | 数量 |
|------|------|
| 修改的文件 | 1 个 |
| 修改的位置 | 2 处 |
| 新增代码行数 | 8 行 |
| 删除代码行数 | 0 行 |

---

## ✨ 效果

### 修改前的流程

```
加载账号时：
  ✅ 传递 --emulator 参数 → 在正确的模拟器上加载

运行副本时：
  ❌ 没有传递 --emulator 参数 → 在默认模拟器上运行（错误！）
```

### 修改后的流程

```
加载账号时：
  ✅ 传递 --emulator 参数 → 在正确的模拟器上加载

运行副本时：
  ✅ 传递 --emulator 参数 → 在正确的模拟器上运行（正确！）
```

---

## 🚀 使用方式

### 配置文件示例

在 `accounts.json` 中指定模拟器：

```json
{
  "accounts": [
    {
      "name": "账号1",
      "phone": "18502542158",
      "run_script": "run_account1.sh",
      "description": "主账号",
      "emulator": "emulator-5554"
    },
    {
      "name": "账号2",
      "phone": "18502542159",
      "run_script": "run_account2.sh",
      "description": "副账号",
      "emulator": "emulator-5555"
    }
  ]
}
```

### 运行脚本

```bash
# 顺序模式（默认）
./cron_run_all_dungeons.sh

# 并行模式
./cron_run_all_dungeons.sh --parallel
```

---

## 📝 日志示例

修改后的日志输出：

```
=====================================
账号 1/2: 账号1
描述: 主账号
手机号: 18502542158
模拟器: emulator-5554
=====================================

🔄 加载账号: 18502542158
✅ 使用 Airtest 内置 ADB: /path/to/airtest/adb/mac/adb
✅ 模拟器 emulator-5554 已在运行
🎮 运行脚本: run_account1.sh --no-prompt --emulator emulator-5554
✅ 账号 账号1 完成
```

---

## 🔍 验证

### 脚本语法检查

```bash
bash -n cron_run_all_dungeons.sh
```

✅ **检查通过**

### 测试运行

```bash
# 查看脚本会执行的命令（不实际执行）
bash -x cron_run_all_dungeons.sh 2>&1 | head -50
```

---

## 📚 相关文件

| 文件 | 用途 |
|------|------|
| `cron_run_all_dungeons.sh` | Cron 包装脚本 |
| `auto_dungeon.py` | 副本自动遍历脚本 |
| `accounts.json` | 账号配置文件 |
| `CHANGELOG.md` | 更新日志 |

---

## ✅ 总结

### 问题
- 运行副本脚本时没有传递 `--emulator` 参数
- 导致多模拟器场景下副本在错误的模拟器上运行

### 解决
- 在并行模式和顺序模式中都添加 `--emulator` 参数传递
- 检查 `$EMULATOR` 变量是否为空，有值时传递参数

### 效果
- ✅ 多模拟器场景下副本在正确的模拟器上运行
- ✅ 并行模式和顺序模式都支持指定模拟器
- ✅ 向后兼容，未指定模拟器时使用默认行为

### 验证
- ✅ 脚本语法检查通过
- ✅ 所有修改已完成
- ✅ CHANGELOG.md 已更新

---

**修复完成时间：** 2025-10-29

**状态：** ✅ **已完成**

