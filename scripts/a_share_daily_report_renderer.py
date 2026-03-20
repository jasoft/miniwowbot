"""A 股单页日报 HTML 渲染。"""

from __future__ import annotations

from html import escape

from scripts.a_share_daily_report_data import IndexSeries, IndexSnapshot, MarketReport, format_turnover


def render_report_html(report: MarketReport) -> str:
    """渲染单页 A4 HTML。

    Args:
        report: 市场日报数据对象。

    Returns:
        可直接导出为 PDF 的 HTML 文本。
    """
    hero_cards = "".join(_render_index_card(item) for item in report.major_indices)
    summary_cards = "".join(_render_benchmark_card(item) for item in report.benchmark_indices)
    points = "".join(f"<li>{escape(item)}</li>" for item in report.key_points)
    trend_chart = _render_trend_chart(report.series)
    performance_chart = _render_performance_chart(report.benchmark_indices, report.major_indices[2])
    source_text = " / ".join(report.sources)
    report_date = report.as_of_date.strftime("%Y-%m-%d")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>今日A股市场简报</title>
  <style>
    @page {{ size: A4; margin: 0; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(255, 213, 173, 0.75), transparent 28%),
        radial-gradient(circle at bottom right, rgba(185, 225, 255, 0.75), transparent 22%),
        linear-gradient(135deg, #fffaf5 0%, #f6f8fb 45%, #eef5ff 100%);
      color: #1f2937;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 12mm 12mm 10mm;
      display: grid;
      grid-template-rows: auto auto auto 1fr auto;
      gap: 6mm;
    }}
    .header {{
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 5mm;
      align-items: stretch;
    }}
    .hero,
    .aside,
    .panel {{
      border: 1px solid rgba(15, 23, 42, 0.08);
      border-radius: 8mm;
      background: rgba(255, 255, 255, 0.86);
      box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
      backdrop-filter: blur(12px);
    }}
    .hero {{
      padding: 8mm;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .eyebrow {{
      font-size: 10pt;
      color: #b45309;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    h1 {{
      margin: 3mm 0 2mm;
      font-size: 26pt;
      line-height: 1.1;
      color: #111827;
    }}
    .subheadline {{
      margin: 0;
      font-size: 12.5pt;
      color: #374151;
      line-height: 1.5;
    }}
    .meta {{
      margin-top: 4mm;
      display: flex;
      gap: 4mm;
      font-size: 10pt;
      color: #4b5563;
      flex-wrap: wrap;
    }}
    .chip {{
      padding: 1.5mm 3mm;
      background: #fef3c7;
      border-radius: 999px;
      font-weight: 700;
    }}
    .aside {{
      padding: 7mm;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 4mm;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(245, 248, 255, 0.92)),
        linear-gradient(135deg, rgba(255, 224, 196, 0.45), rgba(191, 219, 254, 0.45));
    }}
    .aside-title {{
      margin: 0;
      font-size: 10.5pt;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.18em;
    }}
    .temperature {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 3mm;
      align-items: end;
    }}
    .temp-card {{
      padding: 3mm;
      border-radius: 5mm;
      background: rgba(255, 255, 255, 0.78);
      text-align: center;
    }}
    .temp-value {{
      font-size: 18pt;
      font-weight: 800;
    }}
    .temp-label {{
      margin-top: 1mm;
      font-size: 9pt;
      color: #6b7280;
    }}
    .indices {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4mm;
    }}
    .index-card {{
      padding: 5mm;
      border-radius: 7mm;
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid rgba(15, 23, 42, 0.06);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }}
    .index-title {{
      font-size: 10pt;
      color: #6b7280;
    }}
    .index-price {{
      margin-top: 2mm;
      font-size: 22pt;
      font-weight: 800;
      color: #111827;
    }}
    .index-change {{
      margin-top: 1.5mm;
      font-size: 11pt;
      font-weight: 700;
    }}
    .positive {{ color: #b91c1c; }}
    .negative {{ color: #0f766e; }}
    .neutral {{ color: #374151; }}
    .turnover {{
      margin-top: 2mm;
      font-size: 9pt;
      color: #6b7280;
    }}
    .chart-row {{
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 4mm;
    }}
    .panel {{
      padding: 5mm;
    }}
    .panel h2 {{
      margin: 0 0 3mm;
      font-size: 13pt;
    }}
    .panel p {{
      margin: 0 0 3mm;
      color: #6b7280;
      font-size: 9.5pt;
    }}
    .benchmark-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 3mm;
    }}
    .benchmark-card {{
      padding: 3mm;
      border-radius: 5mm;
      background: #f8fafc;
    }}
    .benchmark-name {{
      font-size: 9pt;
      color: #6b7280;
    }}
    .benchmark-value {{
      margin-top: 1mm;
      font-size: 15pt;
      font-weight: 800;
    }}
    .bottom-row {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 4mm;
    }}
    .insights {{
      margin: 0;
      padding-left: 5mm;
      display: grid;
      gap: 2mm;
      font-size: 10.5pt;
      line-height: 1.45;
    }}
    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: #6b7280;
      font-size: 8.5pt;
      padding: 0 1mm;
    }}
    svg text {{
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="header">
      <div class="hero">
        <div>
          <div class="eyebrow">China A-Share Daily Brief</div>
          <h1>今日A股市场简报</h1>
          <p class="subheadline"><strong>{escape(report.headline)}</strong><br>{escape(report.subheadline)}</p>
        </div>
        <div class="meta">
          <span class="chip">{escape(report_date)}</span>
          <span>单页 A4 打印版</span>
          <span>数据源：{escape(source_text)}</span>
        </div>
      </div>
      <aside class="aside">
        <h2 class="aside-title">市场温度</h2>
        <div class="temperature">
          {_render_temperature_card("领涨", report.major_indices[2].name, report.major_indices[2].change_percent)}
          {_render_temperature_card("承压", report.major_indices[0].name, report.major_indices[0].change_percent)}
          {_render_temperature_card("风格差", "创业板-沪深300", report.major_indices[2].change_percent - report.benchmark_indices[1].change_percent)}
        </div>
      </aside>
    </section>

    <section class="indices">{hero_cards}</section>

    <section class="chart-row">
      <div class="panel" id="trend-chart">
        <h2>近阶段核心指数走势</h2>
        <p>近 7 个交易日收盘点位，用于快速判断市场分化方向。</p>
        {trend_chart}
      </div>
      <div class="panel" id="relative-performance-chart">
        <h2>宽基表现对比</h2>
        <p>观察蓝筹、核心资产与中小盘的日内强弱。</p>
        {performance_chart}
      </div>
    </section>

    <section class="panel">
      <h2>风格横截面</h2>
      <p>用更多宽基指数补充今天的结构特征。</p>
      <div class="benchmark-grid">{summary_cards}</div>
    </section>

    <section class="bottom-row">
      <div class="panel">
        <h2>今日要点</h2>
        <ul class="insights">{points}</ul>
      </div>
      <div class="panel">
        <h2>打印提示</h2>
        <p>版式已固定为单页 A4，适合直接导出为 PDF 并发送到默认打印机。</p>
        <p>建议使用彩色打印，以保留指数卡片、趋势线和结构分化的视觉层次。</p>
        <p>如需复盘，可保留 PDF 存档，后续按日期连续对比市场节奏变化。</p>
      </div>
    </section>

    <footer class="footer">
      <span>仅作市场信息整理，不构成投资建议。</span>
      <span>生成日期：{escape(report_date)}</span>
    </footer>
  </main>
</body>
</html>
"""


def _render_index_card(snapshot: IndexSnapshot) -> str:
    """渲染主指数卡片。"""
    change_class = _change_class(snapshot.change_percent)
    sign = "+" if snapshot.change_percent > 0 else ""
    amount_sign = "+" if snapshot.change_amount > 0 else ""

    return f"""
    <article class="index-card">
      <div class="index-title">{escape(snapshot.name)}</div>
      <div class="index-price">{snapshot.latest:.2f}</div>
      <div class="index-change {change_class}">{sign}{snapshot.change_percent:.2f}% / {amount_sign}{snapshot.change_amount:.2f}</div>
      <div class="turnover">成交额：{escape(format_turnover(snapshot.turnover))}</div>
    </article>
    """


def _render_benchmark_card(snapshot: IndexSnapshot) -> str:
    """渲染风格横截面卡片。"""
    change_class = _change_class(snapshot.change_percent)
    sign = "+" if snapshot.change_percent > 0 else ""
    return f"""
    <article class="benchmark-card">
      <div class="benchmark-name">{escape(snapshot.name)}</div>
      <div class="benchmark-value">{snapshot.latest:.2f}</div>
      <div class="{change_class}">{sign}{snapshot.change_percent:.2f}%</div>
    </article>
    """


def _render_temperature_card(label: str, name: str, value: float) -> str:
    """渲染右上角温度卡。"""
    sign = "+" if value > 0 else ""
    return f"""
    <div class="temp-card">
      <div class="temp-label">{escape(label)}</div>
      <div class="temp-value {_change_class(value)}">{sign}{value:.2f}%</div>
      <div class="temp-label">{escape(name)}</div>
    </div>
    """


def _render_trend_chart(series: tuple[IndexSeries, ...]) -> str:
    """渲染趋势图 SVG。"""
    selected_series = series[:5]
    width = 780
    height = 330
    padding_left = 62
    padding_right = 24
    padding_top = 20
    padding_bottom = 44

    all_values = [value for item in selected_series for value in item.values]
    min_value = min(all_values)
    max_value = max(all_values)
    value_range = max(max_value - min_value, 1.0)
    usable_width = width - padding_left - padding_right
    usable_height = height - padding_top - padding_bottom
    labels = selected_series[0].labels
    step_x = usable_width / max(len(labels) - 1, 1)
    palette = ("#ef4444", "#1d4ed8", "#f59e0b", "#7c3aed", "#0f766e")

    grid_lines = []
    for index in range(5):
        y = padding_top + usable_height * index / 4
        value = max_value - value_range * index / 4
        grid_lines.append(
            f'<line x1="{padding_left}" y1="{y:.2f}" x2="{width - padding_right}" y2="{y:.2f}" '
            'stroke="#e5e7eb" stroke-width="1" />'
            f'<text x="8" y="{y + 4:.2f}" fill="#6b7280" font-size="12">{value:.0f}</text>'
        )

    x_labels = []
    for index, label in enumerate(labels):
        x = padding_left + index * step_x
        x_labels.append(
            f'<text x="{x:.2f}" y="{height - 14}" fill="#6b7280" font-size="12" text-anchor="middle">{escape(label[5:])}</text>'
        )

    lines = []
    legends = []
    for index, item in enumerate(selected_series):
        color = palette[index]
        points = []
        for point_index, value in enumerate(item.values):
            x = padding_left + point_index * step_x
            y = padding_top + (max_value - value) / value_range * usable_height
            points.append(f"{x:.2f},{y:.2f}")
        lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3.2" stroke-linecap="round" '
            f'stroke-linejoin="round" points="{" ".join(points)}" />'
        )
        legends.append(
            f'<text x="{padding_left + index * 128:.2f}" y="16" fill="{color}" font-size="12" font-weight="700">{escape(item.name)}</text>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="240" role="img" aria-label="指数走势">'
        f'{"".join(grid_lines)}'
        f'{"".join(x_labels)}'
        f'{"".join(lines)}'
        f'{"".join(legends)}'
        "</svg>"
    )


def _render_performance_chart(
    benchmarks: tuple[IndexSnapshot, ...],
    chinext: IndexSnapshot,
) -> str:
    """渲染表现对比柱状图。"""
    items = (chinext,) + benchmarks
    width = 460
    height = 330
    padding = 28
    baseline = 165
    max_abs = max(abs(item.change_percent) for item in items) or 1.0
    bar_width = 52
    gap = 22

    bars = []
    for index, item in enumerate(items):
        x = padding + index * (bar_width + gap)
        magnitude = abs(item.change_percent) / max_abs * 110
        y = baseline - magnitude if item.change_percent >= 0 else baseline
        color = "#d9485f" if item.change_percent >= 0 else "#0f766e"
        bars.append(
            f'<rect x="{x}" y="{y:.2f}" width="{bar_width}" height="{magnitude:.2f}" rx="14" fill="{color}" opacity="0.88" />'
            f'<text x="{x + bar_width / 2:.2f}" y="{y - 10 if item.change_percent >= 0 else y + magnitude + 18:.2f}" '
            f'fill="{color}" font-size="12" text-anchor="middle" font-weight="700">{item.change_percent:+.2f}%</text>'
            f'<text x="{x + bar_width / 2:.2f}" y="304" fill="#6b7280" font-size="11" text-anchor="middle">{escape(item.name)}</text>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="240" role="img" aria-label="宽基表现对比">'
        f'<line x1="14" y1="{baseline}" x2="{width - 12}" y2="{baseline}" stroke="#cbd5e1" stroke-width="1.5" />'
        f'{"".join(bars)}'
        "</svg>"
    )


def _change_class(value: float) -> str:
    """根据涨跌幅返回 CSS 类名。"""
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"
