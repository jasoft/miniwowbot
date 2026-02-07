# 副本自动遍历脚本

自动遍历游戏副本，支持多角色配置、进度保存和 OCR 识别纠正。

## 功能特性

- ✅ 多角色配置支持（新增）
- ✅ JSON 配置文件管理
- ✅ 自动遍历所有副本
- ✅ 选择性打副本
- ✅ 记录每天的通关进度
- ✅ 智能跳过已通关副本
- ✅ OCR 识别纠正
- ✅ 缓存持久化

## 快速开始

### 安装依赖

```bash
uv pip install peewee pytest
```

### 运行脚本

```bash
# 使用默认配置
python auto_dungeon_simple.py

# 使用主力角色配置
python auto_dungeon_simple.py -c configs/main_character.json

# 使用小号配置
python auto_dungeon_simple.py -c configs/alt_character.json
```

### 查看进度

```bash
# 查看默认配置进度
python view_progress.py

# 查看主力角色进度
python view_progress.py -c main_character

# 查看小号进度
python view_progress.py -c alt_character
```

### Web Dashboard（Streamlit）

> 用于实时观察运行状态（模拟器在线情况 / 当前职业与副本进度 / 进度统计）。

```bash
# 在项目根目录执行（推荐用 uv 保证依赖一致）
uv run streamlit run view_progress_streamlit.py --server.headless true --server.port 8501

# 浏览器打开
# http://127.0.0.1:8501
```

说明：运行时监控需要本机可执行 `adb`（用于 `adb devices` 检测在线设备）。

## 配置

### 多角色配置（新增）

#### 创建配置文件

复制现有配置并修改：

```bash
cp configs/default.json configs/my_character.json
```

编辑 `configs/my_character.json`：

```json
{
  "description": "我的角色配置",
  "ocr_correction_map": {
    "梦魔丛林": "梦魇丛林"
  },
  "zone_dungeons": {
    "风暴群岛": [
      {"name": "真理之地", "selected": true},
      {"name": "预言神殿", "selected": false},
      {"name": "海底王宫", "selected": true}
    ]
  }
}
```

#### 使用配置

```bash
python auto_dungeon_simple.py -c configs/my_character.json
```

### 预设配置

- `configs/default.json` - 默认配置，所有副本都打
- `configs/main_character.json` - 主力角色配置，选择性打副本
- `configs/alt_character.json` - 小号配置，打简单副本

### 配置文件格式

```json
{
  "description": "配置描述（可选）",
  "ocr_correction_map": {
    "OCR错误文本": "正确文本"
  },
  "zone_dungeons": {
    "区域名称": [
      {"name": "副本名称", "selected": true}
    ]
  }
}
```

## 测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试

```bash
pytest tests/test_config.py
pytest tests/test_database.py
```

### 查看详细输出

```bash
pytest -v
```

## 文件结构

```
helper/
├── auto_dungeon_simple.py    # 主程序
├── dungeon_config.py          # 配置文件
├── ocr_helper.py              # OCR 辅助类
├── view_progress.py           # 进度查看
├── database/                  # 数据库模块
│   ├── __init__.py
│   ├── dungeon_db.py          # 数据库类
│   └── dungeon_progress.db    # 数据库文件
├── tests/                     # 测试目录
│   ├── __init__.py
│   ├── test_config.py         # 配置测试（22个）
│   ├── test_database.py       # 数据库测试（12个）
│   └── test_ocr.py            # OCR 测试（15个）
├── pytest.ini                 # pytest 配置
├── README.md                  # 项目说明
└── CHANGELOG.md               # 更新日志
```

## 更新日志

查看 [CHANGELOG.md](CHANGELOG.md)
