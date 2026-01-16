"""
副本自动遍历脚本 - 主入口

本文件只保留入口点，所有核心逻辑已迁移到 auto_dungeon_core.py。
"""
from auto_dungeon_core import (
    # 核心类
    DailyCollectManager,
    DungeonStateMachine,
    DeviceManager,
    DependencyContainer,
    # 文本查找函数
    find_text,
    find_text_and_click,
    find_text_and_click_safe,
    find_all_texts,
    find_all,
    text_exists,
    # UI 交互函数
    click_back,
    click_free_button,
    switch_to,
    # 地图和导航函数
    open_map,
    is_on_map,
    is_main_world,
    is_on_character_selection,
    back_to_main,
    switch_to_zone,
    switch_account,
    select_character,
    # 战斗函数
    auto_combat,
    wait_for_main,
    # 业务函数
    daily_collect,
    focus_and_click_dungeon,
    process_dungeon,
    run_dungeon_traversal,
    count_remaining_selected_dungeons,
    show_progress_statistics,
    sell_trashes,
    # 配置和环境
    apply_env_overrides,
    initialize_configs,
    handle_load_account_mode,
    # 通知
    send_bark_notification,
    # 主入口
    main_wrapper,
)

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
    "send_bark_notification",
    # 主入口
    "main_wrapper",
]
