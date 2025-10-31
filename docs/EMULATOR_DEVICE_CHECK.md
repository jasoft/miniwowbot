# 模拟器设备检查功能

## 功能概述

为 `auto_dungeon.py` 添加了模拟器设备列表检查功能，在指定模拟器不存在时立即报错并发送 Bark 通知。

## 工作原理

### 检查流程

1. **获取设备列表**
   - 调用 `EmulatorManager.get_adb_devices()` 获取所有已连接的 ADB 设备
   - 返回格式：`{device_name: status}` 字典

2. **验证模拟器存在**
   - 检查指定的 `emulator_name` 是否在设备列表中
   - 如果不存在，立即报错并退出

3. **发送通知**
   - 使用 `send_bark_notification()` 发送 Bark 通知
   - 通知级别设置为 `timeSensitive`（紧急）
   - 通知内容包含错误信息和可用设备列表

### 检查位置

在以下三个关键函数中添加了设备检查：

1. **`check_and_start_emulator(emulator_name)`**
   - 在启动模拟器前检查
   - 如果检查失败，返回 `False`

2. **`handle_load_account_mode(account_name, emulator_name)`**
   - 在加载账号前检查
   - 如果检查失败，调用 `sys.exit(1)` 退出

3. **`initialize_device_and_ocr(emulator_name)`**
   - 在初始化设备前检查
   - 如果检查失败，抛出 `RuntimeError` 异常

## 使用示例

### 正常使用（模拟器存在）

```bash
# 指定存在的模拟器
uv run auto_dungeon.py --emulator emulator-5554

# 输出：
# 📱 连接到模拟器: emulator-5554
# 连接字符串: Android://127.0.0.1:5555/emulator-5554
# ✅ 成功连接到设备
```

### 错误使用（模拟器不存在）

```bash
# 指定不存在的模拟器
uv run auto_dungeon.py --emulator emulator-9999

# 输出：
# ❌ 模拟器 emulator-9999 不在设备列表中
# 可用设备: ['emulator-5554', 'emulator-5555']
# 📱 发送 Bark 通知: 副本助手 - 错误
# ✅ Bark 通知发送成功
```

### 查看可用设备

```bash
# 获取所有已连接的设备
adb devices

# 输出示例：
# List of devices attached
# emulator-5554          device
# emulator-5555          device
```

## 配置 Bark 通知

### 启用 Bark 通知

编辑 `system_config.json`：

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

将 `{device_key}` 替换为你的 Bark 设备密钥。

### 禁用 Bark 通知

```json
{
    "bark": {
        "enabled": false
    }
}
```

## 测试

### 运行单元测试

```bash
# 运行所有设备检查测试
uv run python -m pytest tests/test_emulator_device_check.py -v

# 运行特定测试
uv run python -m pytest tests/test_emulator_device_check.py::TestEmulatorDeviceCheck::test_device_check_exists -v
```

### 测试覆盖

- ✅ 成功获取 ADB 设备列表
- ✅ 处理空设备列表
- ✅ 处理 ADB 命令执行失败
- ✅ 检查存在的设备
- ✅ 检查不存在的设备
- ✅ 处理多个设备的情况

## 错误处理

### 常见错误

| 错误信息 | 原因 | 解决方案 |
|---------|------|--------|
| 模拟器不在设备列表中 | 指定的模拟器未启动或不存在 | 检查模拟器名称，确保模拟器已启动 |
| 可用设备为空 | 没有任何模拟器连接 | 启动 BlueStacks 模拟器 |
| ADB 命令执行失败 | ADB 连接问题 | 检查 Android SDK 和 ADB 配置 |

### 调试技巧

1. **查看可用设备**
   ```bash
   adb devices
   ```

2. **查看 Bark 通知日志**
   - 检查 `system_config.json` 中的 Bark 配置
   - 确保 `enabled` 为 `true`
   - 确保设备密钥正确

3. **查看详细日志**
   ```bash
   uv run auto_dungeon.py --emulator emulator-5554 2>&1 | tee debug.log
   ```

## 相关文件

- `auto_dungeon.py` - 主脚本，包含设备检查逻辑
- `emulator_manager.py` - 模拟器管理器，提供 `get_adb_devices()` 方法
- `tests/test_emulator_device_check.py` - 单元测试
- `system_config.json` - 系统配置，包含 Bark 通知设置

## 更新日志

详见 `CHANGELOG.md` 中的 "[新功能] 添加模拟器设备检查和 Bark 通知" 部分。

