"""A 股单页日报的数据整理逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class IndexSnapshot:
    """指数快照。"""

    code: str
    name: str
    latest: float
    change_percent: float
    change_amount: float
    turnover: float


@dataclass(frozen=True)
class IndexSeries:
    """指数历史序列。"""

    name: str
    labels: tuple[str, ...]
    values: tuple[float, ...]


@dataclass(frozen=True)
class MarketReport:
    """单页市场日报数据。"""

    as_of_date: date
    headline: str
    subheadline: str
    major_indices: tuple[IndexSnapshot, ...]
    benchmark_indices: tuple[IndexSnapshot, ...]
    series: tuple[IndexSeries, ...]
    key_points: tuple[str, ...]
    sources: tuple[str, ...]


def format_turnover(value: float) -> str:
    """把成交额格式化为亿元。

    Args:
        value: 原始成交额，单位为元。

    Returns:
        以亿元为单位的格式化字符串。
    """
    return f"{value / 100_000_000:.2f} 亿元"


def build_market_report(
    as_of_date: date,
    snapshots: tuple[IndexSnapshot, ...],
    series: tuple[IndexSeries, ...],
) -> MarketReport:
    """根据指数快照与序列构建日报模型。

    Args:
        as_of_date: 报告日期。
        snapshots: 指数快照集合。
        series: 指数历史序列集合。

    Returns:
        渲染 HTML 所需的市场日报对象。
    """
    snapshots_by_name = {item.name: item for item in snapshots}

    major_indices = (
        snapshots_by_name["上证指数"],
        snapshots_by_name["深证成指"],
        snapshots_by_name["创业板指"],
    )
    benchmark_indices = (
        snapshots_by_name["上证50"],
        snapshots_by_name["沪深300"],
        snapshots_by_name["中证500"],
        snapshots_by_name["中证1000"],
    )

    headline = _build_headline(
        shanghai=major_indices[0],
        shenzhen=major_indices[1],
        chinext=major_indices[2],
    )
    subheadline = _build_subheadline(
        shanghai=major_indices[0],
        chinext=major_indices[2],
        csi300=snapshots_by_name["沪深300"],
    )
    key_points = _build_key_points(
        shanghai=major_indices[0],
        shenzhen=major_indices[1],
        chinext=major_indices[2],
        csi300=snapshots_by_name["沪深300"],
        csi1000=snapshots_by_name["中证1000"],
        snapshots=snapshots,
    )

    return MarketReport(
        as_of_date=as_of_date,
        headline=headline,
        subheadline=subheadline,
        major_indices=major_indices,
        benchmark_indices=benchmark_indices,
        series=series,
        key_points=key_points,
        sources=(
            "东方财富公开行情接口",
            "指数历史日线接口",
        ),
    )


def _build_headline(
    shanghai: IndexSnapshot,
    shenzhen: IndexSnapshot,
    chinext: IndexSnapshot,
) -> str:
    """生成头部主标题。"""
    if chinext.change_percent > 0 and shanghai.change_percent < 0 and shenzhen.change_percent < 0:
        return "创业板逆势走强，主板指数承压回落"
    if all(item.change_percent > 0 for item in (shanghai, shenzhen, chinext)):
        return "三大指数齐涨，市场情绪明显修复"
    if all(item.change_percent < 0 for item in (shanghai, shenzhen, chinext)):
        return "三大指数同步回调，风险偏好明显回落"
    return "指数走势分化，市场风格快速切换"


def _build_subheadline(
    shanghai: IndexSnapshot,
    chinext: IndexSnapshot,
    csi300: IndexSnapshot,
) -> str:
    """生成副标题。"""
    growth_edge = chinext.change_percent - csi300.change_percent
    if growth_edge >= 1.0 and shanghai.change_percent < 0:
        return "三大指数分化，成长风格明显强于大盘蓝筹。"
    if shanghai.change_percent > 0 and chinext.change_percent > 0:
        return "权重与成长共振走强，市场赚钱效应回暖。"
    return "宽基指数表现不一，场内资金围绕结构性机会切换。"


def _build_key_points(
    shanghai: IndexSnapshot,
    shenzhen: IndexSnapshot,
    chinext: IndexSnapshot,
    csi300: IndexSnapshot,
    csi1000: IndexSnapshot,
    snapshots: tuple[IndexSnapshot, ...],
) -> tuple[str, ...]:
    """生成摘要要点。"""
    total_turnover = sum(item.turnover for item in snapshots)
    growth_edge = chinext.change_percent - shanghai.change_percent
    leadership_edge = chinext.change_percent - csi300.change_percent

    return (
        (
            f"创业板指逆势上涨 {chinext.change_percent:.2f}%，"
            f"较上证指数高出 {growth_edge:.2f} 个百分点，成长板块相对更强。"
        ),
        (
            f"主要宽基指数成交额合计约 {format_turnover(total_turnover)}，"
            "场内交投仍保持在高活跃区间。"
        ),
        (
            f"中证1000 跌幅 {abs(csi1000.change_percent):.2f}%，"
            f"而沪深300 仅变动 {abs(csi300.change_percent):.2f}%，"
            f"风格分化幅度达到 {leadership_edge:.2f} 个百分点。"
        ),
        (
            f"深证成指收于 {shenzhen.latest:.2f} 点，"
            f"单日回撤 {abs(shenzhen.change_amount):.2f} 点，主板修复力度仍待观察。"
        ),
    )
