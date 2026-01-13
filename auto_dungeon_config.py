"""
auto_dungeon 配置模块

本模块包含副本自动遍历脚本的所有模板定义和常量配置。
"""
from airtest.core.api import Template

from project_paths import resolve_project_path

# ====== 模板定义 ======

SETTINGS_TEMPLATE = Template(
    str(resolve_project_path("images", "settings_button.png")),
    resolution=(720, 1280),
    record_pos=(0.426, -0.738),
)

GIFTS_TEMPLATE = Template(
    str(resolve_project_path("images", "gifts_button.png")),
    resolution=(720, 1280),
    record_pos=(0.428, -0.424),
)

MAP_DUNGEON_TEMPLATE = Template(
    str(resolve_project_path("images", "map_dungeon.png")),
    resolution=(720, 1280),
    record_pos=(0.35, 0.422),
)

ENTER_GAME_BUTTON_TEMPLATE = Template(
    str(resolve_project_path("images", "enter_game_button.png")),
    resolution=(720, 1280),
)

AUTOCOMBAT_TEMPLATE = Template(
    str(resolve_project_path("images", "autocombat_flag.png")),
    record_pos=(-0.001, -0.299),
    resolution=(720, 1280),
)

# ====== 常量定义 ======

CLICK_INTERVAL = 1
"""点击间隔时间（秒）"""

STOP_FILE = str(resolve_project_path(".stop_dungeon"))
"""停止标记文件路径"""

LAST_OCCURRENCE = 9999
"""用于表示查找最后一个出现的文字"""

# ====== OCR 图像识别策略配置 ======
# 配置 Airtest 图像识别策略：优先使用模板匹配，避免 SIFT/SURF 特征点不足导致的 OpenCV 报错
# "tpl": 模板匹配 (Template Matching)
# "mstpl": 多尺度模板匹配 (Multi-Scale Template Matching)
OCR_STRATEGY = ["mstpl", "tpl", "sift", "brisk"]

# ====== 超时配置 ======

FIND_TIMEOUT = 10
"""默认查找超时时间（秒）"""

FIND_TIMEOUT_TMP = 0.1
"""临时查找超时时间（秒）"""

# ====== 战斗配置 ======

COMBAT_TIMEOUT = 60
"""战斗超时时间（秒）"""

MAIN_WORLD_CHECK_TIMEOUT = 0.3
"""主界面检测超时时间（秒）"""

# ====== 区域划分配置 ======

# 屏幕区域划分（用于优化OCR搜索范围）
# 区域编号从左到右、从上到下排列
SCREEN_REGIONS = {
    "left": [1, 4, 7],      # 左侧区域
    "center": [2, 5, 8],    # 中间区域
    "right": [3, 6, 9],     # 右侧区域
    "top": [1, 2, 3],       # 上方区域
    "middle": [4, 5, 6],    # 中间区域
    "bottom": [7, 8, 9],    # 下方区域
    "all": [1, 2, 3, 4, 5, 6, 7, 8, 9],  # 全部区域
}

# ====== 重试配置 ======

MAX_DUNGEON_ATTEMPTS = 3
"""副本最大尝试次数"""

MAX_ACCOUNT_SWIPE = 10
"""账号列表最大滑动次数"""

MAX_RETINUE_RECRUIT = 4
"""随从招募最大次数"""

# ====== 等待时间配置 ======

MAP_LOAD_WAIT = 2
"""地图加载等待时间（秒）"""

CHAR_SELECTION_WAIT = 3
"""角色选择界面等待时间（秒）"""

AD_WATCH_WAIT = 40
"""广告观看等待时间（秒）"""

SHOP_COOLDOWN = 150
"""商店购买冷却时间（秒）"""
