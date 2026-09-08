"""Candles, derived statistics and the mini SVG chart.

Daily bars come from the local kline.db; intraday bars come from the Human
K-line Review overview endpoint, cached once per day.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import config
from .config import CHART_BARS, TF_LABELS, macro_key

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def load_manifest() -> list[dict]:
    if not config.MANIFEST.exists():
        return []
    return json.loads(config.MANIFEST.read_text(encoding="utf-8")).get("instruments", [])


def load_macro_names() -> dict[str, str]:
    if yaml is None or not config.WATCHLIST_YAML.exists():
        return {}
    data = yaml.safe_load(config.WATCHLIST_YAML.read_text(encoding="utf-8"))
    return {m["id"]: m["name"] for m in data.get("macros", [])}


def load_candles(db: Path, instrument_id: str, limit: int = 130) -> list[dict]:
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select timestamp, open, high, low, close, volume from mvp_candles "
            "where instrument_id=? and timeframe='1d' order by timestamp desc limit ?",
            (instrument_id, limit),
        ).fetchall()
    finally:
        con.close()
    rows.reverse()
    return [dict(t=r[0][:10], o=r[1], h=r[2], l=r[3], c=r[4], v=r[5] or 0) for r in rows]


def ema(values: list[float], span: int) -> float | None:
    if len(values) < span:
        return None
    k = 2 / (span + 1)
    e = sum(values[:span]) / span
    for v in values[span:]:
        e = v * k + e * (1 - k)
    return e


def pct(a: float, b: float) -> float | None:
    return None if not b else round((a / b - 1) * 100, 2)


def compute_stats(candles: list[dict]) -> dict:
    if len(candles) < 2:
        return {}
    closes = [c["c"] for c in candles]
    last = candles[-1]
    n = len(closes)
    window20 = candles[-20:]
    hi20, lo20 = max(c["h"] for c in window20), min(c["l"] for c in window20)
    e20, e50 = ema(closes, 20), ema(closes, 50)
    vols = [c["v"] for c in candles]
    v5 = sum(vols[-5:]) / 5 if n >= 5 else None
    v20 = sum(vols[-20:]) / 20 if n >= 20 else None
    return {
        "as_of": last["t"],
        "close": last["c"],
        "chg1d": pct(last["c"], closes[-2]),
        "chg5d": pct(last["c"], closes[-6]) if n >= 6 else None,
        "chg20d": pct(last["c"], closes[-21]) if n >= 21 else None,
        "chg60d": pct(last["c"], closes[-61]) if n >= 61 else None,
        "ema20": round(e20, 4) if e20 else None,
        "ema50": round(e50, 4) if e50 else None,
        "vs_ema20": pct(last["c"], e20) if e20 else None,
        "vs_ema50": pct(last["c"], e50) if e50 else None,
        "pos20": round((last["c"] - lo20) / (hi20 - lo20) * 100) if hi20 > lo20 else None,
        "vol_ratio": round(v5 / v20, 2) if v5 and v20 else None,
        "bars": n,
    }


def svg_candles(candles: list[dict], width: int = 140, height: int = 40, bars: int = 40) -> str:
    """Light mini candlesticks: grey wicks, soft green/red bodies. Three paths total."""
    data = candles[-bars:]
    if not data:
        return f'<svg class="k" viewBox="0 0 {width} {height}" role="img" aria-label="无数据"></svg>'
    hi = max(c["h"] for c in data)
    lo = min(c["l"] for c in data)
    rng = (hi - lo) or 1
    pad = 2
    step = (width - pad * 2) / len(data)
    bw = max(1.0, step * 0.62)
    y = lambda v: pad + (hi - v) / rng * (height - pad * 2)  # noqa: E731
    wicks, ups, downs = [], [], []
    for i, c in enumerate(data):
        x = pad + i * step + step / 2
        top, bot = y(max(c["o"], c["c"])), y(min(c["o"], c["c"]))
        wicks.append(f"M{x:.1f} {y(c['h']):.1f}V{y(c['l']):.1f}")
        body = f"M{x - bw / 2:.1f} {top:.1f}h{bw:.1f}v{max(0.8, bot - top):.1f}h-{bw:.1f}z"
        (ups if c["c"] >= c["o"] else downs).append(body)
    return (
        f'<svg class="k" viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="最近 {len(data)} 根日线">'
        f'<path class="w" d="{"".join(wicks)}"/><path class="u" d="{"".join(ups)}"/><path class="d" d="{"".join(downs)}"/></svg>'
    )


def should_expand(stats: dict, has_note: bool, threshold: float = 3.0) -> bool:
    chg = stats.get("chg1d")
    return has_note or (chg is not None and abs(chg) >= threshold)


def load_review_overview(date: str, url: str = config.REVIEW_OVERVIEW_URL) -> dict:
    """Fetch the 16-asset daily/4h/30m candle bundle once per day and cache it."""
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = config.CACHE_DIR / f"{date}-overview.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(url, timeout=90) as resp:
            raw = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[overview] unavailable: {exc}\n")
        return {}
    compact = {"cutoff_at": raw.get("cutoff_at"), "assets": {}}
    for asset in raw.get("assets", []):
        key = macro_key(asset.get("display_name", ""), asset.get("ticker", ""))
        if not key:
            continue
        tfs = {}
        for tf in asset.get("timeframes", []):
            name = tf.get("timeframe")
            if name not in TF_LABELS:
                continue
            bars = [
                [c["timestamp"], c["open"], c["high"], c["low"], c["close"], c.get("volume") or 0]
                for c in tf.get("candles", [])[-CHART_BARS:]
                if c.get("close") is not None
            ]
            tfs[name] = {"status": tf.get("status"), "as_of": (tf.get("as_of") or "")[:16].replace("T", " "), "bars": bars}
        compact["assets"][key] = {"name": asset.get("display_name"), "ticker": asset.get("ticker"), "timeframes": tfs}
    cache_path.write_text(json.dumps(compact, ensure_ascii=False), encoding="utf-8")
    return compact


def bars_to_candles(bars: list[list]) -> list[dict]:
    return [dict(t=str(b[0])[:10], o=b[1], h=b[2], l=b[3], c=b[4], v=b[5]) for b in bars]


def tf_stats(overview: dict, key: str) -> dict[str, dict]:
    asset = overview.get("assets", {}).get(key, {})
    return {tf: compute_stats(bars_to_candles(v["bars"])) for tf, v in asset.get("timeframes", {}).items() if v.get("bars")}


def build_universe(manifest: list[dict], db: Path) -> tuple[dict[str, dict], list[dict]]:
    macros: dict[str, dict] = {}
    stocks: list[dict] = []
    for inst in manifest:
        iid = inst["instrument_id"]
        entry = {
            "id": iid,
            "name": inst.get("display_name") or iid,
            "symbol": inst.get("display_symbol") or iid.split(".")[-1],
            "asset_class": inst.get("asset_class"),
            "memberships": inst.get("metadata", {}).get("registry_memberships", []),
            "candles": load_candles(db, iid),
        }
        entry["stats"] = compute_stats(entry["candles"])
        if iid.startswith("WATCH.CROSS."):
            macros[iid.split(".")[-1]] = entry
        else:
            stocks.append(entry)
    return macros, stocks
