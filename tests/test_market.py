"""Derived statistics and the mini chart."""
from morning import market


def test_compute_stats_and_expand_rule(candles):
    stats = market.compute_stats(candles())
    assert stats["bars"] == 70
    assert stats["ema50"] is not None and stats["chg60d"] is not None
    assert 0 <= stats["pos20"] <= 100
    assert market.should_expand({"chg1d": 3.4}, False) is True
    assert market.should_expand({"chg1d": 1.0}, False) is False
    assert market.should_expand({"chg1d": None}, True) is True
    assert market.compute_stats([]) == {}


def test_svg_candles_draws_requested_bars(candles):
    svg = market.svg_candles(candles(), bars=30)
    assert svg.count("<path") == 3
    assert svg.count("M") == 60  # 30 wicks + 30 bodies
    assert 'class="k"' in svg
    assert "无数据" in market.svg_candles([])


def test_series_lag_is_measured_against_the_asset_own_daily_bar():
    """A holiday weekend must not look like a broken feed."""
    # Tuesday after Labor Day: 4h ends Friday, daily has the Sunday session.
    assert market.series_lag_days("2026-09-04T20:00", "2026-09-07") == 3
    assert 3 <= market.STALE_AFTER_DAYS
    # A series that genuinely stopped two weeks ago.
    assert market.series_lag_days("2026-08-24T17:00", "2026-09-07") == 14
    assert 14 > market.STALE_AFTER_DAYS
    # Same session, and unusable inputs.
    assert market.series_lag_days("2026-09-07T14:00", "2026-09-07") == 0
    assert market.series_lag_days("", "2026-09-07") is None
    assert market.series_lag_days("2026-09-07", "") is None
