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
