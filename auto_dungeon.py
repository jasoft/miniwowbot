"""
副本自动遍历脚本 - 主入口

本文件只保留入口点，所有核心逻辑已迁移到 auto_dungeon_core.py。
"""

from auto_dungeon_account import select_character, switch_account, wait_for_main
from auto_dungeon_combat import auto_combat
from auto_dungeon_container import DependencyContainer
from auto_dungeon_core import (
    DungeonStateMachine,
    apply_env_overrides,
    count_remaining_selected_dungeons,
    handle_load_account_mode,
    initialize_configs,
    main_wrapper,
    process_dungeon,
    run_dungeon_traversal,
    show_progress_statistics,
)
from auto_dungeon_daily import DailyCollectManager, execute_daily_collect
from auto_dungeon_device import DeviceManager
from auto_dungeon_navigation import (
    back_to_main,
    focus_and_click_dungeon,
    is_main_world,
    is_on_character_selection,
    is_on_map,
    open_map,
    switch_to_zone,
)
from auto_dungeon_notification import (
    send_notification,
    send_pushover_html_notification,
    send_pushover_notification,
)
from auto_dungeon_ui import (
    click_back,
    click_free_button,
    find_all,
    find_all_texts,
    find_text,
    find_text_and_click,
    find_text_and_click_safe,
    sell_trashes,
    switch_to,
    text_exists,
)

# 向后兼容：daily_collect 函数别名
daily_collect = execute_daily_collect

# 向后兼容：状态机别名
AutoDungeonStateMachine = DungeonStateMachine

# 向后兼容：导出常用函数
__all__ = [
    # 核心类
    "DailyCollectManager",
    "DungeonStateMachine",
    "AutoDungeonStateMachine",
    "DeviceManager",
    "DependencyContainer",
    # 文本查找函数
    "find_text",
    "find_text_and_click",
    "find_text_and_click_safe",
    "find_all_texts",
    "find_all",
    "text_exists",
    # UI 交互函数
    "click_back",
    "click_free_button",
    "switch_to",
    # 地图和导航函数
    "open_map",
    "is_on_map",
    "is_main_world",
    "is_on_character_selection",
    "back_to_main",
    "switch_to_zone",
    "switch_account",
    "select_character",
    # 战斗函数
    "auto_combat",
    "wait_for_main",
    # 业务函数
    "daily_collect",
    "focus_and_click_dungeon",
    "process_dungeon",
    "run_dungeon_traversal",
    "count_remaining_selected_dungeons",
    "show_progress_statistics",
    "sell_trashes",
    # 配置和环境
    "apply_env_overrides",
    "initialize_configs",
    "handle_load_account_mode",
    # 通知
    "send_notification",
    "send_notification",
    "send_pushover_notification",
    "send_pushover_html_notification",
    # 主入口
    "main_wrapper",
]
