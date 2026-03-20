"""生成并打印今日 A 股单页日报。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.a_share_daily_report_exporter import (
    build_report_paths,
    export_pdf,
    find_edge_path,
    print_pdf,
)
from scripts.a_share_daily_report_fetcher import fetch_market_report
from scripts.a_share_daily_report_renderer import render_report_html


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    Returns:
        解析后的命名空间对象。
    """
    parser = argparse.ArgumentParser(description="生成并打印今日 A 股单页日报")
    parser.add_argument(
        "--output-dir",
        default="output/a_share_reports",
        help="HTML 和 PDF 输出目录",
    )
    parser.add_argument(
        "--printer-name",
        default=None,
        help="指定打印机名称；默认使用系统默认打印机",
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="只生成 HTML/PDF，不执行打印",
    )
    return parser.parse_args()


def main() -> int:
    """脚本主入口。

    Returns:
        进程退出码。
    """
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = fetch_market_report()
    html = render_report_html(report)
    html_path, pdf_path = build_report_paths(
        output_dir=output_dir,
        report_date=report.as_of_date,
    )
    html_path.write_text(html, encoding="utf-8")

    edge_path = find_edge_path()
    export_pdf(edge_path=edge_path, html_path=html_path, pdf_path=pdf_path)

    if not args.no_print:
        print_pdf(pdf_path=pdf_path, printer_name=args.printer_name)

    print(f"HTML 已生成: {html_path}")
    print(f"PDF 已生成: {pdf_path}")
    if args.no_print:
        print("已跳过打印。")
    else:
        print("已发送到打印机。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
