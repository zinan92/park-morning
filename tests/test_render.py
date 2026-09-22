from morning import market, render
from morning.sources import Section


def _entry(iid, name, symbol, market_code, sector, chg=1.0, n=90):
    candles = [dict(t=f"2026-06-{(i % 28) + 1:02d}", o=10 + i * 0.1, h=10.5 + i * 0.1, l=9.5 + i * 0.1, c=10.2 + i * 0.1, v=100) for i in range(n)]
    return {
        "id": iid, "name": name, "symbol": symbol, "asset_class": "x", "market": market_code,
        "memberships": [{"macro_id": "ai_capex", "sector_name": sector}],
        "candles": candles, "stats": {"close": candles[-1]["c"], "chg1d": chg, "as_of": "2026-09-09"},
    }


def _page(macros, stocks):
    ok = Section("x", "x", status="ok", html="<p>x</p>")
    return render.render_page("2026-09-10", ok, ok, ok, {"summary": {}, "assets": [], "treasuries": []}, macros, stocks, {}, {}, {}, {})


def test_macro_chart_is_keyed_by_macro_key_not_ticker_symbol():
    """GOLD's kline.db symbol is GC=F; the chart payload and the slot must agree on GOLD."""
    gold = _entry("WATCH.CROSS.GOLD", "微黄金期货", "GC=F", "US", "-")
    page = _page({"GOLD": gold}, [])
    assert 'data-key="GOLD" data-tf="daily"' in page
    assert 'data-key="GC=F"' not in page
    assert '"GOLD":{"daily":[["2026-06-' in page


def test_every_asset_gets_exactly_one_daily_chart():
    """2026-09-22, Park: one format for everything, daily only."""
    gold = _entry("WATCH.CROSS.GOLD", "微黄金期货", "GC=F", "US", "-")
    nvda = _entry("WATCH.US.NVDA", "英伟达", "NVDA", "US", "算力")
    page = _page({"GOLD": gold}, [nvda])
    # no intraday slots anywhere
    assert 'data-tf="four_hour"' not in page and 'data-tf="thirty_minute"' not in page
    assert page.count('data-tf="daily"') == 2
    # macro and stock render the same card class, so they look identical
    assert page.count('<article class="asset') == 2
    assert 'class="macro"' not in page and 'class="stock' not in page


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
    assert 'data-key="WATCH.CN.A.600900" data-tf="daily"' in page
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in page  # cards, not a right-hand thumbnail
