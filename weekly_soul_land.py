# -*- encoding=utf8 -*-
"""每周挑战「聚魂之地」自动闯关脚本。

背景
----
主界面左上角「领取任务>>」打开「任务清单」，面板里第一条就是每周重置的秘境
挑战 ``【秘境】聚魂之地-史诗N``（金橙色边框，其余条目是紫/蓝框）。接取后
左侧任务追踪栏出现该条目，之后每次开打都走同一条链路：

    点追踪条目 → 任务详情弹窗「前往」→ 副本详情页「前往」→ 进入战斗（挂机自动打）

**打不过的判据**（大王定义）：战斗结束回到野外后，任务追踪条目右侧的感叹号
**仍然是灰的**。金黄 = 可交付 = 这一层过了；灰 = 没打完 = 打不过，本轮结束。
识别复用 ``quest_claimer.py`` 的颜色掩膜（R>200 & G>170 & B<110、
面积 1600~3200 px），不看 OCR 文本。

主循环::

    接取「聚魂之地」→ 前往 → 等回到野外
        ├─ 感叹号变金黄 → 交付 → 接下一层 → 继续
        └─ 感叹号仍是灰 → 打不过 → 结束

硬超时默认 3600 秒（``--max-seconds``），到点无条件收工。

模拟器不在线时会自动拉起：按 ``emulators.json`` 里该会话的
``emulator_start_cmd``（``pwsh -File c:\\tools\\scripts\\start_bluestacks.ps1 -Id 1``，
幂等，已在跑就跳过）启动，仍不上线再退化为 ``emulator_control.restart_emulator``
完整重启 —— 与每天 06:05 的日常流水线走同一条已验证链路。
**结束时只关本次自己拉起的实例**（跑之前就在线的不动），``--keep-emulator`` 可保留。

用法::

    python weekly_soul_land.py                     # 完整跑一轮
    python weekly_soul_land.py --max-seconds 600   # 只跑 10 分钟
    python weekly_soul_land.py --dry-run           # 只探测界面，不进战斗
    python weekly_soul_land.py --skip-start        # 游戏已在主世界时不重启
    python weekly_soul_land.py --keep-game         # 结束后不关游戏
    python weekly_soul_land.py --keep-emulator     # 结束后不关模拟器
    python weekly_soul_land.py --no-start-emulator # 模拟器离线时不要自动拉起
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auto_dungeon_notification import send_notification  # noqa: E402
from logger_config import (  # noqa: E402
    attach_file_handler_to_loggers,
    setup_logger,
    update_log_context,
)
from project_paths import resolve_project_path  # noqa: E402

LOGGER_NAME = "weekly_soul_land"

DEVICE_DEFAULT = "192.168.1.150:5555"
PACKAGE = "com.ms.ysjyzr"
OCR_URL = os.getenv("OCR_SERVER_URL", "http://192.168.1.150:8311/ocr")
QUEST_KEYWORD = "聚魂之地"

# —— 模拟器自动拉起（复用 emulators.json 的会话命令）——
EMULATORS_CONFIG = PROJECT_ROOT / "emulators.json"
EMULATOR_BOOT_TIMEOUT = 180  # 启动命令执行后等设备上线的秒数

# —— 坐标（基准 720x1280 / 320dpi）——
ENTRY_QUEST_LIST = (50, 99)  # 主界面「领取任务>>」
TRACK_CLICK_X = 150  # 任务追踪条目的点击 x（y 由 OCR 定位）
DIALOG_ACTION = (359, 865)  # 任务详情弹窗底部按钮（「接受任务」/「前往」）
DUNGEON_GO = (359, 921)  # 副本详情页「前往」
NAV_BATTLE = (362, 1245)  # 底部导航「战斗」（也用来关面板）
CHAR_ENTER = (359, 571)  # 角色选择页「进入游戏」

# —— 识别区域 ——
TRACK_BOX = (0, 60, 300, 260)  # 左侧任务追踪栏
TRACK_MARKERS = ("聚魂", "魂之地", "通关", "史诗")  # 任务条目被 OCR 拆行时的定位词
LIST_BOX = (150, 300, 540, 950)  # 任务清单条目区（排除标题栏）
GIFT_BOX = (600, 290, 720, 380)  # 主世界专属：「礼包」按钮
TOP_BOX = (0, 0, 720, 84)  # 顶部标题区（副本名 / 波次计数）

# —— 金黄感叹号的判据（与 quest_claimer.py 保持一致）——
YELLOW_R, YELLOW_G, YELLOW_B = 200, 170, 110
BADGE_MIN_AREA, BADGE_MAX_AREA = 1600, 3200

# 关面板 / 结算弹窗的候选按钮文字
DISMISS_KEYS = ("确定", "继续", "挑战完成", "领取奖励", "确定领取")

logger = setup_logger(name=LOGGER_NAME, level="INFO")


def resolve_adb_path() -> str:
    """解析 adb 可执行文件路径。

    与 ``emulator_manager._resolve_adb_path`` 保持一致的策略：优先系统 PATH，
    找不到就回落到字面量 ``adb``（计划任务环境的 PATH 与交互式 shell 不同，
    写死绝对路径反而更脆）。

    Returns:
        str: adb 可执行文件路径。
    """
    name = "adb.exe" if os.name == "nt" else "adb"
    return shutil.which(name) or "adb"


ADB_BIN = resolve_adb_path()


def load_emulator_session_cmds(device: str) -> Dict[str, Optional[str]]:
    """从 ``emulators.json`` 读取指定设备所属会话的启停命令。

    Args:
        device: 模拟器地址，如 ``192.168.1.150:5555``。

    Returns:
        Dict[str, Optional[str]]: ``{"start_cmd": ..., "shutdown_cmd": ...}``，
        缺项或读取失败时对应值为 ``None``。
    """
    empty: Dict[str, Optional[str]] = {"start_cmd": None, "shutdown_cmd": None}
    try:
        with open(EMULATORS_CONFIG, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.warning(f"⚠️ 未找到 {EMULATORS_CONFIG.name}，无法自动启动模拟器")
        return empty
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"⚠️ 读取 {EMULATORS_CONFIG.name} 失败: {type(exc).__name__}: {exc}")
        return empty

    sessions = data.get("sessions") if isinstance(data, dict) else data
    if not isinstance(sessions, list):
        logger.warning(f"⚠️ {EMULATORS_CONFIG.name} 里没有 sessions 列表")
        return empty

    for sess in sessions:
        if not isinstance(sess, dict) or sess.get("emulator") != device:
            continue
        return {
            "start_cmd": str(sess.get("emulator_start_cmd", "")).strip() or None,
            "shutdown_cmd": str(sess.get("emulator_shutdown_cmd", "")).strip() or None,
        }

    logger.warning(f"⚠️ {EMULATORS_CONFIG.name} 里没有设备 {device} 对应的会话")
    return empty


# --------------------------------------------------------------------------- #
# 基础 IO：adb / 截图 / OCR
# --------------------------------------------------------------------------- #
def adb(*args: str, timeout: int = 30) -> str:
    """执行 adb 子命令。

    Args:
        *args: 传给 adb 的参数（不含设备串）。
        timeout: 秒级超时。

    Returns:
        str: 标准输出（解码失败时用替换字符兜底）。
    """
    result = subprocess.run(
        [ADB_BIN, "-s", DEVICE_DEFAULT, *args],
        capture_output=True,
        timeout=timeout,
    )
    return result.stdout.decode("utf-8", errors="replace")


def tap(x: int, y: int, wait: float = 1.2) -> None:
    """点击屏幕坐标并等待界面稳定。

    Args:
        x: 横坐标。
        y: 纵坐标。
        wait: 点击后等待秒数。
    """
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(wait)


def screenshot(name: str, image_dir: Path) -> Path:
    """截图并落盘。

    Args:
        name: 文件名（不含扩展名）。
        image_dir: 存放目录。

    Returns:
        Path: 截图路径。
    """
    image_dir.mkdir(parents=True, exist_ok=True)
    path = image_dir / f"{name}.png"
    data = b""
    for _ in range(3):
        data = subprocess.run(
            [ADB_BIN, "-s", DEVICE_DEFAULT, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=60,
        ).stdout
        if len(data) > 1000:
            break
        time.sleep(1.5)
    path.write_bytes(data)
    return path


def ocr_items(path: Path) -> List[Dict]:
    """对截图调用 OCR 服务，返回文本 + 坐标列表。

    Args:
        path: 截图路径。

    Returns:
        List[Dict]: 每项含 ``text`` / ``score`` / ``center`` / ``box``；
            OCR 失败时返回空列表。
    """
    payload = {
        "file": base64.b64encode(path.read_bytes()).decode("utf-8"),
        "fileType": 1,
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
    }
    data = None
    for attempt in range(2):
        try:
            resp = requests.post(OCR_URL, json=payload, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:  # noqa: BLE001 - 网络异常要重试一次再放弃
            if attempt == 1:
                logger.warning(f"⚠️ OCR 请求失败: {type(exc).__name__}: {exc}")
                return []
            time.sleep(2)
    if not data:
        return []

    results = data.get("result", {}).get("ocrResults", [])
    if not results:
        return []
    pruned = results[0].get("prunedResult", {})
    items: List[Dict] = []
    for text, score, poly in zip(
        pruned.get("rec_texts", []),
        pruned.get("rec_scores", []),
        pruned.get("dt_polys", []),
    ):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        items.append(
            {
                "text": text,
                "score": round(float(score), 3),
                "center": (int(sum(xs) / len(xs)), int(sum(ys) / len(ys))),
                "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
            }
        )
    return items


class Frame:
    """一帧截图 + 其 OCR 结果，避免同一帧反复请求 OCR。"""

    def __init__(self, image_dir: Path) -> None:
        """初始化空帧。

        Args:
            image_dir: 截图存放目录。
        """
        self.image_dir = image_dir
        self.path: Optional[Path] = None
        self.items: List[Dict] = []

    def refresh(self, name: str = "frame") -> "Frame":
        """重新截图并 OCR。

        Args:
            name: 截图名。

        Returns:
            Frame: 自身，便于链式调用。
        """
        self.path = screenshot(name, self.image_dir)
        self.items = ocr_items(self.path)
        return self

    def find(
        self,
        keyword: str,
        box: Optional[Sequence[int]] = None,
        min_score: float = 0.6,
    ) -> Optional[Dict]:
        """在（可选的）区域内按子串查找第一条命中文本。

        Args:
            keyword: 关键词（子串匹配）。
            box: ``(x1, y1, x2, y2)`` 限定搜索区域；``None`` 表示整屏。
            min_score: 置信度下限。

        Returns:
            Optional[Dict]: 命中的 OCR 项；未命中返回 ``None``。
        """
        for item in self.items:
            if item["score"] < min_score or keyword not in item["text"]:
                continue
            if box is not None:
                x1, y1, x2, y2 = box
                cx, cy = item["center"]
                if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                    continue
            return item
        return None

    def find_all(self, keyword: str, box: Optional[Sequence[int]] = None) -> List[Dict]:
        """按子串查找区域内全部命中项。

        Args:
            keyword: 关键词（子串匹配）。
            box: 限定区域。

        Returns:
            List[Dict]: 命中列表。
        """
        hits = []
        for item in self.items:
            if keyword not in item["text"]:
                continue
            if box is not None:
                x1, y1, x2, y2 = box
                cx, cy = item["center"]
                if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                    continue
            hits.append(item)
        return hits

    def find_any(self, keywords: Sequence[str], box: Optional[Sequence[int]] = None) -> List[Dict]:
        """区域内命中**任一**关键词的项（用于定位被 OCR 拆行的条目）。

        Args:
            keywords: 关键词集合。
            box: 限定区域。

        Returns:
            List[Dict]: 命中列表。
        """
        hits = []
        for item in self.items:
            if not any(k in item["text"] for k in keywords):
                continue
            if box is not None:
                x1, y1, x2, y2 = box
                cx, cy = item["center"]
                if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                    continue
            hits.append(item)
        return hits

    def region_text(self, box: Optional[Sequence[int]] = None) -> str:
        """把区域内（或整屏）的 OCR 文本按阅读顺序拼成一个串。

        任务名经常被 OCR 拆成多行 —— 实测「通关史诗7-聚魂之地」会被切成
        ``通关史诗7-聚`` + ``魂之地``。逐条做子串匹配永远匹配不到完整任务名，
        拼起来再匹配才稳。

        Args:
            box: ``(x1, y1, x2, y2)`` 限定区域；``None`` 表示整屏。

        Returns:
            str: 拼接后的文本。
        """
        parts: List[str] = []
        for item in sorted(self.items, key=lambda d: (d["box"][1], d["box"][0])):
            if box is not None:
                x1, y1, x2, y2 = box
                cx, cy = item["center"]
                if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                    continue
            parts.append(item["text"])
        return "".join(parts)

    def has(self, keyword: str, box: Optional[Sequence[int]] = None) -> bool:
        """区域内（文本拼接后）是否出现关键词。

        Args:
            keyword: 关键词（子串匹配）。
            box: 限定区域。

        Returns:
            bool: 是否命中。
        """
        return keyword in self.region_text(box)


# --------------------------------------------------------------------------- #
# 金黄感叹号（颜色掩膜）
# --------------------------------------------------------------------------- #
def find_yellow_badges(image_path: Path, box: Sequence[int] = TRACK_BOX) -> List[Tuple[int, int]]:
    """定位区域内所有金黄色的「!」按钮。

    判据与 ``quest_claimer.py`` 一致：``R>200 & G>170 & B<110``，
    连通域面积 1600~3200 px、长宽比接近 1。

    Args:
        image_path: 720x1280 截图路径。
        box: ``(x1, y1, x2, y2)`` 搜索区域。

    Returns:
        List[Tuple[int, int]]: 按 y 排序的按钮中心坐标。
    """
    if image_path is None or not image_path.exists():
        return []
    arr = np.asarray(Image.open(image_path).convert("RGB")).astype(np.int16)
    x1, y1, x2, y2 = box
    region = arr[y1:y2, x1:x2]
    mask = (
        (region[:, :, 0] > YELLOW_R) & (region[:, :, 1] > YELLOW_G) & (region[:, :, 2] < YELLOW_B)
    )
    if not mask.any():
        return []

    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    current = 0
    stack: List[Tuple[int, int]] = []
    for sy in range(height):
        for sx in range(width):
            if not mask[sy, sx] or labels[sy, sx]:
                continue
            current += 1
            stack.append((sy, sx))
            labels[sy, sx] = current
            while stack:
                cy, cx = stack.pop()
                for ny in (cy - 1, cy, cy + 1):
                    for nx in (cx - 1, cx, cx + 1):
                        if 0 <= ny < height and 0 <= nx < width:
                            if mask[ny, nx] and not labels[ny, nx]:
                                labels[ny, nx] = current
                                stack.append((ny, nx))

    badges: List[Tuple[int, int]] = []
    for label in range(1, current + 1):
        ys, xs = np.nonzero(labels == label)
        area = len(ys)
        if not (BADGE_MIN_AREA <= area <= BADGE_MAX_AREA):
            continue
        box_w = xs.max() - xs.min() + 1
        box_h = ys.max() - ys.min() + 1
        if box_w < 35 or box_h < 35:
            continue
        if not (0.7 <= box_w / box_h <= 1.4):
            continue
        badges.append((int(xs.mean()) + x1, int(ys.mean()) + y1))
    return sorted(badges, key=lambda p: p[1])


# --------------------------------------------------------------------------- #
# 执行器
# --------------------------------------------------------------------------- #
class SoulLandRunner:
    """「聚魂之地」每周挑战的执行器。"""

    def __init__(self, args: argparse.Namespace) -> None:
        """初始化执行器。

        Args:
            args: 命令行参数。
        """
        self.device = args.device
        self.char_name = args.char
        self.config_name = args.config
        self.max_seconds = args.max_seconds
        self.dry_run = args.dry_run
        self.skip_start = args.skip_start
        self.keep_game = args.keep_game
        self.start_emulator = args.start_emulator
        self.keep_emulator = args.keep_emulator
        self.emulator_launched = False  # 本次运行是否由本脚本拉起了模拟器
        self.image_dir = (
            Path(args.image_dir)
            if args.image_dir
            else resolve_project_path(
                "log", "weekly_soul_land", datetime.now().strftime("%Y-%m-%d")
            )
        )
        self.frame = Frame(self.image_dir)
        self.cleared = 0
        self.attempts = 0
        self.deadline = 0.0
        self.stop_reason = ""

    # ---------------------------- 流程 ---------------------------- #
    def run(self) -> int:
        """执行完整的一轮每周挑战。

        Returns:
            int: 进程退出码，0 表示流程正常跑完（含「打不过」）。
        """
        global DEVICE_DEFAULT
        DEVICE_DEFAULT = self.device
        update_log_context({"config": self.config_name, "emulator": self.device})

        self.deadline = time.monotonic() + self.max_seconds
        logger.info("=" * 60)
        logger.info("🏰 每周挑战「聚魂之地」自动闯关")
        logger.info(f"   设备={self.device}  职业={self.char_name}  硬超时={self.max_seconds}s")
        logger.info(f"   截图目录={self.image_dir}")
        logger.info("=" * 60)

        try:
            if not self.ensure_emulator_online():
                self.stop_reason = f"模拟器 {self.device} 离线"
                return self.finish(1)

            if not self.ensure_in_game():
                self.stop_reason = "未能进入游戏主世界"
                return self.finish(1)

            if self.dry_run:
                self.probe()
                self.stop_reason = "dry-run 探测完成"
                return self.finish(0)

            if not self.ensure_quest_accepted():
                self.stop_reason = "任务清单里没有可接的「聚魂之地」"
                return self.finish(1)

            self.main_loop()
        except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证能发通知
            logger.error(f"❌ 运行异常: {type(exc).__name__}: {exc}", exc_info=True)
            self.stop_reason = f"运行异常: {type(exc).__name__}"
            return self.finish(1)

        return self.finish(0)

    def main_loop(self) -> None:
        """主循环：打一层 → 看感叹号 → 决定继续还是收工。"""
        while time.monotonic() < self.deadline:
            # 如果上一轮打完后任务已完成但没交付，先交付再接下一层
            if self.quest_is_claimable():
                if not self.claim_and_take_next():
                    return
                continue

            self.attempts += 1
            logger.info(f"\n⚔️ 第 {self.attempts} 次出击（本轮已通关 {self.cleared} 层）")
            if not self.goto_fight():
                self.stop_reason = "无法进入战斗（界面异常）"
                return

            if not self.wait_fight_over():
                self.stop_reason = "等待战斗结束超时"
                return

            if self.quest_is_claimable():
                logger.info("🎉 这一层过了（感叹号已变金黄）")
                if not self.claim_and_take_next():
                    return
            else:
                self.stop_reason = "打不过（战斗结束后感叹号仍是灰色）"
                logger.info("🛑 打不过，本轮结束")
                return

        self.stop_reason = f"达到硬超时 {self.max_seconds}s"

    def finish(self, code: int) -> int:
        """收尾：汇总日志、发通知、可选关游戏。

        Args:
            code: 退出码。

        Returns:
            int: 退出码（原样返回）。
        """
        elapsed = int(time.monotonic() - (self.deadline - self.max_seconds))
        summary = (
            f"时间: {elapsed // 60} 分 {elapsed % 60} 秒\n"
            f"出击次数: {self.attempts}\n"
            f"通关层数: {self.cleared}\n"
            f"结束原因: {self.stop_reason or '正常结束'}"
        )
        logger.info("=" * 60)
        logger.info("📊 本轮小结\n" + summary)
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("dry-run 结束：不发通知、不动游戏")
            return code

        title = "聚魂之地" + ("✅" if self.cleared else "⚠️")
        try:
            ok = send_notification(title, summary, provider="bark")
            logger.info(f"📱 通知发送{'成功' if ok else '失败'}: {title}")
        except Exception as exc:  # noqa: BLE001 - 通知失败不能影响退出
            logger.error(f"❌ 发送通知异常: {type(exc).__name__}: {exc}")

        if not self.keep_game:
            logger.info("关闭游戏…")
            adb("shell", "am", "force-stop", PACKAGE)
        if self.emulator_launched and not self.keep_emulator:
            self._shutdown_emulator()
        return code

    def _shutdown_emulator(self) -> None:
        """关闭本次由脚本自己拉起的模拟器。

        计划任务环境下不像 Agent 沙箱会回收派生进程，不主动关就会留下一个常驻
        BlueStacks。**只关自己拉起的**：跑之前就在线的实例不动。

        Returns:
            None
        """
        cmds = load_emulator_session_cmds(self.device)
        shutdown_cmd = cmds["shutdown_cmd"]
        if not shutdown_cmd:
            logger.warning("⚠️ emulators.json 里没有该会话的 emulator_shutdown_cmd，模拟器保持运行")
            return

        # 会话命令里写的是裸 `python`，计划任务环境的 PATH 未必有 —— 换成当前解释器
        if not shutil.which("python"):
            shutdown_cmd = re.sub(r"^\s*python\b", f'"{sys.executable}"', shutdown_cmd)
        logger.info(f"🧹 关闭本次拉起的模拟器: {shutdown_cmd}")
        try:
            subprocess.run(shutdown_cmd, shell=True, capture_output=True, timeout=180)
        except Exception as exc:  # noqa: BLE001 - 关不掉不该影响退出码
            logger.error(f"❌ 关闭模拟器异常: {type(exc).__name__}: {exc}")
        if self._device_online():
            logger.warning("⚠️ 关闭命令已执行，但设备仍在 online 状态")
        else:
            logger.info("✅ 模拟器已关闭")

    # ---------------------------- 步骤 ---------------------------- #
    def ensure_emulator_online(self, timeout: int = 120) -> bool:
        """确保模拟器在线（``adb devices`` 里是 ``device`` 状态）。

        三级升级，与日常流水线同一套机制：

        1. 反复 ``adb connect``，最长 ``timeout`` 秒；
        2. 仍离线 → 执行 ``emulators.json`` 里该会话的 ``emulator_start_cmd``
           （``start_bluestacks.ps1`` 是幂等的，不会打扰已在跑的实例）；
        3. 还离线 → 用 ``emulator_control.restart_emulator`` 完整重启。

        启动动作由本进程承载，拉起的实例会在 ``finish()`` 里关掉（见
        ``_shutdown_emulator``）。``--no-start-emulator`` 可只保留第 1 级。

        Args:
            timeout: ``adb connect`` 重试总时长（秒）。

        Returns:
            bool: 是否在线。
        """
        if self._wait_online(timeout):
            return True
        if not self.start_emulator:
            logger.error("❌ 模拟器离线，且已禁用自动启动（--no-start-emulator）")
            return False

        logger.warning(f"⚠️ {self.device} 离线，尝试按会话命令启动模拟器…")
        self._run_emulator_start_cmd()
        if self._wait_online(EMULATOR_BOOT_TIMEOUT):
            self.emulator_launched = True
            return True

        logger.warning("⚠️ 幂等启动后仍离线，退化为完整重启…")
        self._restart_emulator()
        if self._wait_online(EMULATOR_BOOT_TIMEOUT):
            self.emulator_launched = True
            return True

        logger.error(f"❌ 自动拉起后 {self.device} 仍离线")
        return False

    def _wait_online(self, timeout: int) -> bool:
        """等待设备上线，期间反复 ``adb connect``。

        Args:
            timeout: 等待总时长（秒）。

        Returns:
            bool: 是否在线。
        """
        started = time.monotonic()
        while True:
            if self._device_online():
                logger.info(f"✅ 模拟器在线: {self.device}")
                return True
            if time.monotonic() - started > timeout:
                return False
            logger.warning(f"⚠️ 模拟器 {self.device} 未就绪，尝试 adb connect…")
            adb("connect", self.device)
            time.sleep(8)

    def _run_emulator_start_cmd(self) -> None:
        """执行 ``emulators.json`` 里该会话的模拟器启动命令。

        与 ``emulator_manager._run_start_cmd`` 同构（shell 执行），额外收集
        输出用于排错；失败不抛异常 —— 后面还有完整重启兜底。

        Returns:
            None
        """
        start_cmd = load_emulator_session_cmds(self.device)["start_cmd"]
        if not start_cmd:
            logger.warning("⚠️ emulators.json 里没有该会话的 emulator_start_cmd")
            return
        logger.info(f"🚀 执行启动命令: {start_cmd}")
        try:
            subprocess.run(
                start_cmd,
                shell=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ 启动命令 120 秒未返回，继续等设备上线")
        except Exception as exc:  # noqa: BLE001 - 启动失败后面有重启兜底
            logger.error(f"❌ 执行启动命令失败: {type(exc).__name__}: {exc}")

    def _restart_emulator(self) -> None:
        """用 ``emulator_control.restart_emulator`` 完整重启模拟器。

        Returns:
            None
        """
        cmds = load_emulator_session_cmds(self.device)
        try:
            from emulator_control import EmulatorRestartConfig, restart_emulator
        except Exception as exc:  # noqa: BLE001 - 导入失败不该中断主流程
            logger.error(f"❌ 导入 emulator_control 失败: {type(exc).__name__}: {exc}")
            return
        try:
            restart_emulator(
                EmulatorRestartConfig(
                    emulator=self.device,
                    shutdown_cmd=cmds["shutdown_cmd"],
                    start_cmd=cmds["start_cmd"],
                ),
                logger,
            )
        except Exception as exc:  # noqa: BLE001 - 同上
            logger.error(f"❌ 重启模拟器异常: {type(exc).__name__}: {exc}")

    def _device_online(self) -> bool:
        """判断目标设备在 ``adb devices`` 里是否为可用状态。

        Returns:
            bool: 是否在线。
        """
        try:
            out = adb("devices")
        except Exception as exc:  # noqa: BLE001 - adb 自身异常按离线处理
            logger.warning(f"⚠️ adb devices 失败: {type(exc).__name__}: {exc}")
            return False
        for line in out.splitlines():
            if line.startswith(self.device) and "\tdevice" in line:
                return True
        return False

    def ensure_in_game(self) -> bool:
        """确保游戏处于野外主世界。

        Returns:
            bool: 是否就绪。
        """
        if self.skip_start:
            logger.info("跳过重启，直接确认界面…")
        else:
            logger.info("重启游戏…")
            adb("shell", "am", "force-stop", PACKAGE)
            time.sleep(2)
            adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")

        # 等角色选择页或主世界出现
        started = time.monotonic()
        picked = False
        while time.monotonic() - started < 180:
            frame = self.frame.refresh("boot")
            if self.is_field(frame):
                logger.info("已在野外主世界")
                return True
            if not picked and frame.has("进入游戏"):
                logger.info("到达角色选择页，选择职业并进入游戏")
                warrior = frame.find(self.char_name)
                if warrior:
                    tap(*warrior["center"], wait=1.5)
                tap(*CHAR_ENTER, wait=3)
                picked = True
                continue
            time.sleep(3)

        logger.error("❌ 180 秒内未进入主世界")
        return False

    def is_field(self, frame: Frame) -> bool:
        """判断当前是否为野外主世界。

        Args:
            frame: 当前帧。

        Returns:
            bool: 主世界特征（右侧有「礼包」按钮）且顶部没有副本标题。
        """
        if not frame.has("礼包", GIFT_BOX):
            return False
        return not frame.has(QUEST_KEYWORD, TOP_BOX)

    def has_quest_in_track(self, frame: Optional[Frame] = None) -> bool:
        """任务追踪栏里是否已有「聚魂之地」。

        Args:
            frame: 可复用的帧；``None`` 时重新截图。

        Returns:
            bool: 是否存在。
        """
        frame = frame or self.frame.refresh("track")
        return frame.has(QUEST_KEYWORD, TRACK_BOX)

    def quest_is_claimable(self) -> bool:
        """任务追踪条目的感叹号是否已变金黄（= 这一层过了）。

        Returns:
            bool: 是否可交付。
        """
        frame = self.frame.refresh("claim_check")
        badges = find_yellow_badges(frame.path) if frame.path else []
        if badges:
            logger.info(f"🔔 任务追踪栏发现金黄感叹号: {badges}")
        return bool(badges)

    def track_entry_point(self, frame: Frame) -> Tuple[int, int]:
        """算出任务追踪条目的点击点。

        任务名会被 OCR 拆行，所以用「通关/聚魂/史诗」这类行标记词定位，
        再取这些片段的外接 y 中心。

        Args:
            frame: 当前帧（需已含任务追踪栏文本）。

        Returns:
            Tuple[int, int]: 点击坐标；找不到时回落到固定坐标。
        """
        hits = frame.find_any(TRACK_MARKERS, TRACK_BOX)
        if not hits:
            return (TRACK_CLICK_X, 111)
        top = min(h["box"][1] for h in hits)
        bottom = max(h["box"][3] for h in hits)
        return (TRACK_CLICK_X, (top + bottom) // 2)

    def ensure_quest_accepted(self) -> bool:
        """确保任务追踪栏里挂着「聚魂之地」。

        Returns:
            bool: 是否接取成功（或本来就有）。
        """
        frame = self.frame.refresh("quest_check")
        if self.has_quest_in_track(frame):
            logger.info("任务追踪栏已有「聚魂之地」，直接开打")
            return True
        return self.accept_from_list()

    def accept_from_list(self) -> bool:
        """打开任务清单，接取第一条含「聚魂之地」的任务。

        Returns:
            bool: 是否接取成功。
        """
        for attempt in range(3):
            self.reset_view()
            logger.info(f"📋 打开任务清单找「{QUEST_KEYWORD}」（第 {attempt + 1} 次）")

            frame = self.frame.refresh("quest_entry")
            entry_point = self.quest_list_entry_point(frame)
            if entry_point is None:
                logger.warning("⚠️ 界面上定位不到「领取任务」入口")
                return False
            tap(*entry_point, wait=3)

            frame = self.frame.refresh("quest_list")
            entry = frame.find(QUEST_KEYWORD, LIST_BOX)
            if not entry:
                logger.warning("⚠️ 任务清单里没找到「聚魂之地」条目")
                continue

            logger.info(f"👆 点击任务条目: {entry['text']!r} @ {entry['center']}")
            tap(*entry["center"], wait=3)
            tap(*DIALOG_ACTION, wait=3)

            frame = self.frame.refresh("quest_accepted")
            if frame.has(QUEST_KEYWORD, TRACK_BOX):
                logger.info("✅ 已接取「聚魂之地」")
                self.reset_view()  # 关掉任务清单面板
                return True
            logger.warning("⚠️ 点了接受任务但追踪栏没出现该任务")

        return False

    def reset_view(self, rounds: int = 2) -> None:
        """把界面拉回野外：点底部「战斗」逐层关掉可能残留的面板。

        Args:
            rounds: 点击次数（面板可能叠了多层）。
        """
        for _ in range(rounds):
            tap(*NAV_BATTLE, wait=1.5)

    def quest_list_entry_point(self, frame: Frame) -> Optional[Tuple[int, int]]:
        """定位「领取任务>>」入口。

        该入口会被左侧任务追踪栏挤得上下浮动（空追踪栏时在 y≈99，
        挂着任务时会掉到 y≈187），所以不能写死坐标。

        Args:
            frame: 当前帧。

        Returns:
            Optional[Tuple[int, int]]: 入口坐标；定位不到时，若追踪栏为空
                则回落到固定坐标，否则返回 ``None``。
        """
        item = frame.find("领取任务", (0, 60, 240, 320))
        if item:
            return item["center"]
        if not frame.has(QUEST_KEYWORD, TRACK_BOX):
            return ENTRY_QUEST_LIST
        return None

    def claim_and_take_next(self) -> bool:
        """交付已完成的任务，并接取下一层。

        Returns:
            bool: ``True`` 表示已接好下一层可以继续；``False`` 表示本轮结束。
        """
        if not self.claim_quest():
            logger.warning("⚠️ 交付任务失败，本轮结束")
            self.stop_reason = "交付任务失败"
            return False
        self.cleared += 1

        logger.info("🔎 回任务清单找下一层「聚魂之地」…")
        if self.accept_from_list():
            return True

        self.stop_reason = "没有下一层「聚魂之地」任务了"
        logger.info("🏁 任务清单里已无「聚魂之地」，全部打完")
        return False

    def claim_quest(self) -> bool:
        """点击金黄感叹号交付任务，并处理随后的弹窗。

        Returns:
            bool: 是否成功交付。
        """
        frame = self.frame.refresh("claim")
        badges = find_yellow_badges(frame.path) if frame.path else []
        if not badges:
            logger.warning("⚠️ 没有找到金黄感叹号，无法交付")
            return False

        x, y = badges[0]
        logger.info(f"👆 点击金黄感叹号 ({x}, {y})")
        tap(x, y, wait=3)

        # 交付后常连弹「完成」→「接受任务」，最多处理 3 层
        for _ in range(3):
            frame = self.frame.refresh("claim_dialog")
            button = self._find_dialog_button(frame)
            if not button:
                break
            text, (bx, by) = button
            logger.info(f"👆 点击「{text}」({bx}, {by})")
            tap(bx, by, wait=3)

        return True

    def _find_dialog_button(self, frame: Frame) -> Optional[Tuple[str, Tuple[int, int]]]:
        """在弹窗里找可点的确认按钮（完全匹配，避免点到描述文字）。

        Args:
            frame: 当前帧。

        Returns:
            Optional[Tuple[str, Tuple[int, int]]]: ``(按钮文字, 坐标)``。
        """
        labels = ("完成", "接受任务") + DISMISS_KEYS
        for item in frame.items:
            text = item["text"].strip()
            if item["score"] > 0.85 and item["center"][1] > 700 and text in labels:
                return text, item["center"]
        return None

    def goto_fight(self) -> bool:
        """走到副本并进入战斗。

        链路：任务追踪条目 → 详情「前往」→ 副本详情「前往」→ 战斗。

        Returns:
            bool: 是否成功进入战斗。
        """
        frame = self.frame.refresh("goto_track")
        if not self.has_quest_in_track(frame):
            logger.warning("⚠️ 追踪栏没有「聚魂之地」，先重新接取")
            if not self.accept_from_list():
                return False
            frame = self.frame.refresh("goto_track_retry")

        point = self.track_entry_point(frame)
        logger.info(f"👆 打开任务详情 {point}")
        tap(*point, wait=3)

        frame = self.frame.refresh("task_detail")
        if not (
            frame.find("前往", (300, 800, 460, 960)) or frame.find("接受任务", (300, 800, 460, 960))
        ):
            logger.warning("⚠️ 任务详情弹窗未出现「前往」按钮，重试一次")
            tap(*point, wait=3)
            frame = self.frame.refresh("task_detail_retry")

        logger.info(f"👆 点任务详情「前往」{DIALOG_ACTION}")
        tap(*DIALOG_ACTION, wait=4)

        frame = self.frame.refresh("dungeon_detail")
        if frame.has("地下城等级") or frame.has("高难度秘境"):
            logger.info(f"👆 副本详情页，点「前往」{DUNGEON_GO}")
            tap(*DUNGEON_GO, wait=8)
        else:
            logger.info("已在战斗或直接进入副本")

        return self.wait_fight_start()

    def wait_fight_start(self, timeout: int = 90) -> bool:
        """等战斗界面出现。

        Args:
            timeout: 最长等待秒数。

        Returns:
            bool: 是否已开打。
        """
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            frame = self.frame.refresh("fight_start")
            if frame.has(QUEST_KEYWORD, TOP_BOX):
                logger.info("⚔️ 已进入战斗")
                return True
            if self.is_field(frame):
                time.sleep(5)
                continue
            time.sleep(3)
        logger.warning("⚠️ 未能确认进入战斗")
        return False

    def wait_fight_over(self, timeout: int = 900) -> bool:
        """等战斗结束、回到野外。

        中途若出现结算弹窗（「确定」/「继续」等），顺手点掉。

        Args:
            timeout: 最长等待秒数。

        Returns:
            bool: 是否已回到野外。
        """
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            if time.monotonic() > self.deadline:
                logger.warning("⏰ 硬超时，停止等待战斗")
                return False
            time.sleep(8)
            frame = self.frame.refresh("fight_wait")
            if self.is_field(frame):
                logger.info("🏕️ 已回到野外")
                return True
            button = self._find_dialog_button(frame)
            if button:
                text, (bx, by) = button
                logger.info(f"👆 战斗结算弹窗，点「{text}」({bx}, {by})")
                tap(bx, by, wait=3)
        logger.warning(f"⚠️ {timeout} 秒内未回到野外")
        return False

    # ---------------------------- 探测 ---------------------------- #
    def probe(self) -> None:
        """dry-run：把关键界面的识别结果打出来，不做任何点击。"""
        frame = self.frame.refresh("probe")
        logger.info("—— dry-run 探测 ——")
        logger.info(f"主世界: {self.is_field(frame)}")
        logger.info(f"追踪栏有「{QUEST_KEYWORD}」: {self.has_quest_in_track(frame)}")
        badges = find_yellow_badges(frame.path) if frame.path else []
        logger.info(f"金黄感叹号: {badges}")
        for item in sorted(frame.items, key=lambda d: (d["box"][1], d["box"][0])):
            logger.info(f"  {item['text']!r:36} score={item['score']:.2f} center={item['center']}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 参数列表；``None`` 时取 ``sys.argv[1:]``。

    Returns:
        argparse.Namespace: 解析结果。
    """
    parser = argparse.ArgumentParser(description="每周挑战「聚魂之地」自动闯关")
    parser.add_argument("--device", default=DEVICE_DEFAULT, help="模拟器地址")
    parser.add_argument("--config", default="warrior", help="日志上下文里的配置名")
    parser.add_argument("--char", default="战士", help="角色选择页要选的职业")
    parser.add_argument(
        "--max-seconds",
        type=int,
        default=3600,
        help="硬超时秒数，默认 3600（1 小时）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只探测界面，不进战斗")
    parser.add_argument("--skip-start", action="store_true", help="不重启游戏，直接在当前界面开始")
    parser.add_argument("--keep-game", action="store_true", help="结束后不关闭游戏")
    parser.add_argument(
        "--no-start-emulator",
        dest="start_emulator",
        action="store_false",
        help="模拟器离线时不自动拉起（默认会按 emulators.json 的会话命令启动）",
    )
    parser.add_argument(
        "--keep-emulator",
        action="store_true",
        help="结束后不关闭模拟器（默认会关掉本次由脚本自己拉起的实例）",
    )
    parser.add_argument(
        "--image-dir", default=None, help="截图目录（默认 log/weekly_soul_land/<日期>）"
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """脚本入口。

    Args:
        argv: 参数列表。

    Returns:
        int: 退出码。
    """
    args = parse_args(argv)
    attach_file_handler_to_loggers(
        filename="weekly_soul_land.log",
        logger_names=(None, LOGGER_NAME),
    )
    runner = SoulLandRunner(args)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
