# Bark 通知配置指南

本文档介绍如何配置和使用 Bark 通知功能，在副本执行超时时接收手机通知。

## 功能说明

当 `wait_for_main()` 函数等待战斗结束超过配置的超时时间（默认 5 分钟）时，系统会：

1. 中断当前执行
2. 通过 Bark 发送通知到你的 iOS 设备
3. 记录详细的错误日志

## 配置步骤

### 1. 安装 Bark App

在 iOS App Store 搜索并下载 "Bark - 给自己的推送" 应用。

### 2. 获取 Device Key

打开 Bark App，你会看到类似这样的推送 URL：

```
https://api.day.app/your_device_key/
```

复制你的 `your_device_key` 部分。

### 3. 配置本地环境变量

在项目根目录创建本地 `.env` 文件（该文件已被 Git 忽略）：

```dotenv
BARK_ENABLED=true
BARK_SERVER=https://api.day.app/your_device_key/
BARK_TITLE=副本助手通知
BARK_GROUP=dungeon_helper
```

**配置说明：**

- `BARK_ENABLED`: 是否启用 Bark 通知（`true` 启用，`false` 禁用）
- `BARK_SERVER`: Bark 服务器地址，替换 `your_device_key` 为你的实际 Device Key
- `BARK_TITLE`: 通知标题（可选，默认为 "副本助手通知"）
- `BARK_GROUP`: 通知分组（可选，用于在 Bark 中分组显示）
- `timeout.wait_for_main`: 等待主界面的超时时间（秒），默认 300 秒（5 分钟）

敏感的 Device Key 只允许保存在本机 `.env` 或部署平台的密钥管理中，不能写入
`system_config.json`、源码、测试数据或 GitHub Actions 日志。

### 4. 测试通知功能

运行测试脚本验证配置是否正确：

```bash
python test_bark_notification.py
```

如果配置正确，你的 iOS 设备应该会收到一条测试通知。

## 使用场景

### 超时通知

当副本战斗时间超过配置的超时时间时，你会收到通知：

```
标题: 副本助手 - 超时警告
内容: 战斗超时（305.2秒 > 300秒），可能卡住了
```

### 停止信号通知

当检测到停止信号文件时，你会收到通知：

```
标题: 副本助手
内容: 收到停止信号，已中断执行
```

### 错误通知

当等待主界面时发生错误，你会收到通知：

```
标题: 副本助手 - 错误
内容: 等待主界面时出错: [错误详情]
```

## 自定义配置

### 修改超时时间

如果你的设备性能较慢，可以增加超时时间（单位：秒）：

```json
{
    "timeout": {
        "wait_for_main": 600
    }
}
```

### 自定义通知标题和分组

```dotenv
BARK_ENABLED=true
BARK_SERVER=https://api.day.app/your_device_key/
BARK_TITLE=游戏助手
BARK_GROUP=game_automation
```

### 使用自建 Bark 服务器

如果你搭建了自己的 Bark 服务器：

```dotenv
BARK_ENABLED=true
BARK_SERVER=https://your-bark-server.com/your_device_key/
BARK_TITLE=副本助手通知
BARK_GROUP=dungeon_helper
```

## 通知级别

系统会根据通知类型设置不同的级别：

- `timeSensitive`: 超时警告、停止信号、错误通知（会立即显示和播放声音）
- `active`: 普通通知（默认行为）
- `passive`: 静默通知（不会打断用户）

## 故障排查

### 收不到通知？

1. **检查 Bark App 是否正常运行**
   - 打开 Bark App，确保没有错误提示

2. **检查 Device Key 是否正确**
   - 在本机 `.env` 中确认 `BARK_SERVER` 地址正确

3. **检查网络连接**
   - 确保设备可以访问 Bark 服务器

4. **查看日志**
   - 运行测试脚本查看详细错误信息：
     ```bash
     python test_bark_notification.py
     ```

5. **检查配置是否已启用**
   - 确认 `.env` 中 `BARK_ENABLED=true`

### 测试脚本报错？

如果测试脚本报错 "未找到 requests 模块"，请安装依赖：

```bash
pip install requests
```

或使用 uv：

```bash
uv pip install requests
```

## 注意事项

1. **隐私安全**：Device Key 是私密信息，不要分享给他人
2. **通知频率**：避免过于频繁的通知，以免影响使用体验
3. **网络依赖**：Bark 通知需要网络连接，离线时无法发送
4. **iOS 专属**：Bark 目前仅支持 iOS 系统

## 相关文件

- `.env`: 本机私有通知配置（不会提交到 Git）
- `.env.example`: 不含密钥的配置模板
- `system_config_loader.py`: 系统配置加载器
- `test_bark_notification.py`: Bark 通知测试脚本
- `auto_dungeon.py`: 主程序（包含通知发送逻辑）

## 更多信息

- Bark 官方仓库：https://github.com/Finb/Bark
- Bark App Store：https://apps.apple.com/cn/app/bark-customed-notifications/id1403753865
