# Cron 任务 Bark 通知指南

## 功能概述

在 cron 任务完成后，自动发送 Bark 通知，包括执行结果统计（成功/失败账号数）。

## 实现方案

### 1. 新建脚本：`send_cron_notification.py`

独立的 Python 脚本，用于发送 Bark 通知：
- 从 shell 脚本调用，接收成功/失败/总数参数
- 自动从 `system_config.json` 读取 Bark API 配置
- 支持不同的通知级别（失败时使用 `timeSensitive`，成功时使用 `active`）

### 2. 修改脚本：`cron_run_all_dungeons.sh`

在任务完成后添加以下逻辑：
```bash
# 发送 Bark 通知
log ""
log "📱 发送 Bark 通知..."
uv run send_cron_notification.py "$success_count" "$failed_count" "$ACCOUNT_COUNT" 2>&1 | tee -a "$LOG_FILE"
if [ $? -eq 0 ]; then
    log "✅ Bark 通知发送成功"
else
    log "⚠️ Bark 通知发送失败或未启用"
fi
```

## 使用方式

### 1. 启用 Bark 通知

编辑 `system_config.json`，设置：
```json
{
    "bark": {
        "enabled": true,
        "server": "https://api.day.app/{device_key}/",
        "title": "异世界勇者 - 副本助手通知",
        "group": "dungeon_helper"
    }
}
```

**参数说明：**
- `enabled`: 是否启用 Bark 通知（true/false）
- `server`: Bark API 服务器地址，包含设备密钥
- `title`: 通知标题前缀（可选）
- `group`: 通知分组（可选）

### 2. 手动测试

```bash
# 测试成功通知（5个账号全部成功）
python3 send_cron_notification.py 5 0 5

# 测试失败通知（5个账号中3个成功，2个失败）
python3 send_cron_notification.py 3 2 5
```

### 3. 查看日志

Cron 任务的日志保存在 `~/cron_logs/` 目录下，文件名格式为 `dungeons_YYYY-MM-DD_HH-MM-SS.log`

## 通知内容示例

### 成功通知
- **标题**：异世界勇者 - 副本运行成功
- **内容**：
  ```
  副本运行完成
  总计: 5 个账号
  ✅ 全部成功: 5 个
  ```
- **级别**：active

### 失败通知
- **标题**：异世界勇者 - 副本运行失败
- **内容**：
  ```
  副本运行完成
  总计: 5 个账号
  ✅ 成功: 3 个
  ❌ 失败: 2 个
  ```
- **级别**：timeSensitive

## 相关文件

| 文件 | 说明 |
|------|------|
| `send_cron_notification.py` | 新建 - 发送 Bark 通知的脚本 |
| `cron_run_all_dungeons.sh` | 修改 - 添加 Bark 通知调用 |
| `system_config.json` | 配置文件 - 需要启用 Bark |
| `test_cron_notification.py` | 新建 - 测试脚本 |

## 故障排查

### 通知未发送

1. **检查 Bark 是否启用**
   ```bash
   grep -A 5 '"bark"' system_config.json
   ```

2. **检查 API 地址是否正确**
   - 确保 `server` 字段包含有效的设备密钥
   - 格式应为：`https://api.day.app/{device_key}/`

3. **检查网络连接**
   ```bash
   curl -I https://api.day.app/
   ```

4. **查看日志**
   ```bash
   tail -f ~/cron_logs/dungeons_*.log
   ```

### 脚本执行失败

1. **检查 Python 依赖**
   ```bash
   python3 -c "import requests; print('✅ requests 已安装')"
   ```

2. **检查脚本权限**
   ```bash
   chmod +x send_cron_notification.py
   ```

3. **手动测试脚本**
   ```bash
   python3 send_cron_notification.py 5 0 5
   ```

## 技术细节

### 参数说明

脚本接收三个参数：
1. `success_count` - 成功的账号数
2. `failed_count` - 失败的账号数
3. `total_count` - 总账号数

### 返回值

- `0` - 通知发送成功或未启用（正常情况）
- `1` - 通知发送失败

### 通知级别

- `active` - 普通通知（成功时使用）
- `timeSensitive` - 时间敏感通知，优先级更高（失败时使用）
- `passive` - 被动通知，不会打断用户

## 集成到 Cron 任务

Cron 任务会自动调用 `cron_run_all_dungeons.sh` 脚本，该脚本会在完成后自动发送 Bark 通知。

无需额外配置，只需确保：
1. `system_config.json` 中启用了 Bark
2. 配置了正确的 API 地址和设备密钥

