"""A 股日报的数据抓取与解析。"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import requests

from scripts.a_share_daily_report_data import IndexSeries, IndexSnapshot, MarketReport, build_market_report

SNAPSHOT_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
    "Connection": "close",
}
INDEX_SECIDS: tuple[tuple[str, str], ...] = (
    ("上证指数", "1.000001"),
    ("深证成指", "0.399001"),
    ("创业板指", "0.399006"),
    ("上证50", "1.000016"),
    ("沪深300", "1.000300"),
    ("中证500", "1.000905"),
    ("中证1000", "1.000852"),
)
TREND_SECIDS: tuple[tuple[str, str], ...] = (
    ("上证指数", "1.000001"),
    ("深证成指", "0.399001"),
    ("创业板指", "0.399006"),
    ("沪深300", "1.000300"),
    ("中证1000", "1.000852"),
)


def fetch_market_report(series_limit: int = 7) -> MarketReport:
    """抓取并构建市场日报对象。

    Args:
        series_limit: 历史序列保留的交易日数量。

    Returns:
        渲染所需的完整市场日报对象。
    """
    snapshots = fetch_index_snapshots()
    series = tuple(fetch_index_series(name=name, secid=secid, limit=series_limit) for name, secid in TREND_SECIDS)
    report_date = date.fromisoformat(series[0].labels[-1])
    return build_market_report(
        as_of_date=report_date,
        snapshots=snapshots,
        series=series,
    )


def fetch_index_snapshots() -> tuple[IndexSnapshot, ...]:
    """抓取宽基指数快照。"""
    payload = _get_json(
        SNAPSHOT_URL,
        {
            "fltt": "2",
            "invt": "2",
            "fields": "f12,f14,f2,f3,f4,f6",
            "secids": ",".join(secid for _, secid in INDEX_SECIDS),
        },
    )
    return parse_snapshot_response(payload)


def fetch_index_series(name: str, secid: str, limit: int) -> IndexSeries:
    """抓取单个指数的日线序列。"""
    payload = _get_json(
        KLINE_URL,
        {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "beg": "20260101",
            "end": "20500101",
            "rtntype": "6",
            "secid": secid,
            "klt": "101",
            "fqt": "0",
        },
    )
    series = parse_kline_response(payload, limit=limit)
    if series.name != name:
        return IndexSeries(name=name, labels=series.labels, values=series.values)
    return series


def parse_snapshot_response(payload: dict[str, Any]) -> tuple[IndexSnapshot, ...]:
    """解析指数快照接口返回。

    Args:
        payload: 东方财富接口 JSON。

    Returns:
        排序后的指数快照元组。
    """
    diff = payload["data"]["diff"]
    snapshots = tuple(
        IndexSnapshot(
            code=str(item["f12"]),
            name=str(item["f14"]),
            latest=float(item["f2"]),
            change_percent=float(item["f3"]),
            change_amount=float(item["f4"]),
            turnover=float(item["f6"]),
        )
        for item in diff
    )
    order = {name: index for index, (name, _) in enumerate(INDEX_SECIDS)}
    return tuple(sorted(snapshots, key=lambda item: order[item.name]))


def parse_kline_response(payload: dict[str, Any], limit: int) -> IndexSeries:
    """解析指数 K 线接口返回。

    Args:
        payload: 东方财富接口 JSON。
        limit: 保留的尾部记录数。

    Returns:
        历史序列对象。
    """
    rows = payload["data"]["klines"][-limit:]
    labels = []
    values = []
    for row in rows:
        parts = row.split(",")
        labels.append(parts[0])
        values.append(float(parts[2]))
    return IndexSeries(
        name=str(payload["data"]["name"]),
        labels=tuple(labels),
        values=tuple(values),
    )


def _get_json(url: str, params: dict[str, str], max_attempts: int = 4) -> dict[str, Any]:
    """带重试地请求 JSON 接口。

    Args:
        url: 目标地址。
        params: 查询参数。
        max_attempts: 最大尝试次数。

    Returns:
        JSON 字典对象。

    Raises:
        RuntimeError: 多次请求后仍失败时抛出。
    """
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(attempt * 1.2)
    raise RuntimeError(f"请求行情接口失败: {url}") from last_error
