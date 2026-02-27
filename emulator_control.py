"""模拟器控制工具。

提供 cron 场景需要的模拟器控制能力：
1. 按单个会话重启对应模拟器（优先 MuMuManager，回退 ADB）。
2. 关闭全部模拟器（用于紧急停机）。
3. 强制终止模拟器相关进程（用于兜底清理）。
"""

from __future__ import annotations

import json
import locale
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

DEFAULT_EMULATOR_PROCESS_NAMES: tuple[str, ...] = (
    # MuMu
    "MuMuPlayer.exe",
    "MuMuPlayerGlobal.exe",
    "MuMuVMMHeadless.exe",
    "NemuHeadless.exe",
    "NemuPlayer.exe",
    # BlueStacks
    "HD-Player.exe",
    "HD-Agent.exe",
    "HD-Frontend.exe",
    "HD-MultiInstanceManager.exe",
    "HD-Adb.exe",
    "BstkSVC.exe",
    "BlueStacksHelper.exe",
    "Bluestacks.exe",
)
MUMU_PROCESS_NAMES: tuple[str, ...] = (
    "MuMuPlayer.exe",
    "MuMuPlayerGlobal.exe",
    "MuMuVMMHeadless.exe",
    "NemuHeadless.exe",
    "NemuPlayer.exe",
)


@dataclass(frozen=True)
class EmulatorRestartConfig:
    """单会话模拟器重启配置。

    Attributes:
        emulator: 模拟器地址，例如 ``192.168.1.150:5555``。
        shutdown_cmd: 自定义关闭命令（可选）。
        start_cmd: 自定义启动命令（可选）。
        mumu_vm_index: MuMu 单实例索引（可选），例如 ``0``。
        mumu_manager_path: MuMuManager.exe 路径（可选）。
    """

    emulator: str
    shutdown_cmd: Optional[str] = None
    start_cmd: Optional[str] = None
    mumu_vm_index: Optional[str] = None
    mumu_manager_path: Optional[str] = None


def decode_process_output(raw_output: Optional[bytes]) -> str:
    """安全解码子进程输出。

    Args:
        raw_output: 子进程原始字节输出。

    Returns:
        解码后的文本。若无法准确匹配编码则使用替换字符兜底。
    """
    if raw_output is None:
        return ""

    candidate_encodings = (
        "utf-8",
        locale.getpreferredencoding(False) or "utf-8",
        "gbk",
    )
    for encoding in candidate_encodings:
        try:
            return raw_output.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_output.decode("utf-8", errors="replace")


def _normalize_emulator(emulator: str) -> str:
    """规范化模拟器地址。

    Args:
        emulator: 用户传入的模拟器地址。

    Returns:
        规范化后的模拟器地址。
    """
    value = str(emulator).strip()
    if value.lower().startswith("android://"):
        parts = value.split("/")
        if parts:
            return parts[-1].strip()
    return value


def parse_emulator_port(emulator: str) -> Optional[int]:
    """解析模拟器端口。

    Args:
        emulator: 模拟器地址。

    Returns:
        端口号；若无法解析则返回 ``None``。
    """
    normalized = _normalize_emulator(emulator)
    if ":" not in normalized:
        return None
    raw_port = normalized.rsplit(":", 1)[-1]
    try:
        return int(raw_port)
    except ValueError:
        return None


def find_mumu_manager_path(preferred_path: Optional[str] = None) -> Optional[Path]:
    """查找 MuMuManager.exe 路径。

    Args:
        preferred_path: 优先使用的路径。

    Returns:
        可用路径；找不到时返回 ``None``。
    """
    candidates: list[Path] = []
    if preferred_path:
        candidates.append(Path(preferred_path))

    env_path = os.getenv("MUMU_MANAGER_PATH")
    if env_path:
        candidates.append(Path(env_path))

    which_path = shutil.which("MuMuManager.exe")
    if which_path:
        candidates.append(Path(which_path))

    candidates.extend(
        [
            Path(r"C:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe"),
            Path(r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe"),
            Path(r"D:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe"),
        ]
    )

    visited: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in visited:
            continue
        visited.add(key)
        if candidate.exists():
            return candidate
    return None


def parse_mumu_info_output(raw_text: str) -> list[dict[str, Any]]:
    """解析 MuMuManager 的实例信息输出。

    Args:
        raw_text: ``MuMuManager.exe info -v all`` 原始文本。

    Returns:
        实例信息列表。解析失败时返回空列表。
    """
    payload = _try_parse_json(raw_text.strip())
    if payload is None:
        payload = _try_parse_embedded_json(raw_text)
    return _normalize_mumu_payload(payload)


def match_mumu_vm_index(instances: Sequence[dict[str, Any]], emulator: str) -> Optional[str]:
    """按模拟器地址端口匹配 MuMu 实例索引。

    Args:
        instances: MuMu 实例信息列表。
        emulator: 模拟器地址。

    Returns:
        匹配到的实例索引；未匹配时返回 ``None``。
    """
    target_port = parse_emulator_port(emulator)
    if target_port is None:
        return None

    for item in instances:
        adb_port = item.get("adb_port")
        index = item.get("index")
        if index is None:
            continue
        try:
            if int(adb_port) == target_port:
                return str(index)
        except (TypeError, ValueError):
            continue
    return None


def restart_emulator(config: EmulatorRestartConfig, logger: logging.Logger) -> bool:
    """重启单个会话对应的模拟器。

    优先级：
    1. 会话自定义 ``shutdown_cmd/start_cmd``。
    2. MuMuManager 单实例 ``shutdown + launch``。
    3. ADB 单设备 ``emu kill + connect``。

    Args:
        config: 会话重启配置。
        logger: 日志对象。

    Returns:
        是否成功执行“关闭 + 启动”。
    """
    logger.info(f"🔄 开始重启模拟器: {config.emulator}")
    normalized_emulator = _normalize_emulator(config.emulator)

    shutdown_ok = _shutdown_single_emulator(normalized_emulator, config, logger)
    time.sleep(3)
    start_ok = _start_single_emulator(normalized_emulator, config, logger)

    if shutdown_ok and start_ok:
        logger.info(f"✅ 模拟器重启成功: {normalized_emulator}")
        return True

    logger.warning(
        f"⚠️ 模拟器重启未完全成功: {normalized_emulator} "
        f"(shutdown_ok={shutdown_ok}, start_ok={start_ok})"
    )
    return False


def shutdown_all_emulators(
    emulators: Sequence[str],
    logger: logging.Logger,
    *,
    mumu_manager_path: Optional[str] = None,
) -> None:
    """关闭全部模拟器。

    Args:
        emulators: 需要清理 ADB 连接的模拟器地址列表。
        logger: 日志对象。
        mumu_manager_path: MuMuManager.exe 路径（可选）。

    Returns:
        None
    """
    manager_path = find_mumu_manager_path(mumu_manager_path)
    should_try_mumu = manager_path is not None
    if should_try_mumu and os.name == "nt" and not _has_any_running_process(MUMU_PROCESS_NAMES):
        logger.info("ℹ️ 未检测到 MuMu 运行进程，跳过 `MuMuManager control -v all shutdown`")
        should_try_mumu = False

    if should_try_mumu and manager_path is not None:
        _run_list_cmd(
            [str(manager_path), "control", "-v", "all", "shutdown"],
            logger,
            "关闭全部 MuMu 模拟器",
            timeout=120,
        )
    else:
        logger.info("ℹ️ 未检测到 MuMuManager，跳过 `control -v all shutdown`")

    adb_path = _resolve_adb_path()
    for emulator in emulators:
        normalized = _normalize_emulator(emulator)
        _run_list_cmd(
            [adb_path, "disconnect", normalized],
            logger,
            f"断开 ADB 连接 {normalized}",
            timeout=8,
            allow_failure=True,
        )
        _run_list_cmd(
            [adb_path, "-s", normalized, "emu", "kill"],
            logger,
            f"发送 emu kill 到 {normalized}",
            timeout=8,
            allow_failure=True,
        )

    _run_list_cmd(
        [adb_path, "kill-server"],
        logger,
        "停止 ADB 服务",
        timeout=8,
        allow_failure=True,
    )


def force_kill_processes(process_names: Sequence[str], logger: logging.Logger) -> None:
    """强制结束指定进程名。

    Args:
        process_names: 进程名列表，例如 ``MuMuPlayer.exe``。
        logger: 日志对象。

    Returns:
        None
    """
    if os.name == "nt":
        for process_name in process_names:
            _run_list_cmd(
                ["taskkill", "/F", "/T", "/IM", process_name],
                logger,
                f"强制结束进程 {process_name}",
                timeout=6,
                allow_failure=True,
            )
        return

    for process_name in process_names:
        _run_list_cmd(
            ["pkill", "-9", "-f", process_name],
            logger,
            f"强制结束进程 {process_name}",
            timeout=6,
            allow_failure=True,
        )


def _shutdown_single_emulator(
    emulator: str,
    config: EmulatorRestartConfig,
    logger: logging.Logger,
) -> bool:
    """执行单模拟器关闭。

    Args:
        emulator: 规范化后的模拟器地址。
        config: 重启配置。
        logger: 日志对象。

    Returns:
        关闭步骤是否成功。
    """
    if config.shutdown_cmd:
        return _run_shell_cmd(config.shutdown_cmd, logger, f"执行自定义关闭命令: {emulator}")

    vm_index, manager_path = _resolve_vm_index_and_manager(config, logger)
    if vm_index and manager_path:
        return _run_list_cmd(
            [str(manager_path), "control", "-v", vm_index, "shutdown"],
            logger,
            f"关闭 MuMu 模拟器实例 {vm_index}",
            timeout=90,
        )

    adb_path = _resolve_adb_path()
    disconnect_ok = _run_list_cmd(
        [adb_path, "disconnect", emulator],
        logger,
        f"断开 ADB 连接 {emulator}",
        timeout=20,
        allow_failure=True,
    )
    kill_ok = _run_list_cmd(
        [adb_path, "-s", emulator, "emu", "kill"],
        logger,
        f"发送 emu kill 到 {emulator}",
        timeout=20,
        allow_failure=True,
    )
    return disconnect_ok or kill_ok


def _start_single_emulator(
    emulator: str,
    config: EmulatorRestartConfig,
    logger: logging.Logger,
) -> bool:
    """执行单模拟器启动。

    Args:
        emulator: 规范化后的模拟器地址。
        config: 重启配置。
        logger: 日志对象。

    Returns:
        启动步骤是否成功。
    """
    if config.start_cmd:
        return _run_shell_cmd(config.start_cmd, logger, f"执行自定义启动命令: {emulator}")

    vm_index, manager_path = _resolve_vm_index_and_manager(config, logger)
    if vm_index and manager_path:
        return _run_list_cmd(
            [str(manager_path), "control", "-v", vm_index, "launch"],
            logger,
            f"启动 MuMu 模拟器实例 {vm_index}",
            timeout=90,
        )

    adb_path = _resolve_adb_path()
    return _run_list_cmd(
        [adb_path, "connect", emulator],
        logger,
        f"重新连接 ADB {emulator}",
        timeout=20,
        allow_failure=True,
    )


def _resolve_vm_index_and_manager(
    config: EmulatorRestartConfig,
    logger: logging.Logger,
) -> tuple[Optional[str], Optional[Path]]:
    """解析单会话对应的 MuMu 实例索引与可执行路径。

    Args:
        config: 重启配置。
        logger: 日志对象。

    Returns:
        二元组 ``(vm_index, manager_path)``；任一不可用时返回 ``None``。
    """
    manager_path = find_mumu_manager_path(config.mumu_manager_path)
    if manager_path is None:
        return (None, None)

    if config.mumu_vm_index:
        return (str(config.mumu_vm_index), manager_path)

    instances = _query_mumu_instances(manager_path, logger)
    if not instances:
        return (None, manager_path)

    vm_index = match_mumu_vm_index(instances, config.emulator)
    if vm_index:
        return (vm_index, manager_path)

    logger.warning(
        f"⚠️ 未能通过端口自动匹配 MuMu 实例: emulator={config.emulator}，"
        "建议在 emulators.json 中设置 mumu_vm_index"
    )
    return (None, manager_path)


def _query_mumu_instances(manager_path: Path, logger: logging.Logger) -> list[dict[str, Any]]:
    """查询 MuMu 实例列表。

    Args:
        manager_path: MuMuManager.exe 路径。
        logger: 日志对象。

    Returns:
        实例信息列表。
    """
    try:
        result = subprocess.run(
            [str(manager_path), "info", "-v", "all"],
            capture_output=True,
            text=False,
            timeout=60,
        )
    except Exception as exc:
        logger.warning(f"⚠️ 读取 MuMu 实例信息失败: {exc}")
        return []

    if result.returncode != 0:
        stderr_text = decode_process_output(result.stderr).strip()
        logger.warning(f"⚠️ MuMu info 执行失败: {stderr_text}")
        return []

    stdout_text = decode_process_output(result.stdout)
    instances = parse_mumu_info_output(stdout_text)
    if not instances:
        logger.warning("⚠️ MuMu info 输出无法解析为实例列表")
    return instances


def _run_shell_cmd(command: str, logger: logging.Logger, desc: str) -> bool:
    """执行 shell 字符串命令。

    Args:
        command: shell 命令字符串。
        logger: 日志对象。
        desc: 日志描述文本。

    Returns:
        命令是否执行成功。
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=False,
            timeout=120,
        )
    except Exception as exc:
        logger.warning(f"⚠️ {desc} 异常: {exc}")
        return False

    stdout_text = decode_process_output(result.stdout).strip()
    stderr_text = decode_process_output(result.stderr).strip()

    if result.returncode == 0:
        logger.info(f"✅ {desc}")
        if stdout_text:
            logger.info(stdout_text)
        return True

    logger.warning(f"⚠️ {desc} 失败，exit={result.returncode}")
    if stdout_text:
        logger.warning(stdout_text)
    if stderr_text:
        logger.warning(stderr_text)
    return False


def _run_list_cmd(
    cmd: Sequence[str],
    logger: logging.Logger,
    desc: str,
    *,
    timeout: int,
    allow_failure: bool = False,
) -> bool:
    """执行 list 形式命令并记录结果。

    Args:
        cmd: 命令参数列表。
        logger: 日志对象。
        desc: 日志描述文本。
        timeout: 命令超时时间（秒）。
        allow_failure: 是否允许失败并降级为提示日志。

    Returns:
        命令是否执行成功。
    """
    try:
        result = subprocess.run(
            list(cmd),
            capture_output=True,
            text=False,
            timeout=timeout,
        )
    except Exception as exc:
        if allow_failure:
            logger.info(f"ℹ️ {desc} 异常（忽略）: {exc}")
            return False
        logger.warning(f"⚠️ {desc} 异常: {exc}")
        return False

    stdout_text = decode_process_output(result.stdout).strip()
    stderr_text = decode_process_output(result.stderr).strip()

    if result.returncode == 0:
        logger.info(f"✅ {desc}")
        if stdout_text:
            logger.info(stdout_text)
        return True

    if allow_failure:
        logger.info(f"ℹ️ {desc} 失败但忽略，exit={result.returncode}")
        if stdout_text:
            logger.info(stdout_text)
        if stderr_text:
            logger.info(stderr_text)
        return False

    logger.warning(f"⚠️ {desc} 失败，exit={result.returncode}")
    if stdout_text:
        logger.warning(stdout_text)
    if stderr_text:
        logger.warning(stderr_text)
    return False


def _resolve_adb_path() -> str:
    """解析系统 ADB 可执行文件路径。

    Returns:
        ADB 可执行文件路径或命令名。
    """
    adb_name = "adb.exe" if os.name == "nt" else "adb"
    return shutil.which(adb_name) or "adb"


def _has_any_running_process(process_names: Sequence[str]) -> bool:
    """判断目标进程名中是否有任意一个正在运行。

    Args:
        process_names: 进程名列表。

    Returns:
        只要匹配到任意进程即返回 ``True``。
    """
    if not process_names:
        return False

    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            return False

        if result.returncode != 0:
            return False

        targets = {name.lower() for name in process_names}
        for line in result.stdout.splitlines():
            cols = line.split(",", 1)
            if not cols:
                continue
            image_name = cols[0].strip().strip('"').lower()
            if image_name in targets:
                return True
        return False

    for name in process_names:
        try:
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            continue
        if result.returncode == 0 and result.stdout.strip():
            return True
    return False


def _try_parse_json(raw_text: str) -> Optional[Any]:
    """尝试解析完整 JSON。

    Args:
        raw_text: JSON 原始文本。

    Returns:
        解析后的对象；失败返回 ``None``。
    """
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _try_parse_embedded_json(raw_text: str) -> Optional[Any]:
    """尝试从文本中提取嵌入 JSON。

    Args:
        raw_text: 可能包含 JSON 的文本。

    Returns:
        解析后的对象；失败返回 ``None``。
    """
    candidates: list[str] = []
    start_list = raw_text.find("[")
    end_list = raw_text.rfind("]")
    if 0 <= start_list < end_list:
        candidates.append(raw_text[start_list : end_list + 1])

    start_dict = raw_text.find("{")
    end_dict = raw_text.rfind("}")
    if 0 <= start_dict < end_dict:
        candidates.append(raw_text[start_dict : end_dict + 1])

    for candidate in candidates:
        parsed = _try_parse_json(candidate)
        if parsed is not None:
            return parsed
    return None


def _normalize_mumu_payload(payload: Any) -> list[dict[str, Any]]:
    """规范化 MuMu 输出为实例字典列表。

    Args:
        payload: 原始解析对象。

    Returns:
        统一后的实例字典列表。
    """
    if payload is None:
        return []

    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        if "index" in payload:
            return [dict(payload)]

        for value in payload.values():
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return [dict(item) for item in value]

    return []
