"""项目路径工具
提供基于 auto_dungeon.py 所在目录的路径解析函数, 确保在任意工作目录运行脚本时都能找到资源文件。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Union

PathLike = Union[str, os.PathLike[str], Path]


@lru_cache(maxsize=1)
def get_auto_dungeon_root() -> Path:
    """返回 auto_dungeon.py 所在的目录路径。"""

    current = Path(__file__).resolve()
    search_dirs: Iterable[Path] = (current.parent,) + tuple(current.parents)
    for directory in search_dirs:
        candidate = directory / "auto_dungeon.py"
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError("未找到 auto_dungeon.py, 无法解析项目根目录")


def ensure_project_path(path: PathLike) -> Path:
    """将相对路径转换为相对于 auto_dungeon.py 的绝对路径。"""

    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return get_auto_dungeon_root() / path_obj


def resolve_project_path(*parts: PathLike) -> Path:
    """以 auto_dungeon.py 所在目录为根, 拼接路径。"""

    if not parts:
        return get_auto_dungeon_root()

    path = Path(parts[0])
    for part in parts[1:]:
        path = path / part

    return ensure_project_path(path)


__all__ = [
    "get_auto_dungeon_root",
    "ensure_project_path",
    "resolve_project_path",
]
