"""HTML rendering: one reading column, K-line section built around the charts."""
from __future__ import annotations

import html
import json
from datetime import datetime

from . import config
from .config import BJT, KLINE_SUMMARY_ORDER, MACRO_ORDER, TF_LABELS, TF_ORDER
from .market import STALE_AFTER_DAYS, candles_to_bars, series_lag_days, should_expand, svg_candles
from .sources import Section
from .text import md_to_html

MARKET_LABELS = {"CN": "A 股", "HK": "港股", "US": "美股", "KR": "韩股"}
MARKET_ORDER = ["CN", "HK", "US", "KR"]
STOCK_BARS = 80


def fmt_px(v) -> str:
    """Prices without float noise: 718.96, 34.80, 0.0456, 4480."""
    if v is None or not isinstance(v, (int, float)):
        return "—"
    a = abs(v)
    d = 4 if a < 1 else 3 if a < 10 else 2
    text = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return text if "." in text or a >= 1000 else f"{v:.2f}"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{'+' if v > 0 else ''}{v:.2f}%"


def cls_pct(v: float | None) -> str:
    if v is None:
        return ""
    return "up" if v > 0 else "dn" if v < 0 else ""


def note_for(notes: dict[str, str], *keys: str) -> str:
    for k in keys:
        if k and k in notes:
            return notes[k]
    return ""


def chart_box(key: str, tf: str, candles: list[dict] | None, height: int, caption: str = "", sub: str = "") -> str:
    """A chart slot: the interactive chart mounts here; the inline SVG shows until it does."""
    placeholder = svg_candles(candles, 420, height, min(len(candles), 80)) if candles else ""
    cap = f'<figcaption>{html.escape(caption)}<small>{html.escape(sub)}</small></figcaption>' if caption else ""
    return f'<figure class="kc">{cap}<div class="chart" data-key="{html.escape(key)}" data-tf="{tf}" style="height:{height}px">{placeholder}</div></figure>'


def macro_bars(key: str, entry: dict | None, overview_asset: dict | None) -> dict[str, list]:
    """Daily from kline.db (written 08:15, always current); intraday from the review server."""
    out: dict[str, list] = {}
    if entry and entry.get("candles"):
        out["daily"] = candles_to_bars(entry["candles"])
    tfs = (overview_asset or {}).get("timeframes", {})
    for tf in ("four_hour", "thirty_minute"):
        info = tfs.get(tf)
        if info and info.get("bars"):
            out[tf] = info["bars"]
    if "daily" not in out and (tfs.get("daily") or {}).get("bars"):
        out["daily"] = tfs["daily"]["bars"]
    return out


def render_macro(key: str, entry: dict | None, analysis: dict | None, note: str, overview_asset: dict | None, condensed: dict | None) -> tuple[str, dict[str, list]]:
    name = (overview_asset or {}).get("name") or (analysis["name"] if analysis else (entry["name"] if entry else key))
    stats = entry["stats"] if entry else {}
    bars = macro_bars(key, entry, overview_asset)
    reference = stats.get("as_of") or (bars.get("daily") or [[""]])[-1][0]
    charts = []
    for tf in TF_ORDER:
        rows = bars.get(tf)
        if not rows:
            continue
        as_of = str(rows[-1][0])[:16].replace("T", " ")
        lag = series_lag_days(as_of, reference) if tf != "daily" else None
        stale = f"（落后 {lag} 天）" if lag is not None and lag > STALE_AFTER_DAYS else ""
        charts.append(chart_box(key, tf, entry["candles"] if (entry and tf == "daily") else None, 230, TF_LABELS[tf], as_of + stale))
    tags = ""
    body = ""
    if condensed:
        tags = "".join(f'<span class="tg {cls}">{html.escape(condensed.get(k, ""))}</span>' for k, cls in (("位置", "pos"), ("状态", "reg"), ("倾向", "lean")) if condensed.get(k))
        body = html.escape(condensed.get("段落", ""))
    elif analysis and analysis.get("fields", {}).get("综合结论"):
        body = html.escape(analysis["fields"]["综合结论"])
    park = f'<div class="park"><span>Park</span><div>{md_to_html(note)}</div></div>' if note else ""
    article = (
        f'<article class="macro" id="m-{html.escape(key)}">'
        f'<header><h4>{html.escape(name)}</h4><span class="px">{fmt_px(stats.get("close"))}</span><span class="chg {cls_pct(stats.get("chg1d"))}">{fmt_pct(stats.get("chg1d"))}</span><span class="tags">{tags}</span></header>'
        f'<div class="charts n{len(charts)}">{"".join(charts)}</div>'
        f'{f"<p class=para>{body}</p>" if body else ""}{park}</article>'
    )
    return article, bars


def render_stock(s: dict, note: str, park_note: str, expanded: bool = False) -> str:
    st = s["stats"]
    park = f'<div class="park"><span>Park</span><div>{md_to_html(park_note)}</div></div>' if park_note else ""
    return (
        f'<article class="stock{" hot" if expanded else ""}" id="s-{html.escape(s["id"])}">'
        f'<header><span class="sym">{html.escape(s["name"])}<small>{html.escape(s["symbol"])}</small></span>'
        f'<span class="px">{fmt_px(st.get("close"))}</span><span class="chg {cls_pct(st.get("chg1d"))}">{fmt_pct(st.get("chg1d"))}</span></header>'
        f'{chart_box(s["id"], "daily", s["candles"], 150)}'
        f'<p class="l2">{html.escape(note) if note else "<i>无描述</i>"}</p>{park}</article>'
    )


def group_stocks(stocks: list[dict], macro_names: dict) -> list[tuple[str, list[tuple[str, list[dict]]]]]:
    """Market first (A 股 / 港股 / 美股 / 韩股), then sector inside each market."""
    by_market: dict[str, dict[str, list[dict]]] = {}
    for s in stocks:
        mem = s["memberships"][0] if s["memberships"] else {}
        sector = f'{macro_names.get(mem.get("macro_id"), mem.get("macro_id", "其他"))} · {mem.get("sector_name", "未分类")}'
        by_market.setdefault(s.get("market") or "US", {}).setdefault(sector, []).append(s)
    ordered = sorted(by_market, key=lambda m: (MARKET_ORDER.index(m) if m in MARKET_ORDER else 99, m))
    out = []
    for m in ordered:
        sectors = sorted(by_market[m].items(), key=lambda kv: -len(kv[1]))
        for _, items in sectors:
            items.sort(key=lambda s: -(abs(s["stats"].get("chg1d") or 0)))
        out.append((MARKET_LABELS.get(m, m), sectors))
    return out


def render_page(date: str, ai: Section, fin: Section, kl: Section, kline: dict, macros: dict, stocks: list[dict], notes: dict, ai_notes: dict, macro_names: dict, overview: dict | None = None, condensed: dict | None = None) -> str:
    overview = overview or {}
    condensed = condensed or {}
    payload: dict[str, dict[str, list]] = {}

    def unavailable(sec: Section) -> str:
        return f'<div class="unavail"><b>今日不可用。</b>{html.escape(sec.reason or "上游管道没有产出")}。不用上一期冒充今天。</div>'

    def status_line(sec: Section) -> str:
        if sec.status == "fallback":
            return f'<p class="stat">自生成 · {html.escape(sec.reason)}</p>'
        return ""

    analysis_by_key = {a["key"]: a for a in kline["assets"] if a.get("key")}
    macro_html = []
    for key in MACRO_ORDER:
        entry = macros.get(key)
        analysis = analysis_by_key.get(key)
        if not entry and not analysis:
            continue
        note = note_for(notes, key, entry["symbol"] if entry else "", entry["name"] if entry else "", analysis["ticker"] if analysis else "", analysis["name"] if analysis else "")
        article, bars = render_macro(key, entry, analysis, note, overview.get("assets", {}).get(key), condensed.get(key))
        macro_html.append(article)
        if bars:
            payload[key] = bars

    hot = 0
    market_html = []
    for market_label, sectors in group_stocks(stocks, macro_names):
        n = sum(len(items) for _, items in sectors)
        blocks = []
        for sector, items in sectors:
            cards = []
            for s in items:
                park_note = note_for(notes, s["symbol"], s["name"], s["id"])
                exp = should_expand(s["stats"], bool(park_note))
                hot += exp
                cards.append(render_stock(s, ai_notes.get(s["id"], ""), park_note, exp))
                if s["candles"]:
                    payload[s["id"]] = {"daily": candles_to_bars(s["candles"], STOCK_BARS)}
            blocks.append(f'<div class="sector"><h5>{html.escape(sector)}<small>{len(items)}</small></h5><div class="cards">{"".join(cards)}</div></div>')
        market_html.append(f'<section class="market"><h4 class="sh">{html.escape(market_label)}<small>{n}</small></h4>{"".join(blocks)}</section>')

    overall = note_for(notes, "总", "总览", "overall")
    summ = kline.get("summary", {})
    lead = f'<div class="lead">{md_to_html(summ["今日结论"])}</div>' if summ.get("今日结论") else ""
    rest = "".join(f'<div class="sc"><span>{html.escape(label)}</span>{md_to_html(summ[label])}</div>' for label in KLINE_SUMMARY_ORDER[1:] if summ.get(label))
    narrative = f'<details class="narrative"><summary>跨资产叙事</summary><div class="sg">{rest}</div></details>' if rest else ""
    treasury_html = "".join(
        f'<div class="tre"><b>{html.escape(t["name"])}</b>' + "".join(f'<p><span>{html.escape(k)}</span>{html.escape(v)}</p>' for k, v in t["fields"].items()) + "</div>"
        for t in kline.get("treasuries", [])
    )
    if kl.status not in ("ok", "fallback"):
        kline_top = unavailable(kl)
    elif kl.status == "fallback":
        kline_top = f'<div class="unavail soft">上游 K 线日报今日不可用（{html.escape(kl.reason)}）。下面的分析由晨报按日线统计自生成。</div>'
    else:
        kline_top = lead + narrative
    park_overall = f'<div class="park big"><span>Park 今日判断</span><div>{md_to_html(overall)}</div></div>' if overall else ""
    kline_body = (
        kline_top + park_overall
        + f'<h3 class="sh2" id="macros">宏观资产 <small>{len(macro_html)} · 日线来自 kline.db，4 小时 / 30 分钟来自盘中源，没有的周期不画</small></h3><div class="macros">{"".join(macro_html)}</div>'
        + (f'<h3 class="sh2">美国国债</h3><div class="tres">{treasury_html}</div>' if treasury_html else "")
        + f'<h3 class="sh2" id="stocks">个股 <small>{len(stocks)} · 先按市场，再按赛道 · 涨跌 ≥3% 或 Park 写过的加亮（{hot}）</small></h3>{"".join(market_html)}'
    )

    conclusion = kline.get("conclusion") or ("K 线日报今日不可用" if kl.status not in ("ok", "fallback") else "")
    chart_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    generated = datetime.now(BJT).strftime("%H:%M")
    digest = []
    if ai.meta.get("top"):
        digest.append(("AI", ai.meta["top"], "#ai"))
    if fin.meta.get("top"):
        digest.append(("财经", fin.meta["top"], "#finance"))
    if conclusion:
        digest.append(("K 线", conclusion, "#kline"))
    digest_html = "".join(f'<a href="{href}"><span>{k}</span>{html.escape(v)}</a>' for k, v, href in digest)
    ai_count = f'{ai.meta.get("items", "")} 条' if ai.meta.get("items") else ""
    fin_count = f'{fin.meta.get("articles", "")} 篇' if fin.meta.get("articles") else ""

    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>晨报 · {date}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500&family=Noto+Sans+SC:wght@300;400;500&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#fbfbf8;--col:#ffffff;--ink:#2e2e2b;--ink2:#5b5b56;--mute:#8f8f88;--line:#ebebe4;--line2:#f3f3ee;--acc:#8b6a3e;--up:#4f8a60;--dn:#b6614f;--upf:#e3efe5;--dnf:#f5e2dd;--wick:#c2c2ba}}
*{{box-sizing:border-box}}html,body{{margin:0;background:var(--bg);color:var(--ink)}}
body{{font-family:"Noto Sans SC",-apple-system,"PingFang SC",sans-serif;font-weight:400;font-size:14px;line-height:1.75;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
.nav{{position:sticky;top:0;z-index:5;background:var(--col);border-bottom:1px solid var(--line)}}
.nav .in{{max-width:1180px;margin:0 auto;padding:10px 24px;display:flex;align-items:baseline;gap:18px;flex-wrap:wrap}}
.nav h1{{font-family:"Noto Serif SC",serif;font-weight:500;font-size:17px;margin:0;letter-spacing:.02em}}
.nav .d{{font:400 12px/1 "IBM Plex Mono",monospace;color:var(--mute)}}
.nav .links{{display:flex;gap:16px;margin-left:auto;font-size:13px;color:var(--ink2)}}.nav .links a:hover{{color:var(--acc)}}.nav .links a.home{{color:var(--mute)}}
.digest{{max-width:1180px;margin:0 auto;padding:10px 24px 0;display:grid;gap:4px;font-size:13.5px;color:var(--ink2)}}
.digest a{{display:flex;gap:10px;align-items:baseline}}.digest a span{{flex:none;width:40px;font:500 10.5px/1.8 "IBM Plex Mono",monospace;letter-spacing:.08em;color:var(--acc)}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px 80px}}
.part,h3.sh2,.macro,.stock{{scroll-margin-top:64px}}
.part{{padding:30px 0 10px;border-top:1px solid var(--line);margin-top:26px}}.part:first-of-type{{border-top:0;margin-top:0}}
.part>h2{{font-family:"Noto Serif SC",serif;font-weight:500;font-size:19px;margin:0 0 16px;display:flex;align-items:baseline;gap:12px}}
.part>h2 small{{font:400 11px/1 "IBM Plex Mono",monospace;color:var(--mute);letter-spacing:.06em}}
.prose{{font-size:14px;color:var(--ink);max-width:78ch}}.prose h2{{font-family:"Noto Serif SC",serif;font-weight:500;font-size:15px;margin:22px 0 6px;color:var(--ink)}}.prose h2:first-child{{margin-top:0}}.prose h3{{font-weight:500;font-size:14px;margin:16px 0 4px;color:var(--acc)}}
.prose ul,.prose ol{{padding-left:18px;margin:6px 0}}.prose li{{margin:5px 0;color:var(--ink2)}}.prose li strong,.prose p strong{{font-weight:500;color:var(--ink)}}.prose a{{color:var(--acc)}}.prose p{{margin:6px 0;color:var(--ink2)}}.prose blockquote{{margin:6px 0;padding-left:10px;border-left:2px solid var(--line);color:var(--mute)}}
.stat{{font-size:12px;color:var(--mute)}}
.unavail{{border-left:2px solid var(--dn);padding:8px 12px;margin:0 0 14px;font-size:13px;color:var(--ink2)}}.unavail.soft{{border-left-color:var(--acc)}}
.lead{{font-family:"Noto Serif SC",serif;font-size:16px;line-height:1.75;color:var(--ink);max-width:78ch;padding-bottom:12px;border-bottom:1px solid var(--line)}}.lead p{{margin:0}}.lead strong{{font-weight:500}}
.narrative{{margin:10px 0 0;font-size:13.5px;max-width:78ch}}.narrative summary{{cursor:pointer;color:var(--mute);font-size:12px;list-style:none}}.narrative summary::before{{content:"› ";color:var(--acc)}}.narrative[open] summary::before{{content:"⌄ "}}
.sg{{display:grid;gap:10px;margin-top:8px}}.sc{{font-size:13.5px;color:var(--ink2)}}.sc span{{display:block;font:500 10.5px/1.8 "IBM Plex Mono",monospace;letter-spacing:.08em;color:var(--acc)}}.sc p{{margin:2px 0}}.sc ol,.sc ul{{margin:2px 0;padding-left:16px}}
.park{{margin-top:8px;padding:8px 12px;border-left:2px solid var(--acc);background:#f7f3ec;font-size:13px}}.park span{{display:block;font:500 10.5px/1.8 "IBM Plex Mono",monospace;letter-spacing:.08em;color:var(--acc)}}.park p{{margin:2px 0}}.park.big{{margin:14px 0;max-width:78ch}}
h3.sh2{{font-family:"Noto Serif SC",serif;font-weight:500;font-size:16px;margin:34px 0 12px;color:var(--ink)}}h3.sh2 small{{font:400 11px/1 "IBM Plex Mono",monospace;color:var(--mute);margin-left:10px;letter-spacing:.04em}}
h4.sh{{font-family:"Noto Serif SC",serif;font-weight:500;font-size:15px;margin:28px 0 8px;color:var(--ink2);padding-bottom:6px;border-bottom:1px solid var(--line)}}h4.sh small{{font:400 11px/1 "IBM Plex Mono",monospace;color:var(--mute);margin-left:8px}}
.macros{{display:grid;gap:16px}}.macro{{background:var(--col);border:1px solid var(--line);padding:14px 16px}}
.macro header{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}.macro h4{{margin:0;font-weight:500;font-size:15px}}
.px{{font:400 13px/1 "IBM Plex Mono",monospace;color:var(--ink2)}}.chg{{font:400 12.5px/1 "IBM Plex Mono",monospace;color:var(--mute)}}.chg.up{{color:var(--up)}}.chg.dn{{color:var(--dn)}}
.tags{{margin-left:auto;display:flex;gap:4px;flex-wrap:wrap}}.tg{{font:400 11px/1 "IBM Plex Mono",monospace;padding:4px 7px;border:1px solid var(--line);border-radius:2px;color:var(--ink2)}}.tg.lean{{border-color:var(--acc);color:var(--acc)}}
.charts{{display:grid;gap:12px;margin:12px 0 8px}}.charts.n3{{grid-template-columns:repeat(3,minmax(0,1fr))}}.charts.n2{{grid-template-columns:repeat(2,minmax(0,1fr))}}.charts.n1{{grid-template-columns:1fr}}
.kc{{margin:0;min-width:0}}.kc figcaption{{font:400 10.5px/1.6 "IBM Plex Mono",monospace;color:var(--mute);display:flex;justify-content:space-between;gap:8px;letter-spacing:.04em}}
.chart{{border:1px solid var(--line2);background:var(--col);position:relative;overflow:hidden}}.chart>svg.k{{position:absolute;inset:0;width:100%;height:100%}}
.para{{margin:8px 0 0;font-size:14px;line-height:1.75;color:var(--ink2);max-width:90ch}}
.tres{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.tre{{font-size:13px;color:var(--ink2);background:var(--col);border:1px solid var(--line);padding:10px 12px}}.tre b{{display:block;font-weight:500;color:var(--ink);margin-bottom:2px}}.tre p{{margin:2px 0}}.tre p span{{font:400 10px/1.6 "IBM Plex Mono",monospace;color:var(--mute);margin-right:6px}}
.sector{{margin:12px 0 18px}}.sector h5{{font:500 11px/1.6 "IBM Plex Mono",monospace;letter-spacing:.06em;color:var(--mute);margin:0 0 8px}}.sector h5 small{{margin-left:6px;font-weight:400}}
.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
.stock{{background:var(--col);border:1px solid var(--line);padding:10px 12px 10px;min-width:0}}.stock.hot{{border-left:2px solid var(--acc)}}
.stock header{{display:flex;align-items:baseline;gap:8px;margin-bottom:8px}}.stock .sym{{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}}.stock .sym small{{font:400 10.5px/1 "IBM Plex Mono",monospace;color:var(--mute);margin-left:6px}}
.stock .l2{{font-size:12.5px;color:var(--mute);margin:8px 0 0;line-height:1.6}}.stock .l2 i{{color:var(--line)}}
svg.k{{display:block}}svg.k path.w{{stroke:var(--wick);stroke-width:.8;fill:none}}svg.k path.u{{fill:var(--upf);stroke:var(--up);stroke-width:.7}}svg.k path.d{{fill:var(--dnf);stroke:var(--dn);stroke-width:.7}}
.foot{{max-width:1180px;margin:0 auto;padding:14px 24px 40px;font-size:11.5px;color:var(--mute);border-top:1px solid var(--line)}}
@media (max-width:1000px){{.cards{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media (max-width:640px){{.charts.n3,.charts.n2,.tres,.cards{{grid-template-columns:1fr}}.nav .links{{margin-left:0;width:100%}}.wrap,.nav .in,.digest,.foot{{padding-left:14px;padding-right:14px}}}}
</style></head><body>
<div class="nav"><div class="in"><h1>晨报 · {date}</h1><span class="d">生成 {generated}</span><nav class="links"><a href="#ai">AI 日报</a><a href="#finance">财经日报</a><a href="#kline">K 线日报</a><a href="#stocks">个股</a><a class="home" href="/daily/">往期</a></nav></div></div>
<div class="digest">{digest_html}</div>
<div class="wrap">
  <section class="part" id="ai"><h2>AI 日报<small>{ai_count}</small></h2>{status_line(ai)}{f'<div class="prose">{ai.html}</div>' if ai.html else unavailable(ai)}</section>
  <section class="part" id="finance"><h2>财经日报<small>{fin_count}</small></h2>{status_line(fin)}{f'<div class="prose">{fin.html}</div>' if fin.html else unavailable(fin)}</section>
  <section class="part" id="kline"><h2>K 线日报<small>{len(macro_html)} 宏观 · {len(stocks)} 个股</small></h2>{status_line(kl)}{kline_body}</section>
</div>
<div class="foot">上游各自生成：AI 日报 08:30 · 财经日报 08:00 · K 线日报 08:20 · 晨报合成 09:00 / 09:40。个股的一句描述按日线统计生成，只描述结构，不构成任何建议。图表：TradingView Lightweight Charts，可拖动缩放。</div>
<script id="kdata" type="application/json">{chart_json}</script>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.0/dist/lightweight-charts.standalone.production.js" integrity="sha384-q1KYLSKHgBnW5tWYGGR8+6YV4/iPy31dILoF2I1OD7XiVUvHEp/TaxIQVmB0j3R2" crossorigin="anonymous"></script>
<script>
(function(){{
  var data = {{}};
  try {{ data = JSON.parse(document.getElementById('kdata').textContent || '{{}}'); }} catch (e) {{ data = {{}}; }}
  var LW = window.LightweightCharts;
  var els = document.querySelectorAll('.chart[data-key]');
  if (!LW || !els.length) return;
  var css = getComputedStyle(document.documentElement);
  var v = function(n, d) {{ return (css.getPropertyValue(n) || d).trim(); }};
  function build(el) {{
    var bars = (data[el.dataset.key] || {{}})[el.dataset.tf] || [];
    if (!bars.length) return;
    var candles = bars.map(function(b) {{ return {{ time: Math.floor(Date.parse(b[0].length === 10 ? b[0] + 'T00:00:00Z' : b[0]) / 1000), open: b[1], high: b[2], low: b[3], close: b[4] }}; }});
    var h = el.clientHeight || 150;
    var chart = LW.createChart(el, {{
      height: h, layout: {{ background: {{ type: 'solid', color: 'transparent' }}, textColor: v('--mute', '#8f8f88'), fontSize: 10, fontFamily: 'IBM Plex Mono, monospace', attributionLogo: false }},
      grid: {{ vertLines: {{ visible: false }}, horzLines: {{ color: v('--line2', '#f3f3ee') }} }},
      rightPriceScale: {{ borderVisible: false }}, timeScale: {{ borderVisible: false, timeVisible: el.dataset.tf !== 'daily', secondsVisible: false }},
      handleScroll: true, handleScale: true, crosshair: {{ mode: 0, vertLine: {{ color: v('--line', '#ebebe4'), labelBackgroundColor: v('--ink2', '#5b5b56') }}, horzLine: {{ color: v('--line', '#ebebe4'), labelBackgroundColor: v('--ink2', '#5b5b56') }} }}
    }});
    var series = chart.addSeries(LW.CandlestickSeries, {{ upColor: v('--upf', '#e3efe5'), downColor: v('--dnf', '#f5e2dd'), borderUpColor: v('--up', '#4f8a60'), borderDownColor: v('--dn', '#b6614f'), wickUpColor: v('--wick', '#c2c2ba'), wickDownColor: v('--wick', '#c2c2ba'), borderVisible: true }});
    series.setData(candles);
    var ph = el.querySelector('svg.k'); if (ph) ph.remove();
    chart.timeScale().setVisibleLogicalRange({{ from: Math.max(0, candles.length - 80), to: candles.length + 2 }});
    new ResizeObserver(function() {{ chart.applyOptions({{ width: el.clientWidth }}); }}).observe(el);
  }}
  var io = new IntersectionObserver(function(entries) {{
    entries.forEach(function(en) {{ if (en.isIntersecting) {{ io.unobserve(en.target); build(en.target); }} }});
  }}, {{ rootMargin: '800px' }});
  els.forEach(function(el) {{ io.observe(el); }});
}})();
</script>
</body></html>"""


def render_index(dates: list[str]) -> str:
    items = "".join(f'<li><a href="/daily/{d}.html">{d}</a></li>' for d in dates)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Park 晨报</title>
<style>body{{margin:0;background:#f8f8f5;color:#20211f;font-family:"Noto Sans SC",-apple-system,sans-serif}}.wrap{{max-width:720px;margin:0 auto;padding:40px 20px}}h1{{font-family:"Noto Serif SC",serif}}ul{{list-style:none;padding:0}}li{{padding:10px 0;border-bottom:1px solid #dedfd8;font-family:"IBM Plex Mono",monospace}}a{{color:inherit;text-decoration:none}}li a:hover{{text-decoration:underline}}p{{color:#65665f}}</style></head>
<body><div class="wrap"><a href="/">← park</a><h1>Park 晨报</h1><p>每个交易日一份：AI 日报、财经日报、K 线日报。This is how I start my day.</p><ul>{items}</ul></div></body></html>"""
