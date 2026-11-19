"""测试 ``output`` 根目录 OCR 结果 sidecar 的兜底清理。

背景（2026-11-19 体检）：``vibe_ocr.OcrHelper.find_all_matching_texts()`` 每次
调用都把识别结果写成 ``<截图名>_res.json`` 落到 ``output_dir``，在同一次调用内
立刻读回，用完不删。项目侧从不读取这些文件，于是 ``output/`` 根目录以每天
8~10 个的速度永久堆积（11-18 已积 796 个）。编排器每轮启动时调用
``cleanup_ocr_sidecars()`` 兜底清理滞留超 24 小时的旧文件。

本测试锁三条不变量：

1. 只删 ``*_res.json`` 且滞留超时的文件 —— 新文件、非 sidecar 文件一律不动；
2. 不递归 —— ``output/cache`` / ``output/temp`` 里的同名文件必须原封不动
   （``cache_<id>_res.json`` 是缓存数据库同目录的配套文件）；
3. 编排器真的接上了这个函数 —— 否则函数写了没人调，等于没修。
"""

from __future__ import annotations

import ast
import os
import time
from pathlib import Path

from cleanup_cache import cleanup_ocr_sidecars

#: 用来构造「明显超时」的 sidecar，远大于默认的 24 小时。
STALE_AGE_SECONDS = 3 * 24 * 3600

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _make_file(path: Path, stale: bool, content: str = "[]") -> Path:
    """创建一个文件，并按需把 mtime 推到过去。

    Args:
        path: 目标文件路径（父目录必须已存在）。
        stale: 为 ``True`` 时把 mtime 设为 ``STALE_AGE_SECONDS`` 之前。
        content: 写入的内容。

    Returns:
        写入的文件路径。
    """
    path.write_text(content, encoding="utf-8")
    if stale:
        stamp = time.time() - STALE_AGE_SECONDS
        os.utime(path, (stamp, stamp))
    return path


def test_removes_only_stale_sidecars(tmp_path):
    """超时的 sidecar 被删，新 sidecar 与其它文件保留。"""
    stale = _make_file(tmp_path / "old_shot_res.json", stale=True, content="[]")
    fresh = _make_file(tmp_path / "new_shot_res.json", stale=False)
    screenshot = _make_file(tmp_path / "old_shot.png", stale=True, content="png")
    note = _make_file(tmp_path / "readme.txt", stale=True, content="keep")

    removed, failed, freed = cleanup_ocr_sidecars(str(tmp_path), logger=None)

    assert removed == 1
    assert failed == 0
    assert freed == len("[]")
    assert not stale.exists()
    assert fresh.exists()
    assert screenshot.exists()
    assert note.exists()


def test_missing_output_dir_is_noop(tmp_path):
    """目录不存在时返回全零，不抛异常。"""
    missing = tmp_path / "not_created"

    assert cleanup_ocr_sidecars(str(missing), logger=None) == (0, 0, 0)


def test_does_not_recurse_into_subdirs(tmp_path):
    """子目录（cache/temp）里的旧 sidecar 必须保留。"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = _make_file(cache_dir / "cache_1_res.json", stale=True)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    leftover = _make_file(temp_dir / "shot_res.json", stale=True)

    removed, _, _ = cleanup_ocr_sidecars(str(tmp_path), logger=None)

    assert removed == 0
    assert cached.exists()
    assert leftover.exists()


def test_logger_receives_summary(tmp_path):
    """有删除动作时写一条汇总日志（便于在 cron 日志里核对）。"""

    class _Recorder:
        def __init__(self):
            self.messages = []

        def info(self, message):
            self.messages.append(message)

        def warning(self, message):
            self.messages.append(message)

    _make_file(tmp_path / "old_shot_res.json", stale=True)
    recorder = _Recorder()

    cleanup_ocr_sidecars(str(tmp_path), logger=recorder)

    assert len(recorder.messages) == 1
    assert "删除 1 个" in recorder.messages[0]


def test_orchestrator_wires_sidecar_cleanup():
    """静态守卫：编排器必须导入并在启动阶段调用 ``cleanup_ocr_sidecars``。

    只测函数本身不够 —— 函数写得再对，没人调也等于没修。
    """
    source = (PROJECT_ROOT / "cron_run_all_dungeons.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "cleanup_cache"
        for alias in node.names
    }
    assert "cleanup_ocr_sidecars" in imported, "编排器没有导入 cleanup_ocr_sidecars"

    called = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cleanup_ocr_sidecars"
    ]
    assert called, "cleanup_ocr_sidecars 已导入但从未被调用（函数写了没人调 = 没修）"
    assert called[0].args, "调用必须显式传入 output 目录，避免依赖 cwd"
