# OCR 区域搜索功能

## 概述

OCR Helper 现在支持区域搜索功能，可以指定只在屏幕的特定区域进行文字识别，大大提升识别速度。

## 功能特点

- **3x3 网格分割**：将屏幕自动分成 9 个区域
- **智能区域合并**：多个区域会自动合并成一个连续的矩形进行 OCR
- **灵活的区域选择**：可以指定搜索一个或多个区域
- **坐标自动修正**：识别出的位置会自动转换为原图坐标
- **性能提升**：相比全屏搜索，可提升 3-9 倍速度
- **跨区域文字支持**：同一行或同一列的多个区域会合并，不会切断连续的文字

## 区域编号

屏幕被分成 3x3 的网格，区域编号如下：

```text
┌─────┬─────┬─────┐
│  1  │  2  │  3  │  ← 上部
├─────┼─────┼─────┤
│  4  │  5  │  6  │  ← 中部
├─────┼─────┼─────┤
│  7  │  8  │  9  │  ← 下部
└─────┴─────┴─────┘
  左    中    右
```

## 区域合并

**重要特性**：当指定多个区域时，它们会自动合并成一个连续的矩形区域进行 OCR，这样可以避免切断跨区域的文字。

### 合并示例

```python
# 示例1: 搜索整个上部（区域1, 2, 3会合并成一个水平矩形）
ocr.find_text_in_image("screenshot.png", "标题", regions=[1, 2, 3])
# 实际搜索区域：整个上部（宽度100%，高度33%）

# 示例2: 搜索整个左侧（区域1, 4, 7会合并成一个垂直矩形）
ocr.find_text_in_image("screenshot.png", "菜单", regions=[1, 4, 7])
# 实际搜索区域：整个左侧（宽度33%，高度100%）

# 示例3: 搜索底部工具栏（区域7, 8, 9会合并）
ocr.find_text_in_image("screenshot.png", "设置", regions=[7, 8, 9])
# 实际搜索区域：整个底部（宽度100%，高度33%）
# 即使"设置"文字横跨多个区域，也能正确识别

# 示例4: 搜索左上角2x2区域（区域1, 2, 4, 5会合并成矩形）
ocr.find_text_in_image("screenshot.png", "返回", regions=[1, 2, 4, 5])
# 实际搜索区域：左上角2x2（宽度66%，高度66%）
```

### 为什么需要合并？

如果不合并，分别对每个区域进行 OCR 会导致：

- ❌ 跨区域的文字被切断，无法识别
- ❌ 需要多次 OCR 调用，性能下降
- ❌ 坐标处理复杂

合并后的优势：

- ✅ 保持文字完整性，识别准确
- ✅ 只需一次 OCR 调用
- ✅ 坐标处理简单

## API 使用

from vibe_ocr import OCRHelper

ocr = OCRHelper()

# 在整个图像中搜索（默认）

result = ocr.find_text_in_image(
"screenshot.png",
"设置",
confidence_threshold=0.6
)

# 只在右上角搜索（区域3）

result = ocr.find_text_in_image(
"screenshot.png",
"设置",
confidence_threshold=0.6,
regions=[3] # 指定区域
)

# 在屏幕上半部分搜索（区域1, 2, 3）

result = ocr.find_text_in_image(
"screenshot.png",
"返回",
confidence_threshold=0.6,
regions=[1, 2, 3]
)

````

### 2. capture_and_find_text

截图并查找文字，支持指定区域。

```python
# 在整个屏幕中搜索
result = ocr.capture_and_find_text(
    "确定",
    confidence_threshold=0.6
)

# 只在中心区域搜索（区域5）
result = ocr.capture_and_find_text(
    "确定",
    confidence_threshold=0.6,
    regions=[5]
)

# 在屏幕底部搜索（区域7, 8, 9）
result = ocr.capture_and_find_text(
    "免费",
    confidence_threshold=0.6,
    regions=[7, 8, 9]
)
````

### 3. find_and_click_text

截图、查找文字并点击，支持指定区域。

```python
# 在整个屏幕中搜索并点击
success = ocr.find_and_click_text(
    "进入游戏",
    confidence_threshold=0.6
)

# 在中心和中下区域搜索并点击
success = ocr.find_and_click_text(
    "进入游戏",
    confidence_threshold=0.6,
    regions=[5, 8]
)
```

## 返回值

所有方法的返回值格式保持不变：

```python
{
    "found": True,              # 是否找到文字
    "center": (x, y),          # 文字中心坐标（已修正为原图坐标）
    "text": "实际识别的文字",    # 识别到的文字
    "confidence": 0.95,        # 置信度
    "bbox": [[x1,y1], ...],    # 边界框坐标（已修正为原图坐标）
    "total_matches": 1,        # 总匹配数
    "selected_index": 1        # 选择的索引
}
```

## 性能对比

| 搜索范围 | 区域数量  | 相对速度 | 适用场景        |
| -------- | --------- | -------- | --------------- |
| 全屏     | 无 (None) | 1x       | 不确定位置      |
| 单个区域 | 1         | 9x       | 明确知道位置    |
| 三个区域 | 3         | 3x       | 大致知道位置    |
| 半屏     | 3-6       | 2-3x     | 上/下/左/右半屏 |

## 使用建议

### 1. 根据UI布局选择区域

```python
# 返回按钮通常在左上角
ocr.find_and_click_text("返回", regions=[1])

# 确定/取消按钮通常在中下或底部
ocr.find_and_click_text("确定", regions=[5, 8])

# 设置按钮通常在右上角
ocr.find_and_click_text("设置", regions=[3])
```

### 2. 从小范围开始

```python
# 先尝试最可能的区域
result = ocr.capture_and_find_text("免费", regions=[8])

if not result["found"]:
    # 如果没找到，扩大搜索范围
    result = ocr.capture_and_find_text("免费", regions=[5, 8, 9])
```

### 3. 在循环中使用

```python
# 在游戏自动化中，按钮位置通常固定
while True:
    # 使用区域搜索加快速度
    if ocr.find_and_click_text("免费", regions=[8], use_cache=False):
        print("点击了免费按钮")
    else:
        break
```

## 实际应用示例

### 示例1: 游戏自动化

```python
ocr = vibe_ocr.OCRHelper()

# 点击左上角的返回按钮
ocr.find_and_click_text("返回", regions=[1])

# 点击中心的确定按钮
ocr.find_and_click_text("确定", regions=[5])

# 点击底部的免费按钮
ocr.find_and_click_text("免费", regions=[7, 8, 9])
```

### 示例2: 自适应搜索

```python
def smart_find_and_click(text, likely_regions, fallback_regions=None):
    """
    智能查找并点击，先在可能的区域搜索，失败后扩大范围
    """
    # 先在最可能的区域搜索
    if ocr.find_and_click_text(text, regions=likely_regions):
        return True

    # 如果没找到且有备选区域，在备选区域搜索
    if fallback_regions:
        if ocr.find_and_click_text(text, regions=fallback_regions):
            return True

    # 最后尝试全屏搜索
    return ocr.find_and_click_text(text)

# 使用示例
smart_find_and_click("免费", likely_regions=[8], fallback_regions=[5, 7, 9])
```

### 示例3: 区域监控

```python
# 监控特定区域的文字变化
def monitor_region(text, region, timeout=10):
    """
    监控特定区域，等待文字出现
    """
    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        result = ocr.capture_and_find_text(
            text,
            regions=[region],
            use_cache=False
        )
        if result["found"]:
            return True
        time.sleep(1)

    return False

# 监控右上角是否出现"完成"
if monitor_region("完成", region=3, timeout=30):
    print("任务完成！")
```

## 注意事项

1. **坐标自动修正**：所有返回的坐标（center, bbox）都已经修正为原图坐标，可以直接使用
2. **区域边界**：区域边界会自动处理，确保覆盖整个图像
3. **无效区域**：如果指定了无效的区域ID（<1 或 >9），会自动跳过
4. **缓存不适用**：使用区域搜索时，缓存功能不适用（因为搜索范围不同）
5. **性能权衡**：虽然区域搜索更快，但如果文字不在指定区域，会找不到

## 技术实现

### 区域分割

```python
# 图像被分成3x3网格
cell_height = image_height // 3
cell_width = image_width // 3

# 区域1的边界
x = 0
y = 0
w = cell_width
h = cell_height
```

### 坐标修正

```python
# 区域内坐标
region_x, region_y = 100, 50

# 区域偏移量
offset_x, offset_y = 300, 300  # 区域5的偏移

# 原图坐标
full_image_x = region_x + offset_x  # 400
full_image_y = region_y + offset_y  # 350
```

## 常见问题

**Q: 如何选择合适的区域？**
A: 根据UI布局和按钮位置选择。如果不确定，可以先用全屏搜索，找到后记录位置，下次直接用区域搜索。

**Q: 可以同时搜索多个不连续的区域吗？**
A: 可以，例如 `regions=[1, 5, 9]` 会搜索左上、中心和右下三个区域。

**Q: 区域搜索会影响识别准确度吗？**
A: 不会。区域搜索只是限制了搜索范围，OCR识别的准确度不受影响。

**Q: 如果文字跨越多个区域怎么办？**
A: 建议指定包含该文字的所有区域，或者使用全屏搜索。

## 更新日志

- **v1.1.0** (2024-01-09)
    - 新增区域搜索功能
    - 支持3x3网格分割
    - 自动坐标修正
    - 性能提升3-9倍
