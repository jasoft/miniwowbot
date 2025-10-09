# 更新日志

## [4.2.0] - 2025-01-09

### 🚀 新增功能：OCR 区域搜索

#### 核心功能
- ✅ 支持将屏幕分成 3x3 网格（9个区域）
- ✅ **智能区域合并**：多个区域自动合并成连续矩形，避免切断文字
- ✅ 可以指定只在特定区域进行 OCR 识别
- ✅ 自动将区域内坐标转换为原图坐标
- ✅ 性能提升 3-9 倍（取决于区域数量）
- ✅ 支持跨区域文字识别（如底部工具栏的长文字）

#### API 更新
所有主要方法都新增了 `regions` 参数：
- ✅ `find_text_in_image(regions=[1, 2, 3])` - 在图像的指定区域搜索
- ✅ `capture_and_find_text(regions=[5])` - 截图并在指定区域搜索
- ✅ `find_and_click_text(regions=[7, 8, 9])` - 在指定区域搜索并点击

#### 区域编号
```
1 2 3  ← 上部
4 5 6  ← 中部
7 8 9  ← 下部
```

#### 区域合并说明
多个区域会自动合并成一个连续的矩形进行 OCR：
- `[1, 2, 3]` → 整个上部（宽100%，高33%）
- `[7, 8, 9]` → 整个底部（宽100%，高33%）- 适合底部工具栏
- `[1, 4, 7]` → 整个左侧（宽33%，高100%）- 适合侧边菜单
- `[1, 2, 4, 5]` → 左上角2x2（宽66%，高66%）

这样可以避免切断跨区域的文字，提高识别准确率。

#### 使用示例
```python
# 在右上角搜索设置按钮（区域3）
ocr.find_and_click_text("设置", regions=[3])

# 在屏幕底部搜索免费按钮（区域7, 8, 9会合并成整个底部）
ocr.find_and_click_text("免费", regions=[7, 8, 9])

# 在中心区域搜索确定按钮（区域5）
ocr.find_and_click_text("确定", regions=[5])

# 在整个左侧搜索菜单项（区域1, 4, 7会合并成整个左侧）
ocr.find_and_click_text("背包", regions=[1, 4, 7])
```

#### 性能对比
| 搜索范围 | 区域数量 | 相对速度 | 适用场景 |
|---------|---------|---------|---------|
| 全屏 | None | 1x | 不确定位置 |
| 单个区域 | 1 | 9x | 明确知道位置 |
| 三个区域 | 3 | 3x | 大致知道位置 |

#### 新增文件
- ✅ `tests/test_ocr_regions.py` - 区域功能测试（10个测试用例）
- ✅ `examples/ocr_region_example.py` - 使用示例
- ✅ `docs/OCR_REGION_SEARCH.md` - 详细文档

#### 内部实现
- ✅ `_merge_regions()` - 合并多个区域为连续矩形
- ✅ `_get_region_bounds()` - 计算合并后的区域边界
- ✅ `_extract_region()` - 提取合并后的图像区域
- ✅ `_adjust_coordinates_to_full_image()` - 坐标修正
- ✅ `_find_text_in_regions()` - 区域搜索核心逻辑
- ✅ `_get_region_description()` - 生成区域描述文字
- ✅ `_empty_result()` - 统一的空结果返回

#### 测试覆盖
- ✅ 区域合并测试（4个）- 单区域、水平、垂直、矩形合并
- ✅ 区域边界计算测试（4个）- 全屏、单区域、水平合并、垂直合并
- ✅ 区域提取测试（3个）- 单区域、水平合并、垂直合并
- ✅ 坐标调整测试（1个）
- ✅ 区域搜索API测试（2个）
- ✅ 空结果测试（1个）
- ✅ 所有测试通过（15/15）

#### 向后兼容
- ✅ 所有现有代码无需修改
- ✅ `regions` 参数默认为 `None`（全屏搜索）
- ✅ 所有现有测试通过（15/15）

#### 使用建议
1. **根据UI布局选择区域**：返回按钮在左上（区域1），确定按钮在中下（区域5,8）
2. **从小范围开始**：先尝试最可能的区域，失败后扩大范围
3. **在循环中使用**：游戏自动化中按钮位置通常固定，使用区域搜索加快速度

#### 参考实现
参考了 Lackey (Sikuli Python 实现) 的 Region 类设计：
- https://lackey.readthedocs.io/en/latest/_modules/lackey/RegionMatching.html

---

## [4.1.1] - 2025-01-07

### 🚀 优化：智能跳过已完成副本

#### 核心改进
- ✅ 在选择角色前先检查当日进度
- ✅ 如果所有选定的副本都已完成，直接退出脚本
- ✅ 避免不必要的设备连接和角色选择操作
- ✅ 优化日志输出，显示选定副本数量

#### 执行流程优化
1. 加载配置文件
2. 初始化数据库，检查今日进度
3. 计算选定副本总数和已完成数量
4. **如果全部完成，输出日志并退出**
5. 如果有剩余副本，才初始化设备和OCR
6. 选择角色（如果配置了职业）
7. 执行副本遍历

#### 日志改进
- 显示选定副本数量
- 显示已完成副本数量
- 显示剩余副本数量
- 全部完成时显示庆祝信息

## [4.1.0] - 2025-01-07

### ✨ 新增功能：角色职业选择

#### 核心功能
- ✅ 配置文件支持 `class` 字段指定角色职业
- ✅ 自动选择角色并等待加载完成
- ✅ 支持战士、法师、刺客、猎人、圣骑士等职业

#### 实现细节
- ✅ 完善 `select_character(char_class)` 函数
  - 使用 OCR 查找职业文字位置
  - 点击文字上方 30 像素的角色头像
  - 等待角色加载（约 10 秒）
  - 调用 `wait_for_main()` 等待回到主界面
- ✅ 配置加载器添加 `get_char_class()` 方法
- ✅ 主程序在初始化后自动选择角色

#### 配置文件变化
- 新增 `class` 字段（可选）：指定角色职业名称
- 示例：`"class": "战士"`
- 如果未配置，跳过角色选择

#### 测试更新
- ✅ 添加 `test_get_char_class()` 测试
- ✅ 更新测试以使用新的配置文件（warrior.json, mage.json 等）
- ✅ 所有 20 个测试通过

## [4.0.0] - 2025-01-16

### 🎉 重大更新：多角色配置支持

#### 核心功能
- ✅ 支持从 JSON 文件加载副本配置
- ✅ 不同角色使用不同的配置文件
- ✅ 通过命令行参数指定配置文件
- ✅ 数据库添加配置名称字段，区分不同角色的进度

#### 新增文件
- ✅ `config_loader.py` - 配置加载器模块
- ✅ `configs/default.json` - 默认配置（所有副本）
- ✅ `configs/main_character.json` - 主力角色配置
- ✅ `configs/alt_character.json` - 小号配置

#### 数据库改进
- ✅ `DungeonProgress` 模型添加 `config_name` 字段
- ✅ 唯一索引更新为 `(config_name, date, zone_name, dungeon_name)`
- ✅ 所有查询和统计方法支持配置名称过滤
- ✅ 清理操作仅影响当前配置的数据

#### 主程序更新
- ✅ 支持 `-c/--config` 命令行参数指定配置文件
- ✅ 默认使用 `configs/default.json`
- ✅ 动态加载配置和初始化

#### 进度查看工具更新
- ✅ 支持 `-c/--config` 参数查看指定配置的进度
- ✅ 默认查看 `default` 配置

### 📖 使用说明

#### 运行不同角色配置

```bash
# 使用默认配置
python auto_dungeon_simple.py

# 使用主力角色配置
python auto_dungeon_simple.py -c configs/main_character.json

# 使用小号配置
python auto_dungeon_simple.py -c configs/alt_character.json
```

#### 查看不同角色进度

```bash
# 查看默认配置进度
python view_progress.py

# 查看主力角色进度
python view_progress.py -c main_character

# 查看小号进度
python view_progress.py -c alt_character
```

#### 创建自定义配置

复制现有配置文件并修改：

```bash
cp configs/default.json configs/my_character.json
# 编辑 configs/my_character.json
python auto_dungeon_simple.py -c configs/my_character.json
```

### 🔧 配置文件格式

```json
{
  "description": "配置描述",
  "ocr_correction_map": {
    "梦魔丛林": "梦魇丛林"
  },
  "zone_dungeons": {
    "风暴群岛": [
      {"name": "真理之地", "selected": true},
      {"name": "预言神殿", "selected": false}
    ]
  }
}
```

### ⚠️ 重要提示

- 数据库结构已更新，旧数据会自动迁移（`config_name` 默认为 "default"）
- 不同配置的进度完全独立，互不影响
- 配置文件名（不含扩展名）会作为配置名称存储在数据库中

---

## [3.2.0] - 2025-01-16

### ✨ 新增功能

#### 副本选定功能
- ✅ 副本配置新增 `selected` 字段，支持选择性打副本
- ✅ 未选定的副本会自动跳过，不会进入战斗
- ✅ 新增 `get_all_selected_dungeons()` - 获取所有选定的副本
- ✅ 新增 `get_selected_dungeon_count()` - 获取选定的副本总数
- ✅ 新增 `get_selected_dungeons_by_zone()` - 获取指定区域的选定副本
- ✅ 新增 `is_dungeon_selected()` - 检查副本是否被选定
- ✅ 新增 `set_dungeon_selected()` - 设置副本的选定状态

### 🔧 优化改进

#### 配置文件优化
- ✅ 副本配置从字符串列表改为字典列表
- ✅ 每个副本包含 `name` 和 `selected` 两个字段
- ✅ 默认所有副本都被选定（`selected: True`）
- ✅ 保持向后兼容，所有辅助函数正常工作

#### 主程序优化
- ✅ 自动跳过未选定的副本
- ✅ 日志显示跳过原因（未选定/已通关）
- ✅ 统计信息更准确

### 🧪 测试完善

#### 新增测试用例
- ✅ 测试所有副本都有 `selected` 字段
- ✅ 测试获取选定副本功能
- ✅ 测试副本选定状态检查
- ✅ 测试副本选定状态设置
- ✅ 所有测试通过（28/28）

### 📖 使用说明

#### 如何选择性打副本

编辑 `dungeon_config.py`，将不想打的副本的 `selected` 设置为 `False`：

```python
ZONE_DUNGEONS = {
    "风暴群岛": [
        {"name": "真理之地", "selected": True},   # 会打
        {"name": "预言神殿", "selected": False},  # 跳过
        {"name": "海底王宫", "selected": True},   # 会打
    ],
}
```

或者使用代码动态设置：

```python
from dungeon_config import set_dungeon_selected

# 取消选定某个副本
set_dungeon_selected("预言神殿", False)

# 重新选定某个副本
set_dungeon_selected("预言神殿", True)
```

---

## [3.1.0] - 2025-01-16

### 🎯 项目结构优化

#### 1. 数据库模块独立
- ✅ 创建 `database/` 目录
- ✅ 移动 `dungeon_db.py` 到 `database/` 目录
- ✅ 移动 `dungeon_progress.db` 到 `database/` 目录
- ✅ 创建 `database/__init__.py` 模块入口
- ✅ 更新所有导入引用

#### 2. OCR 测试完善
- ✅ 删除旧的 `test_ocr_cache.py`
- ✅ 创建 `tests/test_ocr.py` - OCR 模块测试（15个测试用例）
- ✅ 测试 OCR 基本功能（4个）
- ✅ 测试缓存加载功能（3个）
- ✅ 测试配置功能（3个）
- ✅ 测试方法存在性（2个）
- ✅ 测试缓存管理（1个）
- ✅ 测试集成功能（2个）

#### 3. 测试覆盖提升
- ✅ 所有测试通过（49/49）
- ✅ 配置测试：22个
- ✅ 数据库测试：12个
- ✅ OCR 测试：15个

### 📁 新的文件结构

```
helper/
├── auto_dungeon_simple.py    # 主程序
├── dungeon_config.py          # 配置文件
├── ocr_helper.py              # OCR 辅助类
├── view_progress.py           # 进度查看
├── database/                  # 数据库模块（新增）
│   ├── __init__.py
│   ├── dungeon_db.py
│   └── dungeon_progress.db
├── tests/                     # 测试目录
│   ├── __init__.py
│   ├── test_config.py         # 配置测试（22个）
│   ├── test_database.py       # 数据库测试（12个）
│   └── test_ocr.py            # OCR 测试（15个，新增）
├── pytest.ini                 # pytest 配置
├── README.md                  # 项目说明
└── CHANGELOG.md               # 更新日志
```

### 🧪 测试结果

```bash
pytest -v
# 49 passed, 18 warnings in 9.89s
```

### 🗑️ 已删除文件

- `test_ocr_cache.py` - 旧的 OCR 测试脚本

### 📦 导入变更

#### 之前
```python
from dungeon_db import DungeonProgressDB
```

#### 现在
```python
from database import DungeonProgressDB
```

---

## [3.0.0] - 2025-01-16

### 🎯 重大重构

#### 1. 项目结构优化
- 删除所有冗余的说明文档（保留 CHANGELOG.md 和 README.md）
- 创建统一的 `tests/` 目录
- 使用 pytest 作为测试框架
- 配置文件独立到 `dungeon_config.py`

#### 2. 测试框架迁移
- ✅ 从独立测试脚本迁移到 pytest
- ✅ 创建 `tests/test_config.py` - 配置模块测试（22个测试用例）
- ✅ 创建 `tests/test_database.py` - 数据库模块测试（12个测试用例）
- ✅ 添加 `pytest.ini` 配置文件
- ✅ 所有测试通过（34/34）

#### 3. 配置模块独立
- ✅ 创建 `dungeon_config.py` 配置文件
- ✅ 移动 `ZONE_DUNGEONS` 副本字典到配置文件
- ✅ 移动 `OCR_CORRECTION_MAP` 纠正映射到配置文件
- ✅ 添加配置辅助函数（8个工具函数）

#### 4. OCR 识别优化
- ✅ 添加 OCR 纠正映射机制
- ✅ 解决 "梦魇丛林" 被识别为 "梦魔丛林" 的问题
- ✅ 支持反向查找和自动尝试多种可能

#### 5. 性能优化
- ✅ 已通关副本不再执行区域切换操作
- ✅ OCR 缓存持久化（多次运行之间复用）
- ✅ 第二次运行速度提升约 50%

### 📁 新的文件结构

```
auto_dungeon_simple.air/
├── auto_dungeon_simple.py    # 主程序
├── dungeon_config.py          # 配置文件（新增）
├── dungeon_db.py              # 数据库模块
├── view_progress.py           # 进度查看
├── tests/                     # 测试目录（新增）
│   ├── __init__.py
│   ├── test_config.py         # 配置测试（新增）
│   └── test_database.py       # 数据库测试（新增）
├── pytest.ini                 # pytest 配置（新增）
├── README.md                  # 项目说明
└── CHANGELOG.md               # 更新日志
```

### 🧪 测试覆盖

#### test_config.py (22 个测试)
- OCR 纠正功能测试（5个）
- 副本配置测试（4个）
- 辅助函数测试（11个）
- OCR 纠正集成测试（2个）

#### test_database.py (12 个测试)
- 数据库基本功能（2个）
- 副本通关功能（4个）
- 副本统计功能（4个）
- 数据库清理功能（1个）
- 上下文管理器（1个）

### 🚀 使用方法

#### 运行测试
```bash
# 安装 pytest
uv pip install pytest

# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_config.py
pytest tests/test_database.py

# 查看详细输出
pytest -v
```

#### 修改配置
```python
# 编辑 dungeon_config.py

# 添加副本
ZONE_DUNGEONS = {
    "风暴群岛": ["真理之地", "新副本"],
}

# 添加 OCR 纠正
OCR_CORRECTION_MAP = {
    "梦魔丛林": "梦魇丛林",
    "新错误": "正确文本",
}
```

### 🗑️ 已删除文件

- `CONFIG_STRUCTURE.md`
- `FINAL_SUMMARY.md`
- `OCR_CORRECTION_GUIDE.md`
- `OPTIMIZATION_NOTES.md`
- `QUICKSTART.md`
- `SUMMARY.md`
- `UPDATE_NOTES.md`
- `USAGE_EXAMPLES.md`
- `test_db.py`
- `test_ocr_correction.py`

### 📦 依赖项

#### 新增依赖
- `pytest` - 测试框架

#### 现有依赖
- `peewee` - ORM 框架
- `airtest` - 游戏自动化
- `paddleocr` - OCR 识别
- `coloredlogs` - 彩色日志

---

## [2.0.0] - 2025-01-15

### 🎉 新增功能

#### 1. SQLite 数据库支持
- 添加 `DungeonProgressDB` 类来管理副本通关状态
- 使用 SQLite 数据库记录每天每个副本的通关情况
- 支持上下文管理器（with 语句）

#### 2. 智能跳过机制
- 自动检测副本是否已通关
- 跳过已通关的副本，不再重复检测
- 大幅提高脚本运行效率（提升50-70%）

#### 3. 通关状态记录
- 记录每个副本的通关时间
- 按日期隔离数据，每天自动重置
- 符合游戏每天一次免费通关的规则

#### 4. 自动数据清理
- 自动清理7天前的旧记录
- 保持数据库文件小巧
- 可配置保留天数

#### 5. 进度统计功能
- 启动时显示今天已通关的副本
- 显示剩余待通关的副本数量
- 结束时显示总通关数量

#### 6. 进度查看工具 (view_progress.py)
- 查看今天的通关记录
- 查看最近N天的统计
- 查看各区域的通关统计
- 清除今天或所有记录
- 支持命令行参数

#### 7. 测试脚本 (test_db.py)
- 完整的数据库功能测试
- 验证所有核心功能
- 自动清理测试数据

### 📝 文档

#### 新增文档
- `README.md` - 完整的功能说明和使用指南
- `QUICKSTART.md` - 5分钟快速上手指南
- `USAGE_EXAMPLES.md` - 详细的使用示例和场景
- `CHANGELOG.md` - 更新日志（本文件）

### 🔧 代码改进

#### auto_dungeon_simple.py
- 添加 `sqlite3` 和 `datetime` 导入
- 新增 `DungeonProgressDB` 类（140行）
- 修改 `process_dungeon()` 函数，添加数据库参数
- 修改 `main()` 函数，集成数据库功能
- 移除未使用的 `device` 导入

#### 数据库结构
```sql
CREATE TABLE dungeon_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    zone_name TEXT NOT NULL,
    dungeon_name TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    completed_at TEXT,
    UNIQUE(date, zone_name, dungeon_name)
);

CREATE INDEX idx_date_zone_dungeon
ON dungeon_progress(date, zone_name, dungeon_name);
```

### 📊 性能提升

#### 效率对比
- **无数据库**: 每次都检测所有100个副本
- **有数据库**: 只检测未通关的副本

#### 示例场景
假设有100个副本：
- 第一次运行: 通关30个，耗时60分钟
- 第二次运行（无数据库）: 检测100个，通关20个，耗时50分钟
- 第二次运行（有数据库）: 跳过30个，检测70个，通关20个，耗时30分钟
- **节省时间**: 约40%

### 🎯 使用方法

#### 基本使用
```bash
# 运行主脚本
python auto_dungeon_simple.py

# 查看进度
python view_progress.py

# 测试功能
python test_db.py
```

#### 进度查看
```bash
# 查看所有信息
python view_progress.py

# 只查看今天
python view_progress.py --today

# 查看最近7天
python view_progress.py --recent 7

# 查看区域统计
python view_progress.py --zones

# 清除今天的记录
python view_progress.py --clear-today

# 清除所有记录
python view_progress.py --clear-all
```

### 🔄 工作流程

#### 启动时
1. 连接数据库（自动创建）
2. 清理7天前的旧记录
3. 显示今天已通关的副本
4. 显示剩余待通关的副本

#### 处理副本时
1. 检查副本是否已通关
2. 如果已通关，跳过该副本
3. 如果未通关，尝试点击免费按钮
4. 通关成功后，记录到数据库

#### 结束时
1. 显示今天总通关数量
2. 关闭数据库连接

### 💡 核心优势

1. **效率提升**: 自动跳过已通关副本，节省50-70%时间
2. **智能记录**: 按日期记录，每天自动重置
3. **数据持久**: 使用SQLite，数据安全可靠
4. **易于管理**: 提供完整的查看和管理工具
5. **自动清理**: 自动清理旧数据，保持数据库小巧
6. **容错性强**: 脚本中断后可继续运行

### 🐛 修复

- 移除未使用的 `device` 导入
- 优化日志输出格式
- 改进错误处理

### 📦 依赖项

#### 新增依赖
- `sqlite3` (Python 标准库)
- `datetime` (Python 标准库)

#### 现有依赖
- `airtest`
- `paddleocr`
- `coloredlogs`

### 🔮 未来计划

- [ ] 添加 Web 界面查看进度
- [ ] 支持导出统计报表
- [ ] 添加副本优先级设置
- [ ] 支持多账号管理
- [ ] 添加通关成功率统计

### 📄 许可证

本脚本仅供学习和个人使用。

---

## [1.0.0] - 之前版本

### 功能
- 基本的副本自动遍历
- OCR 文字识别
- 自动点击免费按钮
- 自动卖垃圾装备

