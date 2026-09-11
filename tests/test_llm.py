"""Provider fallback, batching, caching, and the guard against advice language."""
from pathlib import Path

from morning import config, llm, market


def test_extract_json_and_sanitize():
    assert llm.extract_json('前言 {"a": "x"} 后语') == {"a": "x"}
    assert llm.extract_json("no json") == {}
    assert llm.sanitize_note("“价格在 20 日区间上沿，量能放大。”") == "价格在 20 日区间上沿，量能放大。"
    assert llm.sanitize_note("建议买入") == ""


def test_provider_order_and_availability(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_KEY", Path("/nonexistent"))
    monkeypatch.setattr(llm, "CODEX_BIN", Path("/nonexistent"))
    assert llm.LLM("auto").providers == []
    assert llm.LLM("auto").active == "none"

    monkeypatch.setattr(llm, "CODEX_BIN", Path("/bin/sh"))
    engine = llm.LLM("auto")
    assert engine.providers == ["codex"]
    monkeypatch.setattr(llm, "codex_call", lambda messages, model, timeout=0, **kw: '{"WATCH.X": "20 日区间上沿，量能放大。"}')
    text, provider = engine.complete([{"role": "user", "content": "x"}])
    assert provider == "codex" and "WATCH.X" in text and engine.calls["codex"] == 1


def test_rule_note_fills_the_gap(candles):
    stats = market.compute_stats(candles())
    note = llm.rule_note(stats)
    assert note.endswith("。") and "20 日" in note
    stocks = [{"id": "a", "stats": stats}, {"id": "b", "stats": stats}, {"id": "c", "stats": {}}]
    notes, fallback = llm.fill_missing_notes(stocks, {"a": "模型写的"})
    assert notes["a"] == "模型写的" and notes["b"] == note and notes.get("c", "") == ""
    assert fallback == 1


def test_annotate_stocks_batches_and_caches(tmp_path, monkeypatch, candles):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "DEEPSEEK_KEY", Path("/nonexistent"))
    monkeypatch.setattr(llm, "CODEX_BIN", Path("/bin/sh"))
    stats = market.compute_stats(candles())
    stocks = [{"id": f"WATCH.S{i}", "name": f"s{i}", "symbol": f"S{i}", "stats": stats} for i in range(4)]
    seen = []

    def fake_codex(messages, model, timeout=0, **kw):
        ids = [s for s in ("WATCH.S0", "WATCH.S1", "WATCH.S2", "WATCH.S3") if s in messages[-1]["content"]]
        seen.append(len(ids))
        return "{" + ",".join(f'"{i}": "{i} 在 20 日区间中部。"' for i in ids) + "}"

    monkeypatch.setattr(llm, "codex_call", fake_codex)
    notes = llm.annotate_stocks(stocks, "2026-09-08", llm.LLM("codex"), batch=3)
    assert seen == [3, 1] and all(notes[s["id"]] for s in stocks)

    seen.clear()
    assert llm.annotate_stocks(stocks, "2026-09-08", llm.LLM("codex"), batch=3) == notes
    assert seen == []


def test_macro_fallback_builds_asset_blocks(tmp_path, monkeypatch, candles):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "DEEPSEEK_KEY", Path("/nonexistent"))
    monkeypatch.setattr(llm, "CODEX_BIN", Path("/bin/sh"))
    stats = market.compute_stats(candles())
    macros = {"GOLD": {"name": "黄金", "symbol": "GOLD", "stats": stats}, "SPX": {"name": "标普", "symbol": "SPX", "stats": stats}}
    monkeypatch.setattr(
        llm, "codex_call",
        lambda m, model, timeout=0, **kw: '{"conclusion": "等待 · 分化", "assets": {"GOLD": {"位置": "高位", "结构": "趋势偏强", "赔率": "未形成", "综合结论": "偏强"}}}',
    )
    assets, conclusion, provider = llm.macro_fallback(macros, "2026-09-08", llm.LLM("codex"))
    assert provider == "codex" and conclusion.startswith("等待")
    assert [a["key"] for a in assets] == ["GOLD"] and assets[0]["fields"]["结构"] == "趋势偏强"
