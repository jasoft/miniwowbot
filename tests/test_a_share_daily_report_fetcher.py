"""A 股日报抓取与导出辅助逻辑测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.a_share_daily_report_exporter import build_edge_pdf_command, build_report_paths
from scripts.a_share_daily_report_fetcher import parse_kline_response, parse_snapshot_response


def test_parse_snapshot_response_extracts_index_snapshots() -> None:
    """快照接口应正确解析指数列表。"""
    payload = {
        "data": {
            "diff": [
                {
                    "f12": "000001",
                    "f14": "上证指数",
                    "f2": 3957.05,
                    "f3": -1.24,
                    "f4": -49.50,
                    "f6": 964_863_108_628.7,
                },
                {
                    "f12": "399006",
                    "f14": "创业板指",
                    "f2": 3352.10,
                    "f3": 1.30,
                    "f4": 43.0,
                    "f6": 663_304_503_456.09,
                },
            ]
        }
    }

    snapshots = parse_snapshot_response(payload)

    assert snapshots[0].name == "上证指数"
    assert snapshots[1].change_percent == 1.30
    assert snapshots[1].turnover == 663_304_503_456.09


def test_parse_kline_response_keeps_latest_rows_with_labels() -> None:
    """K 线接口应保留最近若干交易日。"""
    payload = {
        "data": {
            "name": "上证指数",
            "klines": [
                "2026-03-17,4005.50,4005.50,4011.00,3982.00,0,0,0,0,0,0",
                "2026-03-18,3988.30,3988.30,3993.00,3970.00,0,0,0,0,0,0",
                "2026-03-19,4006.55,4006.55,4010.00,3988.00,0,0,0,0,0,0",
                "2026-03-20,3957.05,3957.05,3961.00,3948.00,0,0,0,0,0,0",
            ]
        }
    }

    series = parse_kline_response(payload, limit=3)

    assert series.name == "上证指数"
    assert series.labels == ("2026-03-18", "2026-03-19", "2026-03-20")
    assert series.values == (3988.30, 4006.55, 3957.05)


def test_build_report_paths_uses_date_slug() -> None:
    """导出路径应按日期生成统一文件名。"""
    html_path, pdf_path = build_report_paths(
        output_dir=Path("output/a_share_reports"),
        report_date=date(2026, 3, 20),
    )

    assert html_path.as_posix().endswith("2026-03-20-a-share-daily-brief.html")
    assert pdf_path.as_posix().endswith("2026-03-20-a-share-daily-brief.pdf")


def test_build_edge_pdf_command_points_to_html_and_pdf() -> None:
    """Edge 导出命令应包含输入 HTML 和输出 PDF。"""
    command = build_edge_pdf_command(
        edge_path=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        html_path=Path("E:/Projects/miniwowbot/output/report.html"),
        pdf_path=Path("E:/Projects/miniwowbot/output/report.pdf"),
    )

    joined = " ".join(command)
    assert "--print-to-pdf=E:\\Projects\\miniwowbot\\output\\report.pdf" in joined
    assert "file:///E:/Projects/miniwowbot/output/report.html" in joined
