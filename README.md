# 异世界勇者自动挂机助手

基于 Airtest 和 PaddleOCR 的自动挂机脚本，用于异世界勇者游戏的副本自动化。

## 核心文件

### 主要脚本
- `auto_dungeon_simple.air/auto_dungeon_simple.py` - 自动挂机主脚本
- `ocr_helper.py` - OCR 工具类，封装 PaddleOCR 功能
- `quick_paddleocr_example.py` - 原始 PaddleOCR 示例（已被 ocr_helper.py 替代）

### 配置和资源
- `pyproject.toml` - 项目依赖配置
- `uv.lock` - 依赖锁定文件
- `tpl1759654885996.png` - Airtest 模板图片
- `output/` - OCR 识别结果输出目录

## 安装依赖

```bash
uv sync
```

或使用 pip：

```bash
pip install airtest paddleocr opencv-python numpy coloredlogs
```

## 使用方法

1. 连接 Android 设备
2. 启动异世界勇者游戏
3. 运行脚本：

```bash
python auto_dungeon_simple.air/auto_dungeon_simple.py
```

## 功能特性

- 🎮 自动遍历所有区域的副本（8个区域，98个副本）
- 🔍 使用 OCRHelper 类进行智能文字识别
- 🎯 自动识别并点击免费按钮
- 📱 支持 Android 设备自动化
- 🔄 智能区域切换和副本选择
- 🌈 彩色日志输出，清晰显示运行状态

## OCRHelper 类

新的 `OCRHelper` 类提供了统一的 OCR 接口，支持多匹配功能：

```python
from ocr_helper import OCRHelper

# 初始化
ocr_helper = OCRHelper(output_dir="output")

# 基本用法：查找并点击第1个匹配的文字（默认启用缓存）
success = ocr_helper.find_and_click_text("确定", confidence_threshold=0.8)

# 多匹配功能：点击第2个"确定"按钮
success = ocr_helper.find_and_click_text("确定", confidence_threshold=0.8, occurrence=2)

# 禁用缓存：强制重新识别（适用于动态内容）
success = ocr_helper.find_and_click_text("免费", confidence_threshold=0.8, use_cache=False)

# 截图并查找文字
result = ocr_helper.capture_and_find_text("设置", confidence_threshold=0.7)

# 查看所有匹配的文字
matches = ocr_helper.find_all_matching_texts("screenshot.png", "确定")
print(f"找到 {len(matches)} 个确定按钮")
```

### 多匹配功能

当界面中有多个相同的文字时，可以指定点击第几个：

- `occurrence=1` (默认): 点击第1个匹配
- `occurrence=2`: 点击第2个匹配
- `occurrence=N`: 点击第N个匹配

如果请求的匹配项超出实际数量，会自动选择最后一个匹配项。

## 区域配置

支持以下区域的自动挂机：
- 风暴群岛、军团领域、暗影大陆、迷雾大陆
- 元素之地、冰封大陆、虚空领域、东部大陆

## 彩色日志

脚本使用 `coloredlogs` 提供彩色的日志输出，不同类型的信息用不同颜色显示：

- 🟢 **INFO** (绿色): 正常操作信息，如成功点击、完成副本等
- 🟡 **WARNING** (黄色): 警告信息，如未找到按钮、跳过副本等
- 🔴 **ERROR** (红色): 错误信息，如切换失败、OCR识别错误等
- 🔵 **DEBUG** (青色): 调试信息，详细的操作过程

日志格式：`时间 级别 消息`，例如：
```
23:18:18 INFO 🎮 副本自动遍历脚本
23:18:18 INFO ✅ 成功点击: 风暴群岛
23:18:18 WARNING ⚠️ 未找到免费按钮
23:18:18 ERROR ❌ 切换失败: 某个区域
```

## 注意事项

- 确保设备屏幕清晰，文字可见
- 脚本运行期间请勿手动操作设备
- 可根据需要调整 OCR 识别的置信度阈值
