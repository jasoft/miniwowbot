# 安卓模拟器截图工具 - YOLO 训练数据收集

这个脚本可以自动从安卓模拟器中每隔指定时间截取屏幕截图，用于收集 YOLO 训练数据集。

## 功能特点

- ✅ 自动每隔 3 秒（可配置）截取安卓模拟器屏幕
- ✅ 截图自动保存到指定目录
- ✅ 支持自定义截图间隔和输出目录
- ✅ 自动检测 ADB 连接状态
- ✅ 显示实时进度和统计信息
- ✅ 按 Ctrl+C 优雅停止

## 前置要求

### 1. 安装 Android SDK Platform Tools (ADB)

**macOS:**
```bash
brew install android-platform-tools
```

**验证安装:**
```bash
adb version
```

### 2. 启动安卓模拟器

确保你的安卓模拟器（如 BlueStacks、NoxPlayer、Android Studio 模拟器等）已经启动并运行。

### 3. 检查 ADB 连接

```bash
adb devices
```

应该看到类似输出：
```
List of devices attached
emulator-5554   device
```

如果没有显示设备，尝试：
```bash
# 重启 ADB 服务
adb kill-server
adb start-server
adb devices
```

## 使用方法

### 基本使用（默认配置）

```bash
# 使用 Python 运行
python3 capture_android_screenshots.py

# 或直接执行（需要先 chmod +x）
./capture_android_screenshots.py
```

默认配置：
- 截图间隔：3 秒
- 输出目录：`yolo_training_images/`

### 自定义配置

```bash
# 自定义输出目录
python3 capture_android_screenshots.py -o my_dataset

# 自定义截图间隔（2秒）
python3 capture_android_screenshots.py -i 2

# 同时自定义输出目录和间隔
python3 capture_android_screenshots.py -o dataset/raw_images -i 5
```

### 查看帮助

```bash
python3 capture_android_screenshots.py --help
```

## 输出文件格式

截图文件命名格式：`screenshot_YYYYMMDD_HHMMSS_NNNN.png`

示例：
```
yolo_training_images/
├── screenshot_20251013_234501_0000.png
├── screenshot_20251013_234504_0001.png
├── screenshot_20251013_234507_0002.png
└── ...
```

## 使用示例

### 示例 1: 收集游戏界面数据

```bash
# 启动脚本，每 3 秒截图一次
python3 capture_android_screenshots.py -o game_ui_dataset

# 在模拟器中操作游戏，脚本会自动截图
# 按 Ctrl+C 停止收集
```

### 示例 2: 快速采样模式

```bash
# 每 1 秒截图，快速收集大量样本
python3 capture_android_screenshots.py -i 1 -o quick_samples
```

### 示例 3: 慢速精确采样

```bash
# 每 10 秒截图，收集间隔较大的关键帧
python3 capture_android_screenshots.py -i 10 -o key_frames
```

## 停止截图

在终端中按 `Ctrl+C` 即可停止截图。脚本会显示总共捕获的截图数量和保存位置。

## 常见问题

### 1. 提示 "未检测到安卓设备/模拟器"

**解决方案：**
- 确保模拟器已启动
- 运行 `adb devices` 检查连接
- 尝试重启 ADB：`adb kill-server && adb start-server`

### 2. 提示 "未找到 adb 命令"

**解决方案：**
- 安装 Android SDK Platform Tools
- macOS: `brew install android-platform-tools`
- 确保 adb 在 PATH 中

### 3. 多个模拟器/设备连接

脚本会自动使用第一个检测到的设备。如果需要指定设备，可以在运行脚本前设置：
```bash
export ANDROID_SERIAL=emulator-5554
python3 capture_android_screenshots.py
```

### 4. 截图质量问题

默认使用 PNG 格式保存，保持原始屏幕分辨率和质量。如需调整，可以修改脚本中的 `screencap` 命令参数。

## YOLO 训练后续步骤

收集完截图后，通常需要：

1. **数据清理**：删除模糊、重复或无用的图片
2. **数据标注**：使用标注工具（如 LabelImg、CVAT）为图片添加边界框
3. **数据集划分**：将数据分为训练集、验证集和测试集
4. **YOLO 训练**：使用标注好的数据集训练 YOLO 模型

## 技术细节

脚本工作流程：
1. 检查 ADB 连接状态
2. 在设备上执行 `screencap` 命令截图
3. 使用 `adb pull` 将截图从设备拉取到本地
4. 删除设备上的临时文件
5. 等待指定间隔后重复

## 许可证

此脚本为开源工具，可自由使用和修改。
