# Roboflow 集成使用指南

这个增强版脚本结合了自动截图和 Roboflow 计算机视觉分析功能，可以实时检测游戏中的目标元素。

## 功能特点

- ✅ 每隔 3 秒（可配置）自动截取安卓模拟器屏幕
- ✅ 实时使用 Roboflow API 分析截图，检测目标对象
- ✅ 自动保存截图和分析结果
- ✅ 支持自定义 Roboflow 工作流
- ✅ 显示检测结果摘要（对象类型、数量、置信度）
- ✅ 可选择仅截图或启用 Roboflow 分析

## 文件说明

1. **[`capture_android_screenshots.py`](capture_android_screenshots.py:1)** - 基础版：仅截图，不进行分析
2. **[`capture_and_analyze.py`](capture_and_analyze.py:1)** - 增强版：截图 + Roboflow 实时分析
3. **[`roboflow_config.example.json`](roboflow_config.example.json:1)** - Roboflow 配置示例

## 快速开始

### 方式 1: 仅截图（用于数据收集）

```bash
# 使用基础版脚本，仅收集截图
python3 capture_android_screenshots.py

# 自定义配置
python3 capture_android_screenshots.py -o training_data -i 2
```

### 方式 2: 截图 + Roboflow 实时分析

```bash
# 安装依赖
pip install requests

# 启用 Roboflow 分析（使用默认配置）
python3 capture_and_analyze.py --enable-roboflow

# 自定义所有参数
python3 capture_and_analyze.py \
  --enable-roboflow \
  --api-key "你的API密钥" \
  --workspace "你的工作空间" \
  --workflow-id "你的工作流ID" \
  -o analyzed_results \
  -i 5
```

## Roboflow 配置

### 获取 Roboflow 凭证

1. **API Key**: 在 [app.roboflow.com](https://app.roboflow.com/soj-demo/settings/api) 获取
2. **Workspace**: 从项目 URL 中获取，例如 `https://app.roboflow.com/soj-demo/...` 中的 `soj-demo`
3. **Workflow ID**: 从部署页面获取，例如 `find-targetarrows-taskavailables-gobuttons-and-taskcompletes`

### 当前配置（示例）

```json
{
  "api_key": "w6oOUMB3dpmlpFSXv8t5",
  "workspace": "soj-demo",
  "workflow_id": "find-targetarrows-taskavailables-gobuttons-and-taskcompletes"
}
```

这个工作流可以检测以下游戏元素：
- Target Arrows（目标箭头）
- Task Availables（可用任务）
- Go Buttons（开始按钮）
- Task Completes（完成任务）

## 使用示例

### 示例 1: 收集训练数据（无分析）

```bash
# 每 3 秒截图，收集原始数据
python3 capture_android_screenshots.py -o yolo_dataset
```

输出结构：
```
yolo_dataset/
├── screenshot_20251013_234501_0000.png
├── screenshot_20251013_234504_0001.png
└── ...
```

### 示例 2: 实时分析游戏状态

```bash
# 启用 Roboflow 实时分析
python3 capture_and_analyze.py --enable-roboflow -i 3
```

输出结构：
```
analyzed_screenshots/
├── images/
│   ├── screenshot_20251013_234501_0000.png
│   ├── screenshot_20251013_234504_0001.png
│   └── ...
└── results/
    ├── screenshot_20251013_234501_0000_result.json
    ├── screenshot_20251013_234504_0001_result.json
    └── ...
```

### 示例 3: 自定义检测间隔

```bash
# 每 1 秒快速检测
python3 capture_and_analyze.py --enable-roboflow -i 1

# 每 10 秒慢速检测（节省 API 调用）
python3 capture_and_analyze.py --enable-roboflow -i 10
```

## 输出说明

### 控制台输出示例

```
======================================================================
安卓模拟器自动截图与分析工具
✓ Roboflow 实时分析已启用
======================================================================
✓ 检测到设备: emulator-5554
✓ Roboflow 分析已启用
✓ 输出目录: /path/to/analyzed_screenshots
  - 图片: images/
  - 结果: results/

配置:
  截图间隔: 3 秒
  输出目录: /path/to/analyzed_screenshots
  Roboflow 分析: 已启用

开始截图... (按 Ctrl+C 停止)

✓ [0001] screenshot_20251013_234501_0000.png (125.3 KB)
  🔍 正在使用 Roboflow 分析...
  ✓ 检测到 3 个对象:
    - go_button: 1 个 (平均置信度: 87.50%)
    - task_available: 2 个 (平均置信度: 92.30%)

✓ [0002] screenshot_20251013_234504_0001.png (128.7 KB)
  🔍 正在使用 Roboflow 分析...
  ✓ 检测到 1 个对象:
    - target_arrow: 1 个 (平均置信度: 95.20%)
```

### 分析结果 JSON 格式

```json
{
  "outputs": [
    {
      "predictions": {
        "image": {
          "width": 1080,
          "height": 1920
        },
        "predictions": [
          {
            "x": 540.5,
            "y": 960.2,
            "width": 120.0,
            "height": 80.0,
            "confidence": 0.8750,
            "class": "go_button",
            "class_id": 0,
            "detection_id": "uuid-here"
          }
        ]
      }
    }
  ]
}
```

## 命令行参数

### capture_and_analyze.py 参数

```bash
python3 capture_and_analyze.py [选项]

选项:
  -h, --help            显示帮助信息
  -o, --output DIR      输出目录路径 (默认: analyzed_screenshots)
  -i, --interval SEC    截图间隔秒数 (默认: 3)
  --enable-roboflow     启用 Roboflow 实时分析
  --api-key KEY         Roboflow API 密钥
  --workspace NAME      Roboflow 工作空间名称
  --workflow-id ID      Roboflow 工作流 ID
```

## 性能优化

### API 调用优化

1. **调整截图间隔**：增加间隔可减少 API 调用次数
   ```bash
   python3 capture_and_analyze.py --enable-roboflow -i 5  # 每 5 秒
   ```

2. **选择性分析**：仅在需要时启用 Roboflow
   ```bash
   # 先收集数据
   python3 capture_android_screenshots.py -o dataset

   # 后期批量分析（可以自己写脚本）
   ```

3. **本地缓存**：Roboflow SDK 支持缓存，减少重复请求

## 常见问题

### 1. Roboflow API 调用失败

**可能原因：**
- API 密钥无效
- 网络连接问题
- API 配额用尽

**解决方案：**
- 验证 API 密钥是否正确
- 检查网络连接
- 查看 Roboflow 账户使用情况

### 2. 检测结果不准确

**解决方案：**
- 确保使用的工作流 ID 正确
- 检查截图质量和清晰度
- 考虑重新训练或调整模型

### 3. 处理速度慢

**解决方案：**
- 增加截图间隔 `-i 5` 或更高
- 检查网络延迟
- 考虑使用本地推理而非 API

## 进阶用法

### 批量分析已有截图

如果你已经有大量截图需要分析，可以创建批量处理脚本：

```python
import os
from pathlib import Path
from capture_and_analyze import RoboflowAnalyzer
import json

# 初始化分析器
analyzer = RoboflowAnalyzer(
    api_key="your-api-key",
    workspace="soj-demo",
    workflow_id="your-workflow-id"
)

# 批量处理
image_dir = Path("yolo_dataset")
results_dir = Path("batch_results")
results_dir.mkdir(exist_ok=True)

for image_file in image_dir.glob("*.png"):
    print(f"分析: {image_file.name}")
    result = analyzer.analyze_image(image_file)

    if result:
        result_file = results_dir / f"{image_file.stem}_result.json"
        with open(result_file, 'w') as f:
            json.dump(result, indent=2, fp=f)
```

### 集成到现有自动化脚本

你可以导入 [`RoboflowAnalyzer`](capture_and_analyze.py:13) 类到其他 Python 脚本中使用：

```python
from capture_and_analyze import RoboflowAnalyzer

# 在你的脚本中
analyzer = RoboflowAnalyzer(
    api_key="your-key",
    workspace="soj-demo",
    workflow_id="your-workflow"
)

# 分析图片
result = analyzer.analyze_image("path/to/image.png")
if result:
    predictions = result['outputs'][0]['predictions']['predictions']
    for pred in predictions:
        print(f"检测到: {pred['class']} (置信度: {pred['confidence']:.2%})")
```

## 相关资源

- [Roboflow 官方文档](https://docs.roboflow.com/)
- [Roboflow API 参考](https://docs.roboflow.com/api-reference)
- [基础截图工具文档](README_SCREENSHOT_CAPTURE.md)

## 技术支持

如遇问题，请检查：
1. ADB 连接是否正常：`adb devices`
2. Roboflow API 密钥是否有效
3. 网络连接是否稳定
4. Python 依赖是否已安装：`pip install requests`
