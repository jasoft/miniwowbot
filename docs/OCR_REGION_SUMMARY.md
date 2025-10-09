# OCR 区域搜索功能总结

## 核心改进

### 问题
原始需求是将屏幕分成 9 个区域分别进行 OCR，但这会导致：
- ❌ 跨区域的文字被切断（如底部工具栏的长文字）
- ❌ 需要多次 OCR 调用，性能下降
- ❌ 坐标处理复杂

### 解决方案
**智能区域合并**：多个区域自动合并成一个连续的矩形进行 OCR

```python
# 示例：搜索底部工具栏（区域 7, 8, 9）
ocr.find_and_click_text("免费", regions=[7, 8, 9])

# 实际执行：
# 1. 合并区域 7, 8, 9 为一个矩形（整个底部）
# 2. 对这个矩形进行一次 OCR
# 3. 坐标自动修正为原图坐标
```

## 技术实现

### 1. 区域合并算法

```python
def _merge_regions(self, regions: List[int]) -> Tuple[int, int, int, int]:
    """
    将多个区域合并为一个矩形
    
    输入: [1, 2, 3]  # 上部三个区域
    输出: (0, 0, 0, 2)  # min_row, max_row, min_col, max_col
    
    输入: [7, 8, 9]  # 下部三个区域
    输出: (2, 2, 0, 2)
    
    输入: [1, 4, 7]  # 左侧三个区域
    输出: (0, 2, 0, 0)
    """
```

### 2. 边界计算

```python
def _get_region_bounds(self, image_shape, regions):
    """
    计算合并后的矩形边界
    
    输入: image_shape=(900, 900), regions=[7, 8, 9]
    输出: (0, 600, 900, 300)  # x, y, w, h
          整个底部：从 y=600 开始，宽度 900，高度 300
    """
```

### 3. 坐标修正

```python
def _adjust_coordinates_to_full_image(self, bbox, offset):
    """
    将区域内坐标转换为原图坐标
    
    输入: bbox=[[10, 20], [100, 20], [100, 50], [10, 50]]
          offset=(0, 600)  # 底部区域的偏移
    输出: [[10, 620], [100, 620], [100, 650], [10, 650]]
    """
```

## 使用示例

### 基本用法

```python
from ocr_helper import OCRHelper

ocr = OCRHelper()

# 1. 单个区域（最快，9倍速度）
ocr.find_and_click_text("设置", regions=[3])  # 右上角

# 2. 水平合并（整行，3倍速度）
ocr.find_and_click_text("免费", regions=[7, 8, 9])  # 整个底部

# 3. 垂直合并（整列，3倍速度）
ocr.find_and_click_text("背包", regions=[1, 4, 7])  # 整个左侧

# 4. 矩形合并（2x2区域）
ocr.find_and_click_text("返回", regions=[1, 2, 4, 5])  # 左上角2x2
```

### 实际应用场景

```python
# 场景1: 游戏底部工具栏（通常有很长的文字）
ocr.find_and_click_text("领取奖励", regions=[7, 8, 9])

# 场景2: 左侧菜单栏
ocr.find_and_click_text("角色", regions=[1, 4, 7])

# 场景3: 顶部标题栏
ocr.find_and_click_text("副本选择", regions=[1, 2, 3])

# 场景4: 中心对话框
ocr.find_and_click_text("确定", regions=[5])

# 场景5: 右侧设置按钮
ocr.find_and_click_text("设置", regions=[3])
```

## 性能对比

| 场景 | 区域 | 速度提升 | 说明 |
|------|------|---------|------|
| 全屏搜索 | None | 1x | 基准速度 |
| 单个区域 | [5] | 9x | 最快 |
| 水平条 | [7,8,9] | 3x | 底部工具栏 |
| 垂直条 | [1,4,7] | 3x | 侧边菜单 |
| 2x2区域 | [1,2,4,5] | 2.25x | 左上角 |

## 区域编号参考

```text
┌─────┬─────┬─────┐
│  1  │  2  │  3  │  ← 上部（标题栏、返回按钮）
├─────┼─────┼─────┤
│  4  │  5  │  6  │  ← 中部（主要内容、对话框）
├─────┼─────┼─────┤
│  7  │  8  │  9  │  ← 下部（工具栏、按钮）
└─────┴─────┴─────┘
  左    中    右
  侧    间    侧
  菜    区    设
  单    域    置
```

## 常见合并模式

### 水平合并（同一行）

```python
# 上部整行
regions=[1, 2, 3]  # 适合：标题栏、顶部导航

# 中部整行
regions=[4, 5, 6]  # 适合：主要内容区域

# 下部整行
regions=[7, 8, 9]  # 适合：底部工具栏、按钮栏
```

### 垂直合并（同一列）

```python
# 左侧整列
regions=[1, 4, 7]  # 适合：左侧菜单、导航栏

# 中间整列
regions=[2, 5, 8]  # 适合：中间主要内容

# 右侧整列
regions=[3, 6, 9]  # 适合：右侧设置、信息栏
```

### 矩形合并

```python
# 左上角 2x2
regions=[1, 2, 4, 5]  # 适合：返回按钮、标题区域

# 右下角 2x2
regions=[5, 6, 8, 9]  # 适合：确定/取消按钮

# 上半部分
regions=[1, 2, 3, 4, 5, 6]  # 适合：对话框上半部

# 下半部分
regions=[4, 5, 6, 7, 8, 9]  # 适合：对话框下半部
```

## 最佳实践

### 1. 根据UI布局选择区域

```python
# 分析UI布局
# - 返回按钮：通常在左上角 → regions=[1]
# - 设置按钮：通常在右上角 → regions=[3]
# - 确定按钮：通常在中下部 → regions=[5, 8]
# - 工具栏：通常在底部 → regions=[7, 8, 9]
```

### 2. 从小到大扩展搜索范围

```python
def smart_search(text):
    # 先尝试最可能的区域
    result = ocr.find_text_in_image("screenshot.png", text, regions=[8])
    if result["found"]:
        return result
    
    # 扩大到整个底部
    result = ocr.find_text_in_image("screenshot.png", text, regions=[7, 8, 9])
    if result["found"]:
        return result
    
    # 最后全屏搜索
    return ocr.find_text_in_image("screenshot.png", text)
```

### 3. 缓存区域位置

```python
# 记录常用按钮的区域
BUTTON_REGIONS = {
    "返回": [1],
    "设置": [3],
    "确定": [5, 8],
    "取消": [5, 8],
    "免费": [7, 8, 9],
    "背包": [1, 4, 7],
}

def click_button(name):
    regions = BUTTON_REGIONS.get(name)
    return ocr.find_and_click_text(name, regions=regions)
```

## 测试覆盖

### 测试类别

1. **区域合并测试** (4个)
   - 单区域合并
   - 水平方向合并
   - 垂直方向合并
   - 矩形区域合并

2. **边界计算测试** (4个)
   - 全屏边界
   - 单区域边界
   - 水平合并边界
   - 垂直合并边界

3. **区域提取测试** (3个)
   - 单区域提取
   - 水平合并提取
   - 垂直合并提取

4. **坐标调整测试** (1个)
   - 区域坐标到原图坐标的转换

5. **API测试** (2个)
   - 区域搜索API
   - 多区域搜索API

6. **其他测试** (1个)
   - 空结果格式测试

**总计**: 15个测试，全部通过 ✅

## 向后兼容

- ✅ 所有现有代码无需修改
- ✅ `regions` 参数默认为 `None`（全屏搜索）
- ✅ 所有现有测试通过（15/15）
- ✅ API签名保持兼容

## 文件清单

### 核心代码
- `ocr_helper.py` - 主要实现

### 测试文件
- `tests/test_ocr_regions.py` - 区域功能测试（15个测试）
- `tests/test_ocr.py` - 原有OCR测试（15个测试）

### 文档
- `docs/OCR_REGION_SEARCH.md` - 详细使用文档
- `docs/OCR_REGION_SUMMARY.md` - 本文档
- `CHANGELOG.md` - 更新日志

### 示例
- `examples/ocr_region_example.py` - 使用示例

## 参考资料

- [Lackey Region 类文档](https://lackey.readthedocs.io/en/latest/_modules/lackey/RegionMatching.html)
- [Sikuli Region 概念](http://doc.sikuli.org/region.html)

