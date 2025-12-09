"""
批量为所有使用 `@timeout_decorator` 的函数添加 `exception_message` 参数。

遍历仓库内的 Python 文件，定位 `@timeout_decorator(...)` 装饰器，
如果其参数中缺少 `exception_message=...`，则自动补充为：
    exception_message="[TIMEOUT]{func_name} 超时"

兼容以下场景：
- 顶层函数、类方法、以及测试文件中的局部函数
- 多装饰器的函数（例如同时存在 `@timer_decorator`）
"""

import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


DECORATOR_PATTERN = re.compile(r"^\s*@timeout_decorator\(([^)]*)\)\s*$")
DEF_PATTERN = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def process_file(path: Path) -> int:
    """处理单个 Python 文件，返回修改次数。

    Args:
        path: 待处理的文件路径

    Returns:
        修改的装饰器数量
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return 0

    lines = content.splitlines()
    changed = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        m = DECORATOR_PATTERN.match(line)
        if not m:
            i += 1
            continue

        args_str = m.group(1)
        if "exception_message" in args_str:
            i += 1
            continue

        # 向前查找后续的 def 行以获取函数名
        func_name = None
        j = i + 1
        while j < len(lines):
            defm = DEF_PATTERN.match(lines[j])
            if defm:
                func_name = defm.group(1)
                break
            # 如果遇到下一段装饰器或空行也继续向下找，直到遇到 def
            j += 1

        if not func_name:
            i += 1
            continue

        # 构造新的装饰器行，追加 exception_message 参数
        new_args = args_str.strip()
        if new_args:
            new_args += ", exception_message=\"[TIMEOUT]{} 超时\"".format(func_name)
        else:
            new_args = "exception_message=\"[TIMEOUT]{} 超时\"".format(func_name)

        lines[i] = re.sub(r"\(([^)]*)\)", f"({new_args})", line)
        changed += 1
        i = j  # 跳到 def 附近减少无谓匹配

    if changed:
        new_content = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
        path.write_text(new_content, encoding="utf-8")

    return changed


def should_process(path: Path) -> bool:
    """判断文件是否需要处理。"""
    if path.suffix != ".py":
        return False
    # 排除虚拟环境、隐藏目录等
    parts = set(path.parts)
    excluded = {".venv", "venv", "__pycache__", ".git"}
    return not (parts & excluded)


def main():
    """遍历项目并更新所有缺少 exception_message 的 timeout 装饰器。"""
    total_changed = 0
    processed_files = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 跳过排除目录
        if any(ex in root.split(os.sep) for ex in (".venv", "venv", "__pycache__", ".git")):
            continue
        for fname in files:
            path = Path(root) / fname
            if not should_process(path):
                continue
            processed_files += 1
            total_changed += process_file(path)

    print(f"处理文件: {processed_files}, 修改装饰器: {total_changed}")


if __name__ == "__main__":
    main()

