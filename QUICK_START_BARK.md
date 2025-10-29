# Bark 通知快速开始

## 3 步启用 Bark 通知

### 1️⃣ 获取设备密钥
- 在 iPhone 上安装 Bark 应用
- 打开应用，复制设备密钥

### 2️⃣ 配置 system_config.json
```bash
# 编辑配置文件
nano system_config.json
```

修改为：
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

将 `{device_key}` 替换为实际的设备密钥。

### 3️⃣ 测试通知
```bash
# 测试成功通知
python3 send_cron_notification.py 5 0 5

# 测试失败通知
python3 send_cron_notification.py 3 2 5
```

## 完成！

Cron 任务完成后会自动发送 Bark 通知到你的 iPhone。

## 常见问题

**Q: 通知没有收到？**
A: 检查 `system_config.json` 中 `enabled` 是否为 `true`，以及设备密钥是否正确。

**Q: 如何禁用通知？**
A: 将 `system_config.json` 中的 `enabled` 改为 `false`。

**Q: 如何查看日志？**
A: 查看 `~/cron_logs/dungeons_*.log` 文件。

## 更多信息

详见 `CRON_BARK_NOTIFICATION_GUIDE.md`

