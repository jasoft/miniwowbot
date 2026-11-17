"""守卫：``vibe-ocr`` 必须来自本地源码，且带 TTL + 重试能力。

**为什么要守（2026-11-17 体检）**：本地库 ``E:\\Projects\\pythonlib\\vibe-ocr`` 比 PyPI 上
同名 ``0.1.6`` 轮子多三处能力（缓存 TTL 过期、``find(exact=)``、OCR 请求瞬态 502 重试），
但版本号没跟着 bump。之前靠手工 ``uv pip install -e`` 维持 editable，计划任务的
``uv run`` 一旦自动同步，就会**静默退回轮子**：

- 缓存永不过期 ⇒ 错误识别结果可被永久复用（2026-09「领取邮件」连败 70 次的病根）；
- 没有请求重试 ⇒ 代理一次 502 就退化成「这次没读到」（2026-10-24 丢 1800 秒挂机的病根）。

而且这一切发生时不报错、日志无异常，只能靠测试发现 —— 所以这里锁两件事：
**依赖来源**（pyproject 声明了 path 源）和**库能力**（TTL 常量 + ``cache_ttl_seconds`` 形参）。
"""

from __future__ import annotations

import inspect
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 本机 venv 是 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
#: 本地库里 ``src/`` 布局下 ``vibe_ocr`` 包的父目录（= path 源的解析结果）
EXPECTED_SOURCE_DIR = (ROOT / "../pythonlib/vibe-ocr").resolve()


def _uv_sources() -> dict:
    """读取 ``pyproject.toml`` 里的 ``[tool.uv.sources]``。

    Returns:
        dict: uv 源声明；未配置时为空字典。
    """
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data.get("tool", {}).get("uv", {}).get("sources", {})


def test_pyproject_declares_vibe_ocr_path_source() -> None:
    """``pyproject.toml`` 必须把 vibe-ocr 指向本地源码，而不是 PyPI 轮子。"""
    source = _uv_sources().get("vibe-ocr")
    assert source is not None, (
        "pyproject 缺少 [tool.uv.sources] 的 vibe-ocr 声明："
        "`uv sync` 会把它退回 PyPI 轮子，重试与缓存 TTL 会静默消失"
    )

    declared = (ROOT / source.get("path", "")).resolve()
    assert (
        declared == EXPECTED_SOURCE_DIR
    ), f"vibe-ocr path 源指向 {declared}，应为 {EXPECTED_SOURCE_DIR}"
    assert declared.is_dir(), f"vibe-ocr 本地源码目录不存在: {declared}"
    assert source.get("editable") is True, "vibe-ocr 必须声明 editable，否则改库源码不会生效"


def test_installed_vibe_ocr_comes_from_local_source() -> None:
    """当前 venv 里实际装上的 ``vibe_ocr`` 必须来自本地源码。"""
    import vibe_ocr

    installed = Path(vibe_ocr.__file__).resolve()
    assert str(installed).lower().startswith(str(EXPECTED_SOURCE_DIR).lower()), (
        f"vibe_ocr 实际来自 {installed}，不是本地源码 {EXPECTED_SOURCE_DIR} —— "
        "这正是 `uv sync` 退回 PyPI 轮子的症状"
    )


def test_library_keeps_cache_ttl_and_retry_capabilities() -> None:
    """库必须仍导出缓存 TTL 与重试参数（能力契约）。"""
    from vibe_ocr import ocr_helper as lib

    ttl = getattr(lib, "DEFAULT_CACHE_TTL_SECONDS", None)
    assert ttl == 24 * 60 * 60, f"缓存 TTL 常量缺失或不是 24 小时: {ttl!r}"

    delays = getattr(lib, "OCR_RETRY_DELAYS_SECONDS", None)
    assert delays, "缺少 OCR 请求重试参数：代理的瞬时 502 会再次退化成「这次没读到」"

    status_codes = getattr(lib, "TRANSIENT_HTTP_STATUS_CODES", ())
    assert 502 in status_codes, f"可重试状态码里没有 502: {status_codes!r}"


def test_ocr_helper_accepts_cache_ttl_seconds() -> None:
    """``OCRHelper`` 构造参数必须支持 ``cache_ttl_seconds``（项目封装按它透传）。"""
    import vibe_ocr

    parameters = inspect.signature(vibe_ocr.OCRHelper.__init__).parameters
    assert (
        "cache_ttl_seconds" in parameters
    ), "OCRHelper 不认识 cache_ttl_seconds —— 装的是 PyPI 旧轮子，项目侧 ocr_helper 会 TypeError"
