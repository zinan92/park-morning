from morning import market, render
from morning.sources import Section


def _entry(iid, name, symbol, market_code, sector, chg=1.0, n=90):
    candles = [dict(t=f"2026-06-{(i % 28) + 1:02d}", o=10 + i * 0.1, h=10.5 + i * 0.1, l=9.5 + i * 0.1, c=10.2 + i * 0.1, v=100) for i in range(n)]
    return {
        "id": iid, "name": name, "symbol": symbol, "asset_class": "x", "market": market_code,
        "memberships": [{"macro_id": "ai_capex", "sector_name": sector}],
        "candles": candles, "stats": {"close": candles[-1]["c"], "chg1d": chg, "as_of": "2026-09-09"},
    }


def _page(macros, stocks, overview=None):
    ok = Section("x", "x", status="ok", html="<p>x</p>")
    return render.render_page("2026-09-10", ok, ok, ok, {"summary": {}, "assets": [], "treasuries": []}, macros, stocks, {}, {}, {}, overview or {}, {})


def test_macro_chart_is_keyed_by_macro_key_not_ticker_symbol():
    """GOLD's kline.db symbol is GC=F; the chart payload and the slot must agree on GOLD."""
    gold = _entry("WATCH.CROSS.GOLD", "微黄金期货", "GC=F", "US", "-")
    overview = {"assets": {"GOLD": {"name": "黄金", "timeframes": {"four_hour": {"bars": [["2026-09-09T20:00", 1, 2, 0.5, 1.5, 0]], "as_of": "2026-09-09 20:00"}}}}}
    page = _page({"GOLD": gold}, [], overview)
    assert 'data-key="GOLD" data-tf="daily"' in page
    assert 'data-key="GOLD" data-tf="four_hour"' in page
    assert 'data-key="GC=F"' not in page
    # daily bars come from kline.db even though the review server has no daily series
    assert '"GOLD":{"daily":[["2026-06-' in page


def test_stocks_are_grouped_by_market_before_sector():
    stocks = [
        _entry("WATCH.US.NVDA", "英伟达", "NVDA", "US", "算力"),
        _entry("WATCH.CN.A.600900", "长江电力", "600900", "CN", "电力"),
        _entry("WATCH.HK.0700", "腾讯", "0700", "HK", "互联网"),
    ]
    page = _page({}, stocks)
    a, hk, us = page.index(">A 股<"), page.index(">港股<"), page.index(">美股<")
    assert a < hk < us
    assert page.index("长江电力") < page.index("腾讯") < page.index("英伟达")
    assert page.count('class="chart" data-key="WATCH.') == 3
    assert 'data-key="WATCH.CN.A.600900" data-tf="daily" style="height:150px"' in page
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in page  # cards, not a right-hand thumbnail


def test_fetch_overview_refreshes_first_then_falls_back(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def read(self): return self.body

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if "refresh=true" in url:
            raise TimeoutError("slow")
        return Resp(b'{"cutoff_at": "x", "assets": []}')

    monkeypatch.setattr(market.urllib.request, "urlopen", fake_urlopen)
    out = market.fetch_overview("http://h/api/overview", refresh_timeout=5)
    assert out == {"cutoff_at": "x", "assets": []}
    assert calls[0] == ("http://h/api/overview?refresh=true", 5)
    assert calls[1][0] == "http://h/api/overview"
