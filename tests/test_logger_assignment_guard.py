"""测试不得篡改模块级 logger —— 静态与运行时双重守卫。

2026-11-08 体检发现：``tests/test_exchange_page_parsing.py`` 里两处

```python
manager.logger.warning = lambda message, *args: alerts.append(message % args)
```

把 ``DailyCollectManager.logger``（与 ``logging.getLogger("auto_dungeon_daily")``
是**同一个对象**）的 ``warning`` 方法永久替换成普通函数。后果是同一次 pytest
运行里，之后所有 ``auto_dungeon_daily`` 的 WARNING 都不再进入 logging 机制：

- 反序执行（``test_exchange_page_parsing.py`` 先跑）时
  ``test_chest_stock_afk.py::test_zero_growth_after_afk_logs_warning`` **FAILED**
  （实测 1 failed / 43 passed），``caplog.records`` 为空；正序执行则 44 passed
  —— 行不行取决于文件执行顺序，属于最隐蔽的一类 flaky；
- 更危险的是反方向 —— 所有「不该告警」的断言都会变成**假绿**，守门测试失效。

守卫分两层：

1. 静态：tests/ 下禁止 ``.logger.<level> =`` 这种直接赋值（Logger 实例是共享的）。
   判据走 **AST**，不用逐行正则 —— 本模块的说明文字里就写着该写法，正则会把
   文档当成违规（首版即误报于此）。
2. 运行时：真跑一遍那两个用例，确认模块级 logger 的 ``warning`` 仍是
   ``logging.Logger`` 的绑定方法，且真实 WARNING 仍能落进 caplog。
"""

from __future__ import annotations

import ast
import inspect
import logging
from pathlib import Path

import pytest

#: 禁止在测试里直接赋值的 logger 方法名。
FORBIDDEN_LOGGER_ATTRS = ("debug", "info", "warning", "error", "exception", "critical")


def _tests_dir() -> Path:
    """返回 tests 目录的绝对路径。

    Returns:
        ``tests`` 目录路径。
    """
    return Path(__file__).resolve().parent


def _is_logger_expr(node: ast.expr) -> bool:
    """判断表达式是否指向一个 logger 对象。

    Args:
        node: 赋值目标左侧的表达式节点。

    Returns:
        形如 ``xxx.logger`` 或 ``logging.getLogger(...)`` 时为 True。
    """
    if isinstance(node, ast.Attribute) and node.attr == "logger":
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "getLogger":
            return True
        return isinstance(func, ast.Name) and func.id == "getLogger"
    return False


def _scan_logger_assignments(path: Path) -> list[str]:
    """用 AST 找出真正的 logger 方法赋值语句。

    逐行正则会把 docstring / 注释里的示例代码当成违规（本模块自身就写着
    ``manager.logger.warning = ...`` 这类说明文字），因此只看真实赋值节点。

    Args:
        path: 待扫描的 Python 文件路径。

    Returns:
        形如 ``文件:行号: 源码`` 的违规条目列表；文件语法错误时返回空列表。
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    lines = source.splitlines()
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr not in FORBIDDEN_LOGGER_ATTRS:
                continue
            if not _is_logger_expr(target.value):
                continue
            snippet = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
            offenders.append(f"{path.name}:{node.lineno}: {snippet}")
    return offenders


def test_no_test_assigns_logger_method_directly() -> None:
    """tests/ 下任何文件都不得直接给 logger 方法赋值。

    这类赋值改的是 ``logging.Logger`` **共享实例**的属性，不会在测试结束时
    自动恢复，会静默破坏同一次运行里后续所有告警断言。
    """
    offenders: list[str] = []
    for path in sorted(_tests_dir().glob("*.py")):
        if path.resolve() == Path(__file__).resolve():
            continue
        offenders.extend(_scan_logger_assignments(path))

    assert not offenders, (
        "发现直接给 logger 方法赋值（会永久污染模块级 logger），"
        "请改用 monkeypatch.setattr(manager, 'logger', 假 logger)：\n" + "\n".join(offenders)
    )


def test_guard_ignores_docstring_examples(tmp_path: Path) -> None:
    """守卫自身不得把 docstring 里的示例代码误判成违规。"""
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""说明文字，里面提到 manager.logger.warning = lambda: None 这种写法。"""\n'
        "# 注释里提到 logger.info = 某函数\n"
        "VALUE = 1\n",
        encoding="utf-8",
    )

    assert _scan_logger_assignments(sample) == []


def _run_case(func) -> None:
    """调用被测用例，兼容「有无 monkeypatch 形参」两种签名。

    旧版用例不接受夹具参数，若固定传 ``monkeypatch`` 会以 ``TypeError``
    失败 —— 那是机械失败，证明不了「模块 logger 被污染」这一行为缺失。

    Args:
        func: 被测的测试函数。
    """
    positional = [
        param
        for param in inspect.signature(func).parameters.values()
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if not positional:
        func()
        return

    inner = pytest.MonkeyPatch()
    try:
        func(inner)
    finally:
        inner.undo()


def test_parsing_tests_leave_module_logger_intact() -> None:
    """跑过兑换页的两个告警用例后，模块级 logger 必须完好无损。"""
    from tests import test_exchange_page_parsing as parsing_tests

    module_logger = logging.getLogger("auto_dungeon_daily")
    assert inspect.ismethod(module_logger.warning), "前提不成立：模块 logger.warning 本应是绑定方法"

    _run_case(parsing_tests.test_warn_when_row_price_differs_from_observation)
    _run_case(parsing_tests.test_no_warn_when_layout_matches_observation)

    assert getattr(module_logger.warning, "__func__", None) is logging.Logger.warning, (
        "模块级 logger 的 warning 被测试篡改成非绑定方法，"
        f"实际类型={type(module_logger.warning)!r}"
    )


def test_real_warning_still_reaches_caplog_after_parsing_tests(caplog) -> None:
    """跑完兑换页用例后，真实 WARNING 仍必须能落进 caplog（端到端证据）。"""
    from tests import test_exchange_page_parsing as parsing_tests

    _run_case(parsing_tests.test_warn_when_row_price_differs_from_observation)
    _run_case(parsing_tests.test_no_warn_when_layout_matches_observation)

    with caplog.at_level(logging.WARNING, logger="auto_dungeon_daily"):
        logging.getLogger("auto_dungeon_daily").warning("守卫探针：这条必须被抓到")

    assert any(
        "守卫探针" in record.getMessage() for record in caplog.records
    ), f"WARNING 未进入 caplog，实际日志={[r.getMessage() for r in caplog.records]}"
