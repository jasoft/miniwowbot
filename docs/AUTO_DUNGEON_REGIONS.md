# auto_dungeon.py 区域搜索使用指南

## 概述

`auto_dungeon.py` 提供了两个核心函数用于文本查找：
- `find_text()` - 查找文本并返回结果，支持超时异常
- `find_text_and_click()` - 查找文本并点击，内部调用 `find_text()`

两个函数都支持 `regions` 参数，可以指定在屏幕的特定区域搜索文字，大幅提升性能。

## 函数签名

### find_text()

```python
def find_text(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
    raise_exception=True,  # 新增参数
):
    """
    使用 OCRHelper 查找文本

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :param raise_exception: 超时后是否抛出异常，默认True
    :return: OCR识别结果字典，包含 center, text, confidence 等信息
    :raises TimeoutError: 如果超时且 raise_exception=True
    """
```

### find_text_and_click()

```python
def find_text_and_click(
    text,
    timeout=10,
    similarity_threshold=0.7,
    occurrence=1,
    use_cache=True,
    regions=None,
):
    """
    使用 OCRHelper 查找文本并点击

    :param text: 要查找的文本
    :param timeout: 超时时间（秒）
    :param similarity_threshold: 相似度阈值
    :param occurrence: 指定点击第几个出现的文字 (1-based)，默认为1
    :param use_cache: 是否使用缓存
    :param regions: 要搜索的区域列表 (1-9)，None表示全屏搜索
    :return: 是否成功
    """
```

## 区域编号

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

## 使用示例

### 基本用法

#### find_text() - 查找文本

```python
# 1. 查找文本（超时抛出异常）
try:
    result = find_text("免费", timeout=5, regions=[7, 8, 9])
    print(f"找到文本，位置: {result['center']}")
    print(f"识别文本: {result['text']}")
    print(f"置信度: {result['confidence']}")
except TimeoutError as e:
    print(f"超时未找到文本: {e}")

# 2. 查找文本（超时不抛出异常）
result = find_text("免费", timeout=5, regions=[7, 8, 9], raise_exception=False)
if result:
    print(f"找到文本，位置: {result['center']}")
else:
    print("未找到文本")

# 3. 等待文本出现（用于等待界面加载）
try:
    find_text("进入游戏", timeout=10, regions=[8])
    print("游戏界面已加载")
except TimeoutError:
    print("游戏界面加载超时")
```

#### find_text_and_click() - 查找并点击

```python
# 1. 原有用法（全屏搜索）
find_text_and_click("免费")

# 2. 新用法（指定区域搜索）
find_text_and_click("免费", regions=[7, 8, 9])  # 只在底部搜索

# 3. 带返回值判断
if find_text_and_click("免费", timeout=5, regions=[7, 8, 9]):
    print("成功点击免费按钮")
else:
    print("未找到免费按钮")
```

### 实际应用场景

#### 1. 优化 `click_free_button()` 函数

免费按钮通常在屏幕底部，可以只搜索底部区域：

```python
def click_free_button():
    """点击免费按钮（优化版）"""
    free_words = ["免费"]

    for word in free_words:
        # 只在底部区域搜索，速度提升3倍
        if find_text_and_click(word, timeout=3, use_cache=False, regions=[7, 8, 9]):
            logger.info(f"💰 点击了免费按钮: {word}")
            return True

    logger.warning("⚠️ 未找到免费按钮")
    return False
```

#### 2. 优化角色选择

返回按钮通常在左上角，进入游戏按钮通常在底部：

```python
def switch_character(char_class):
    """切换角色（优化版）"""
    logger.info(f"🔄 切换角色: {char_class}")

    if not is_character_selection():
        back_to_main()
        touch(SETTINGS_POINT)
        sleep(1)

        # 返回按钮在左上角，只搜索区域1
        find_text_and_click("返回角色选择界面", regions=[1])
        wait(Template(r"images/enter_game_button.png", resolution=(720, 1280)), 10)
    else:
        logger.info("已在角色选择界面")

    # 查找职业文字位置（中部区域）
    result = ocr_helper.capture_and_find_text(
        char_class,
        confidence_threshold=0.7,
        occurrence=1,
        regions=[4, 5, 6],  # 只在中部搜索
    )

    if result["found"]:
        center = result["center"]
        touch(center)
        sleep(1)
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        logger.error(f"❌ 未找到职业: {char_class}")
        raise Exception(f"无法找到职业: {char_class}")

    # 进入游戏按钮在底部
    find_text_and_click("进入游戏", regions=[7, 8, 9])
    wait_for_main()
```

#### 3. 优化区域切换

切换区域按钮通常在顶部或中部：

```python
def switch_zone(zone_name):
    """切换区域（优化版）"""
    logger.info(f"🗺️ 切换区域: {zone_name}")

    # 点击切换区域按钮（通常在顶部）
    switch_words = ["切换区域"]

    for word in switch_words:
        if find_text_and_click(word, timeout=10, regions=[1, 2, 3]):
            break

    # 点击区域名称（在弹出的菜单中，通常在中部）
    if find_text_and_click(zone_name, timeout=10, occurrence=2, regions=[4, 5, 6]):
        logger.info(f"✅ 成功切换到: {zone_name}")
        touch((80, 212))  # 关闭切换菜单
        return True

    logger.error(f"❌ 切换失败: {zone_name}")
    return False
```

#### 4. 优化装备售卖

装备、整理售卖等按钮位置相对固定：

```python
def sell_trashes():
    """卖垃圾（优化版）"""
    logger.info("💰 卖垃圾")
    click_back()

    # 装备按钮通常在底部或右侧
    find_text_and_click("装备", regions=[6, 9])

    # 整理售卖按钮通常在右上角
    find_text_and_click("整理售卖", regions=[3, 6])

    # 出售按钮通常在底部中间
    find_text_and_click("出售", regions=[8])

    click_back()
    click_back()

    # 战斗按钮通常在底部
    find_text_and_click("战斗", regions=[7, 8, 9])
```

#### 5. 优化副本处理

副本名称通常在中部，免费按钮在底部：

```python
def process_dungeon(dungeon_name, index, total):
    """
    处理单个副本（优化版）
    """
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

    # 副本名称通常在中部区域
    if not find_text_and_click(dungeon_name, timeout=5, regions=[4, 5, 6]):
        logger.warning(f"⏭️ 跳过: {dungeon_name}")
        return False

    # 免费按钮在底部
    if click_free_button():  # 已经优化为只搜索底部
        logger.info(f"✅ 完成: {dungeon_name}")
        return True

    logger.info(f"⏭️ 已通关: {dungeon_name}")
    click_back()
    return False
```

## 性能对比

### 原有实现（全屏搜索）

```python
find_text_and_click("免费", timeout=3)
# OCR 耗时: ~0.9秒
```

### 优化后（区域搜索）

```python
find_text_and_click("免费", timeout=3, regions=[7, 8, 9])
# OCR 耗时: ~0.3秒
# 性能提升: 3倍
```

## 常用区域组合

### 按钮位置参考

| 按钮类型 | 常见位置 | 推荐区域 |
|---------|---------|---------|
| 返回按钮 | 左上角 | `[1]` |
| 设置按钮 | 右上角 | `[3]` |
| 确定/取消 | 中下部 | `[5, 8]` |
| 免费按钮 | 底部 | `[7, 8, 9]` |
| 进入游戏 | 底部中间 | `[8]` |
| 副本名称 | 中部 | `[4, 5, 6]` |
| 装备按钮 | 右下角 | `[6, 9]` |
| 战斗按钮 | 底部 | `[7, 8, 9]` |

### 区域组合策略

```python
# 1. 单个区域（最快，9倍速度）
regions=[5]  # 中心区域

# 2. 水平条（3倍速度）
regions=[1, 2, 3]  # 整个上部
regions=[4, 5, 6]  # 整个中部
regions=[7, 8, 9]  # 整个下部

# 3. 垂直条（3倍速度）
regions=[1, 4, 7]  # 整个左侧
regions=[2, 5, 8]  # 整个中间
regions=[3, 6, 9]  # 整个右侧

# 4. 矩形区域
regions=[1, 2, 4, 5]  # 左上角2x2
regions=[5, 6, 8, 9]  # 右下角2x2
```

## 最佳实践

### 1. 渐进式搜索

如果不确定按钮位置，可以从小范围逐步扩大：

```python
def smart_find_and_click(text):
    """智能查找并点击"""
    # 先尝试最可能的区域
    if find_text_and_click(text, timeout=2, regions=[8]):
        return True

    # 扩大到整个底部
    if find_text_and_click(text, timeout=3, regions=[7, 8, 9]):
        return True

    # 最后全屏搜索
    return find_text_and_click(text, timeout=5)
```

### 2. 缓存区域位置

记录常用按钮的区域，避免重复搜索：

```python
# 在文件顶部定义
BUTTON_REGIONS = {
    "免费": [7, 8, 9],
    "返回": [1],
    "设置": [3],
    "确定": [5, 8],
    "取消": [5, 8],
    "进入游戏": [8],
    "装备": [6, 9],
    "战斗": [7, 8, 9],
}

def click_button(name, **kwargs):
    """点击按钮（使用预定义区域）"""
    regions = BUTTON_REGIONS.get(name)
    return find_text_and_click(name, regions=regions, **kwargs)
```

### 3. 日志输出

使用区域搜索时，日志会自动显示区域信息：

```python
find_text_and_click("免费", regions=[7, 8, 9])
# 输出: 🔍 查找文本: 免费 [区域[7, 8, 9]]
# 输出: ✅ 成功点击: 免费 [区域[7, 8, 9]]
```

## 注意事项

1. **区域合并**：多个区域会自动合并成一个连续的矩形
   - `[7, 8, 9]` → 整个底部（一次OCR）
   - 不会分别对每个区域进行OCR

2. **向后兼容**：不指定 `regions` 参数时，默认全屏搜索
   ```python
   find_text_and_click("免费")  # 全屏搜索，与之前行为一致
   ```

3. **性能权衡**：
   - 区域太小：可能找不到目标
   - 区域太大：性能提升不明显
   - 建议：根据实际UI布局选择合适的区域

4. **测试验证**：
   - 修改后建议测试确保按钮能正确找到
   - 可以先用全屏搜索确认位置，再优化为区域搜索

## 迁移指南

### 步骤1：识别按钮位置

运行游戏，观察常用按钮的位置，记录在哪个区域。

### 步骤2：逐步优化

不要一次性修改所有调用，逐个函数优化：

```python
# 原代码
def click_free_button():
    if find_text_and_click("免费", timeout=3, use_cache=False):
        return True

# 优化后
def click_free_button():
    if find_text_and_click("免费", timeout=3, use_cache=False, regions=[7, 8, 9]):
        return True
```

### 步骤3：测试验证

每次修改后运行测试，确保功能正常。

### 步骤4：性能监控

观察日志中的 OCR 耗时，确认性能提升。

## 总结

- ✅ 简单易用：只需添加 `regions` 参数
- ✅ 性能提升：3-9倍速度提升
- ✅ 向后兼容：不影响现有代码
- ✅ 智能合并：多个区域自动合并
- ✅ 日志清晰：自动显示区域信息

建议优先优化以下场景：
1. 高频调用的函数（如 `click_free_button`）
2. 位置固定的按钮（如返回、设置）
3. 超时时间较长的搜索（可以缩短超时时间）

