"""
auto_dungeon 核心功能模块

包含所有核心功能函数，消除全局变量。
"""

import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from airtest.core.api import (
    log as airtest_log,
)
from airtest.core.api import (
    start_app,
    stop_app,
)
from airtest.core.settings import Settings as ST

import auto_dungeon_account
import auto_dungeon_combat
import auto_dungeon_navigation

# Imports for logging slices references
import auto_dungeon_ui
from auto_dungeon_account import switch_account
from auto_dungeon_config import (
    CLICK_INTERVAL,
    FIND_TIMEOUT,
    FIND_TIMEOUT_TMP,
    OCR_STRATEGY,
)

# Import from new modules
from auto_dungeon_container import _container
from auto_dungeon_daily import DailyCollectManager
from auto_dungeon_device import DeviceConnectionError, DeviceManager
from auto_dungeon_navigation import (
    back_to_main,
    is_on_character_selection,
)
from auto_dungeon_notification import send_notification
from auto_dungeon_state_machine import DungeonStateMachine
from auto_dungeon_ui import (
    click_back,
    find_text_and_click_safe,
    sell_trashes,
)
from auto_dungeon_utils import check_stop_signal, sleep
from coordinates import SKILL_POSITIONS as DEFAULT_SKILL_POSITIONS
from database import DungeonProgressDB
from error_dialog_monitor import ErrorDialogMonitor
from logger_config import setup_logger_from_config
from system_config_loader import load_system_config

# 初始化模块级 logger
logger = logging.getLogger(__name__)

# 配置 Airtest 图像识别策略
ST.CVSTRATEGY = OCR_STRATEGY
airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)
ST.FIND_TIMEOUT = FIND_TIMEOUT
ST.FIND_TIMEOUT_TMP = FIND_TIMEOUT_TMP

# 设置 OCR 日志级别
logging.getLogger("ocr_helper").setLevel(logging.DEBUG)


# ====== 核心业务函数 ======

# 兼容层：保留历史上可 monkeypatch 的符号，供旧测试与外部脚本使用。
wait = auto_dungeon_combat.wait
touch = auto_dungeon_combat.touch
is_main_world = auto_dungeon_navigation.is_main_world
SKILL_POSITIONS = DEFAULT_SKILL_POSITIONS


def auto_combat(completed_dungeons: int = 0, total_dungeons: int = 0) -> None:
    """执行自动战斗并兼容历史 monkeypatch 行为。

    Args:
        completed_dungeons: 当前已完成副本数。
        total_dungeons: 总副本数，0 表示按时间进度模式运行。
    """
    auto_dungeon_combat.find_text_and_click_safe = find_text_and_click_safe
    auto_dungeon_combat.wait = wait
    auto_dungeon_combat.check_stop_signal = check_stop_signal
    auto_dungeon_combat.is_main_world = is_main_world
    auto_dungeon_combat.touch = touch
    auto_dungeon_combat.sleep = sleep
    auto_dungeon_combat.SKILL_POSITIONS = SKILL_POSITIONS
    auto_dungeon_combat.auto_combat(
        completed_dungeons=completed_dungeons,
        total_dungeons=total_dungeons,
    )


def process_dungeon(
    dungeon_name: str,
    zone_name: str,
    index: int,
    total: int,
    db: DungeonProgressDB,
    completed_dungeons: int = 0,
    remaining_dungeons: int = 0,
    state_machine: Optional[DungeonStateMachine] = None,
) -> bool:
    """处理单个副本"""
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

    if state_machine is None:
        logger.error("❌ 状态机未初始化，无法处理副本")
        return False

    # 处理日常任务
    if zone_name == "日常任务":
        logger.info(f"📋 执行日常任务: {dungeon_name}")
        manager = DailyCollectManager(_container.config_loader, db)
        if manager.execute_task(dungeon_name):
            db.mark_dungeon_completed(zone_name, dungeon_name)
            return True
        return False

    if not state_machine.prepare_dungeon_state(
        zone_name=zone_name, dungeon_name=dungeon_name, max_attempts=3
    ):
        state_machine.ensure_main()
        return False

    battle_started = state_machine.start_battle_state(
        dungeon_name=dungeon_name,
        completed_dungeons=completed_dungeons,
        total_dungeons=remaining_dungeons,
    )

    if not battle_started:
        logger.warning("⚠️ 无免费按钮，标记为已完成")
        db.mark_dungeon_completed(zone_name, dungeon_name)
        click_back()
        state_machine.return_to_main_state()
        return True

    logger.info(f"✅ 完成: {dungeon_name}")
    state_machine.complete_battle_state()
    db.mark_dungeon_completed(zone_name, dungeon_name)
    sleep(CLICK_INTERVAL)
    state_machine.return_to_main_state()
    return True


def count_remaining_selected_dungeons(db: DungeonProgressDB) -> int:
    """统计未完成的选定副本数量"""
    zone_dungeons = (
        _container.config_loader.get_zone_dungeons() if _container.config_loader else None
    )
    if zone_dungeons is None:
        logger.warning("⚠️ 配置未初始化，无法计算剩余副本")
        return 0

    remaining = 0
    for zone_name, dungeons in zone_dungeons.items():
        for dungeon_dict in dungeons:
            if not dungeon_dict.get("selected", True):
                continue
            if not db.is_dungeon_completed(zone_name, dungeon_dict["name"]):
                remaining += 1
    return remaining


def show_progress_statistics(db: DungeonProgressDB) -> Tuple[int, int, int]:
    """显示进度统计信息"""
    db.cleanup_old_records(days_to_keep=7)

    completed_count = db.get_today_completed_count()
    if completed_count > 0:
        logger.info(f"📊 今天已通关 {completed_count} 个副本")
        completed_dungeons = db.get_today_completed_dungeons()
        for zone, dungeon in completed_dungeons[:5]:
            logger.info(f"  ✅ {zone} - {dungeon}")
        if len(completed_dungeons) > 5:
            logger.info(f"  ... 还有 {len(completed_dungeons) - 5} 个")
        logger.info("")

    zone_dungeons = _container.config_loader.get_zone_dungeons() if _container.config_loader else {}
    total_selected_dungeons = sum(
        sum(1 for d in dungeons if d.get("selected", True)) for dungeons in zone_dungeons.values()
    )
    total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())

    remaining_dungeons_detail = []
    for zone_name, dungeons in zone_dungeons.items():
        for dungeon in dungeons:
            if not dungeon.get("selected", True):
                continue
            if not db.is_dungeon_completed(zone_name, dungeon["name"]):
                remaining_dungeons_detail.append((zone_name, dungeon["name"]))

    logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本")
    logger.info(f"📊 选定: {total_selected_dungeons} 个副本")
    logger.info(f"📊 已完成: {completed_count} 个副本")

    if completed_count >= total_selected_dungeons:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 今天所有选定的副本都已完成！")
        logger.info("=" * 60)
        logger.info("💤 无需执行任何操作，脚本退出")
        return completed_count, total_selected_dungeons, total_dungeons

    remaining = len(remaining_dungeons_detail)
    logger.info(f"📊 剩余: {remaining} 个副本待通关")
    if remaining_dungeons_detail:
        logger.info("📋 待通关副本清单:")
        for zone_name, dungeon_name in remaining_dungeons_detail:
            logger.info(f"  • {zone_name} - {dungeon_name}")
    logger.info("")

    return completed_count, total_selected_dungeons, total_dungeons


def run_dungeon_traversal(
    db: DungeonProgressDB, total_dungeons: int, state_machine: DungeonStateMachine
) -> int:
    """执行副本遍历主循环"""
    if _container.config_loader is None or state_machine is None:
        logger.error("❌ 配置未初始化")
        return 0

    zone_dungeons = _container.config_loader.get_zone_dungeons()
    if zone_dungeons is None:
        logger.error("❌ 区域副本配置未初始化")
        return 0

    dungeon_index = 0
    processed_dungeons = 0
    remaining_dungeons = count_remaining_selected_dungeons(db)

    logger.info(f"📊 需要完成的副本总数: {remaining_dungeons}")
    completed_today = db.get_today_completed_count()
    logger.info(f"📊 今天已完成的副本数: {completed_today}")

    state_machine.ensure_main()

    for zone_idx, (zone_name, dungeons) in enumerate(zone_dungeons.items(), 1):
        logger.info(f"\n{'#' * 60}")
        logger.info(f"# 🌍 [{zone_idx}/{len(zone_dungeons)}] 区域: {zone_name}")
        logger.info(f"# 🎯 副本数: {len(dungeons)}")
        logger.info(f"{'#' * 60}")

        for dungeon_dict in dungeons:
            if check_stop_signal():
                logger.info(f"\n📊 统计: 本次运行完成 {processed_dungeons} 个副本")
                logger.info("👋 已停止执行")
                state_machine.ensure_main()
                return processed_dungeons

            dungeon_name = dungeon_dict["name"]
            is_selected = dungeon_dict["selected"]
            dungeon_index += 1

            if not is_selected:
                logger.info(f"⏭️ [{dungeon_index}/{total_dungeons}] 未选定，跳过: {dungeon_name}")
                continue

            if db.is_dungeon_completed(zone_name, dungeon_name):
                logger.info(f"⏭️ [{dungeon_index}/{total_dungeons}] 已通关，跳过: {dungeon_name}")
                continue

            if process_dungeon(
                dungeon_name,
                zone_name,
                dungeon_index,
                total_dungeons,
                db,
                completed_today + processed_dungeons,
                remaining_dungeons,
                state_machine=state_machine,
            ):
                processed_dungeons += 1
                if processed_dungeons % 3 == 0:
                    if state_machine.sell_loot():
                        state_machine.finish_sell_loot()
                    else:
                        sell_trashes()
                        back_to_main()
                        state_machine.ensure_main()

        logger.info(f"\n✅ 完成区域: {zone_name}")

    return processed_dungeons


# ====== 命令行参数解析 ======


def parse_arguments():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(description="副本自动遍历脚本")
    parser.add_argument(
        "-c", "--config", type=str, default="configs/default.json", help="配置文件路径"
    )
    parser.add_argument("--load-account", type=str, help="加载指定账号后退出")
    parser.add_argument("--emulator", type=str, help="指定模拟器网络地址")
    parser.add_argument("--memlog", action="store_true", help="启用内存监控日志")
    parser.add_argument(
        "-e", "--env", type=str, action="append", dest="env_overrides", help="环境变量覆盖"
    )
    parser.add_argument("--max-iterations", type=int, default=1, help="限制副本遍历的最大轮数")
    return parser.parse_args()


def apply_env_overrides(env_overrides: List[str]) -> Dict[str, Any]:
    """应用命令行环境变量覆盖"""
    overrides = {}
    if not env_overrides:
        return overrides

    for override in env_overrides:
        if "=" not in override:
            logger.warning(f"⚠️ 无效的环境变量格式: {override}，应为 key=value")
            continue
        key, value = override.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.lower() == "true":
            overrides[key] = True
        elif value.lower() == "false":
            overrides[key] = False
        elif value.isdigit():
            overrides[key] = int(value)
        else:
            overrides[key] = value

        logger.info(f"📝 环境变量覆盖: {key} = {overrides[key]}")

    return overrides


def handle_load_account_mode(account_name: str, emulator_name: Optional[str] = None):
    """处理账号加载模式"""
    logger.info("\n" + "=" * 60)
    logger.info("🔄 账号加载模式")
    logger.info("=" * 60 + "\n")
    logger.info(f"📱 目标账号: {account_name}")

    try:
        device_manager = DeviceManager()
        device_manager.initialize(emulator_name=emulator_name)

        # 注入依赖
        _container.emulator_manager = device_manager.emulator_manager
        _container.ocr_helper = device_manager.get_ocr_helper()
        _container.game_actions = device_manager.get_game_actions()
        _container.target_emulator = device_manager.get_target_emulator()

    except Exception as e:
        logger.error(f"❌ {e}")
        send_notification(
            "副本助手 - 错误",
            f"模拟器 {emulator_name} 未运行或未连接",
            level="timeSensitive",
        )
        sys.exit(1)

    try:
        switch_account(account_name)
        logger.info(f"✅ 成功加载账号: {account_name}")
        logger.info("=" * 60 + "\n")
    except Exception as e:
        logger.error(f"❌ 加载账号失败: {e}")
        sys.exit(1)


def initialize_configs(config_path: str, env_overrides: Optional[List[str]] = None):
    """初始化系统配置和用户配置"""
    # 加载系统配置
    try:
        _container.system_config = load_system_config()
    except Exception as e:
        logger.warning(f"⚠️ 加载系统配置失败: {e}，使用默认配置")
        _container.system_config = None

    # 加载用户配置
    try:
        from config_loader import load_config

        _container.config_loader = load_config(config_path)
        _container.config_name = _container.config_loader.get_config_name()

        # 重新初始化日志
        new_logger = setup_logger_from_config(use_color=True)
        globals()["logger"] = new_logger

        # 更新全局日志上下文
        from logger_config import update_log_context

        update_log_context({"config": _container.config_name})

        # 应用环境变量覆盖
        if env_overrides:
            overrides = apply_env_overrides(env_overrides)
            for key, value in overrides.items():
                if hasattr(_container.config_loader, key):
                    logger.info(f"🔄 覆盖配置: {key} = {value}")
                    setattr(_container.config_loader, key, value)
                else:
                    logger.warning(f"⚠️ 配置中不存在属性: {key}")

    except Exception as e:
        logger.error(f"❌ 加载配置失败: {e}")
        sys.exit(1)


def attach_file_logger(emulator_name: str):
    """附加文件日志处理器"""
    from logger_config import attach_emulator_file_handler

    try:
        attach_emulator_file_handler(
            emulator_name=emulator_name or "unknown",
            config_name=_container.config_name or "unknown",
            log_dir="log",
            level="DEBUG",
        )
    except Exception as e:
        logger.warning(f"⚠️ 初始化文件日志处理器失败: {e}")


def start_error_monitor():
    """启动错误对话框监控器"""
    _container.error_dialog_monitor = ErrorDialogMonitor(logger)
    _container.error_dialog_monitor.start()


def stop_error_monitor():
    """停止错误对话框监控器"""
    if _container.error_dialog_monitor:
        _container.error_dialog_monitor.stop()
        _container.error_dialog_monitor = None


# ====== 主函数 ======


def main():
    """主函数"""
    args = parse_arguments()

    # 初始化配置（必须在使用 logger 之前）
    initialize_configs(args.config, args.env_overrides)

    # 现在 logger 已经正确设置了 config 上下文
    if not args.load_account:
        logger.info("\n" + "=" * 60)
        logger.info("🎮 副本自动遍历脚本")
        logger.info("=" * 60 + "\n")

    if args.memlog:
        try:
            from memory_monitor import start_memory_monitor

            start_memory_monitor(logger, interval_sec=10.0, enable_tracemalloc=True)
            logger.info("已启用内存监控")
        except Exception as e:
            logger.warning(f"启用内存监控失败: {e}")

    attach_file_logger(args.emulator)

    if args.load_account:
        handle_load_account_mode(args.load_account, args.emulator)
        return

    if _container.config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)

    with DungeonProgressDB(config_name=_container.config_loader.get_config_name()) as db:
        completed_count, total_selected, total = show_progress_statistics(db)

        if completed_count >= total_selected:
            logger.info("✅ 无需启动模拟器，脚本退出")
            return

    # 初始化设备
    try:
        # 创建 DeviceManager 实例
        device_manager = DeviceManager()

        # 获取 OCR 纠错映射
        correction_map = None
        if _container.config_loader:
            correction_map = _container.config_loader.get_ocr_correction_map()

        # 初始化设备
        device_manager.initialize(emulator_name=args.emulator, correction_map=correction_map)

        # 将组件注入到依赖容器
        _container.emulator_manager = device_manager.emulator_manager
        _container.ocr_helper = device_manager.get_ocr_helper()
        _container.game_actions = device_manager.get_game_actions()
        _container.target_emulator = device_manager.get_target_emulator()

    except DeviceConnectionError as e:
        logger.error(f"❌ 设备连接错误: {e}")
        send_notification(
            "副本助手 - 错误",
            f"设备连接失败: {e}",
            level="timeSensitive",
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 设备初始化失败: {e}")
        sys.exit(1)

    state_machine = DungeonStateMachine()

    # 启动游戏
    logger.info("关闭游戏...")
    stop_app("com.ms.ysjyzr")
    sleep(2, "关闭游戏")

    logger.info("启动游戏")
    start_app("com.ms.ysjyzr")

    # 等待进入角色选择界面
    if is_on_character_selection(120):
        logger.info("已在角色选择界面")

    # 选择角色
    char_class = _container.config_loader.get_char_class()
    if char_class:
        logger.info(f"开始选择角色: {char_class}")
        state_machine.select_character_state(char_class=char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")
        state_machine.ensure_main()

    # 执行副本遍历
    with DungeonProgressDB(config_name=_container.config_loader.get_config_name()) as db:
        iteration = 1
        max_iterations = args.max_iterations or 1

        while iteration <= max_iterations:
            logger.info(f"\n🔁 开始第 {iteration} 轮副本遍历…")
            run_dungeon_traversal(db, total, state_machine)

            remaining = count_remaining_selected_dungeons(db)
            if remaining <= 0:
                break

            logger.warning(f"⚠️ 第 {iteration} 轮结束后仍有 {remaining} 个副本未完成，准备继续")
            iteration += 1

        if iteration > max_iterations:
            remaining = count_remaining_selected_dungeons(db)
            if remaining > 0:
                logger.warning(
                    f"⚠️ 已达到最大轮数 {max_iterations}，仍有 {remaining} 个副本未完成；为避免卡住已优雅退出"
                )

        logger.info("\n" + "=" * 60)
        logger.info(f"🎉 全部完成！今天共通关 {db.get_today_completed_count()} 个副本")
        logger.info("=" * 60 + "\n")
        state_machine.ensure_main()


def main_wrapper():
    """主函数包装器 - 处理超时和重启逻辑"""
    global logger

    max_restarts = 10
    restart_count = 0

    while restart_count < max_restarts:
        try:
            start_error_monitor()
            main()
            return

        except TimeoutError as e:
            restart_count += 1
            logger.error(f"\n❌ 检测到超时错误: {e}")
            logger.error("⏱️ 操作超时，可能是网络错误或识别失败导致的卡死")
            airtest_log("超时错误" + str(e), snapshot=True)

            if restart_count < max_restarts:
                logger.warning(f"\n🔄 正在重启程序... (第 {restart_count}/{max_restarts} 次重启)")
                send_notification(
                    "副本助手 - 超时重启",
                    f"程序因超时重启 ({restart_count}/{max_restarts})",
                    level="timeSensitive",
                )
                _container.reset()
                time.sleep(5)
                continue
            else:
                logger.error(f"\n❌ 已达到最大重启次数 ({max_restarts})，程序退出")
                send_notification(
                    "副本助手 - 严重错误",
                    "程序因多次超时失败退出",
                    level="timeSensitive",
                )
                sys.exit(1)

        except KeyboardInterrupt:
            logger.info("\n\n⛔ 用户中断，程序退出")
            sys.exit(0)

        except Exception as e:
            import traceback

            logger.error(f"\n❌ 发生未预期的错误: {e}")
            error_traceback = traceback.format_exc()
            logger.error(error_traceback)
            logger.critical(f"脚本异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}")
            send_notification("副本助手 - 错误", f"程序发生错误: {str(e)}", level="timeSensitive")
            sys.exit(1)

        finally:
            stop_error_monitor()


# ====== 日志切面 ======


def setup_logging_slices():
    """设置日志切面"""
    from logger_config import apply_logging_slice

    apply_logging_slice(
        [
            (auto_dungeon_ui, "find_text"),
            (auto_dungeon_ui, "text_exists"),
            (auto_dungeon_ui, "find_text_and_click"),
            (auto_dungeon_ui, "find_text_and_click_safe"),
            (auto_dungeon_navigation, "is_main_world"),
            (auto_dungeon_navigation, "open_map"),
            (auto_dungeon_combat, "auto_combat"),
            (auto_dungeon_account, "select_character"),
            (auto_dungeon_account, "wait_for_main"),
            (auto_dungeon_navigation, "switch_to_zone"),
            (auto_dungeon_ui, "sell_trashes"),
            (auto_dungeon_account, "switch_account"),
            (auto_dungeon_navigation, "back_to_main"),
            (auto_dungeon_navigation, "focus_and_click_dungeon"),
            (sys.modules[__name__], "process_dungeon"),
            (sys.modules[__name__], "run_dungeon_traversal"),
            (sys.modules[__name__], "initialize_configs"),
            (sys.modules[__name__], "show_progress_statistics"),
            (sys.modules[__name__], "apply_env_overrides"),
            (sys.modules[__name__], "handle_load_account_mode"),
            (sys.modules[__name__], "main_wrapper"),
            (sys.modules[__name__], "main"),
        ],
        level="DEBUG",
    )


if __name__ == "__main__":
    main_wrapper()
