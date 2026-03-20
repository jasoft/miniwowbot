"""A 股日报生成逻辑测试。"""

from __future__ import annotations

from datetime import date

from scripts.a_share_daily_report_data import (
    IndexSeries,
    IndexSnapshot,
    build_market_report,
    format_turnover,
)
from scripts.a_share_daily_report_renderer import render_report_html


def _build_snapshots() -> tuple[IndexSnapshot, ...]:
    """构造用于测试的指数快照。"""
    return (
        IndexSnapshot(
            code="000001",
            name="上证指数",
            latest=3957.05,
            change_percent=-1.24,
            change_amount=-49.50,
            turnover=964_863_108_628.7,
        ),
        IndexSnapshot(
            code="399001",
            name="深证成指",
            latest=13866.20,
            change_percent=-0.25,
            change_amount=-35.37,
            turnover=1_321_995_589_658.72,
        ),
        IndexSnapshot(
            code="399006",
            name="创业板指",
            latest=3352.10,
            change_percent=1.30,
            change_amount=43.00,
            turnover=663_304_503_456.09,
        ),
        IndexSnapshot(
            code="000016",
            name="上证50",
            latest=2883.86,
            change_percent=-1.11,
            change_amount=-32.37,
            turnover=135_730_910_402.0,
        ),
        IndexSnapshot(
            code="000300",
            name="沪深300",
            latest=4567.02,
            change_percent=-0.35,
            change_amount=-16.23,
            turnover=615_463_088_557.8,
        ),
        IndexSnapshot(
            code="000905",
            name="中证500",
            latest=7760.04,
            change_percent=-1.49,
            change_amount=-117.05,
            turnover=417_113_691_310.9,
        ),
        IndexSnapshot(
            code="000852",
            name="中证1000",
            latest=7783.43,
            change_percent=-1.59,
            change_amount=-125.80,
            turnover=486_114_330_316.8,
        ),
    )


def _build_series() -> tuple[IndexSeries, ...]:
    """构造用于测试的历史走势。"""
    labels = (
        "2026-03-12",
        "2026-03-13",
        "2026-03-16",
        "2026-03-17",
        "2026-03-18",
        "2026-03-19",
        "2026-03-20",
    )
    return (
        IndexSeries(
            name="上证指数",
            labels=labels,
            values=(4010.10, 3998.60, 3982.20, 4005.50, 3988.30, 4006.55, 3957.05),
        ),
        IndexSeries(
            name="深证成指",
            labels=labels,
            values=(13940.0, 13935.0, 13888.0, 13992.0, 13956.0, 13901.57, 13866.20),
        ),
        IndexSeries(
            name="创业板指",
            labels=labels,
            values=(3290.0, 3312.0, 3308.0, 3333.0, 3322.0, 3309.10, 3352.10),
        ),
        IndexSeries(
            name="沪深300",
            labels=labels,
            values=(4588.0, 4591.0, 4577.0, 4601.0, 4589.0, 4583.25, 4567.02),
        ),
        IndexSeries(
            name="中证1000",
            labels=labels,
            values=(7920.0, 7911.0, 7892.0, 7904.0, 7860.0, 7909.23, 7783.43),
        ),
    )


def test_format_turnover_uses_yi_unit_for_large_values() -> None:
    """大额成交额应格式化为亿元。"""
    assert format_turnover(964_863_108_628.7) == "9648.63 亿元"


def test_build_market_report_generates_expected_headline_and_points() -> None:
    """市场摘要应体现分化与成交额特征。"""
    report = build_market_report(
        as_of_date=date(2026, 3, 20),
        snapshots=_build_snapshots(),
        series=_build_series(),
    )

    assert report.headline == "创业板逆势走强，主板指数承压回落"
    assert report.subheadline == "三大指数分化，成长风格明显强于大盘蓝筹。"
    assert any("创业板指逆势上涨 1.30%" in point for point in report.key_points)
    assert any("主要宽基指数成交额合计约 46045.85 亿元" in point for point in report.key_points)
    assert any("中证1000 跌幅 1.59%" in point for point in report.key_points)


def test_render_report_html_contains_a4_layout_and_core_sections() -> None:
    """HTML 应包含单页 A4 版式与核心内容。"""
    report = build_market_report(
        as_of_date=date(2026, 3, 20),
        snapshots=_build_snapshots(),
        series=_build_series(),
    )

    html = render_report_html(report)

    assert "@page { size: A4;" in html
    assert "今日A股市场简报" in html
    assert "创业板逆势走强，主板指数承压回落" in html
    assert "relative-performance-chart" in html
    assert "trend-chart" in html
    assert "上证指数" in html
    assert "创业板指" in html
