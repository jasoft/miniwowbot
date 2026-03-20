"""A 股日报的导出与打印工具。"""

from __future__ import annotations

import subprocess
import time
from datetime import date
from pathlib import Path


def build_report_paths(output_dir: Path, report_date: date) -> tuple[Path, Path]:
    """构建 HTML 和 PDF 输出路径。

    Args:
        output_dir: 输出目录。
        report_date: 报告日期。

    Returns:
        HTML 路径和 PDF 路径。
    """
    slug = f"{report_date.isoformat()}-a-share-daily-brief"
    return output_dir / f"{slug}.html", output_dir / f"{slug}.pdf"


def find_edge_path() -> Path:
    """查找本机 Edge 可执行文件。

    Returns:
        Edge 可执行文件路径。

    Raises:
        FileNotFoundError: 未找到 Edge 时抛出。
    """
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("未找到 Microsoft Edge，可执行 PDF 导出失败。")


def build_edge_pdf_command(edge_path: Path, html_path: Path, pdf_path: Path) -> list[str]:
    """构建 Edge 导出 PDF 命令。

    Args:
        edge_path: Edge 可执行文件。
        html_path: HTML 输入文件。
        pdf_path: PDF 输出文件。

    Returns:
        适合 `subprocess.run` 的命令参数列表。
    """
    html_uri = html_path.resolve().as_uri()
    return [
        str(edge_path),
        "--headless",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        f"--print-to-pdf={pdf_path.resolve()}",
        html_uri,
    ]


def export_pdf(edge_path: Path, html_path: Path, pdf_path: Path) -> None:
    """使用 Edge 把 HTML 导出为 PDF。

    Args:
        edge_path: Edge 可执行文件。
        html_path: HTML 文件路径。
        pdf_path: PDF 输出路径。
    """
    command = build_edge_pdf_command(edge_path=edge_path, html_path=html_path, pdf_path=pdf_path)
    subprocess.run(command, check=True, capture_output=True, text=True)


def print_pdf(pdf_path: Path, printer_name: str | None = None) -> None:
    """把 PDF 发送到打印机。

    Args:
        pdf_path: PDF 文件路径。
        printer_name: 打印机名称；为空时使用默认打印机。
    """
    if printer_name:
        verb = "PrintTo"
        printer_argument = f'"{printer_name}"'
        command = (
            f'Start-Process -FilePath "{pdf_path}" -Verb {verb} '
            f'-ArgumentList {printer_argument}'
        )
    else:
        command = f'Start-Process -FilePath "{pdf_path}" -Verb Print'
    subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            command,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    time.sleep(3)
