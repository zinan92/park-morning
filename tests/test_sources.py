"""Upstream parsing: what the brief keeps, what it drops, what it says when a file is absent."""
from morning import config, render, sources

from conftest import KLINE_MD


def test_parse_kline_md_splits_summary_and_assets():
    parsed = sources.parse_kline_md(KLINE_MD)
    assert parsed["conclusion"].startswith("等待")
    assert "## 世界模型" in parsed["summary_md"]
    assert "共有 16 个资产" not in parsed["summary_md"]
    assert [a["key"] for a in parsed["assets"]] == ["DXY", "GOLD"]
    dxy = parsed["assets"][0]
    assert dxy["ticker"] == "UUP" and dxy["as_of"] == "2026-09-04"
    assert dxy["fields"]["位置"] == "日线处于高位。"  # duplicated label prefix stripped
    assert "snapshots" not in str(dxy["fields"])


def test_macro_key_matches_by_keyword():
    assert config.macro_key("上证红利", "") == "DIVIDEND"
    assert config.macro_key("上证指数", "") == "SHCOMP"
    assert config.macro_key("中证红利", "000015.SH") == "DIVIDEND"
    assert config.macro_key("美股红利 ETF（SCHD）", "SCHD") == "SCHD"
    assert config.macro_key("纳斯达克 100 ETF（QQQ）", "QQQ") == "NDX"
    assert config.macro_key("某公司", "XYZ") is None


def test_finance_ops_sections_are_stripped():
    body = (
        "# 财经日报 | 2026-09-08\n\n## Source Status\n- cls_telegraph: 正常\n\n"
        "Processing Status:\n- Article scoring: 正常\n\n---\n\n"
        "🎯 Daily Trader Brief — 2026-09-08 00:01 UTC\n覆盖窗口：past 24h\n\n"
        "## 今日交易地图\n- 黄金：偏多\n\n## Source Health\n- ok\n"
    )
    cleaned = sources.clean_finance_md(body)
    assert "今日交易地图" in cleaned
    for noise in ("Source Status", "Source Health", "Processing Status", "Daily Trader Brief", "覆盖窗口"):
        assert noise not in cleaned


def test_park_notes_are_keyed_by_heading(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PARK_DIR", tmp_path)
    (tmp_path / "2026-09-08.md").write_text("## 总\n今天等。\n\n## NVDA\n高位放量，不追。\n## EMPTY\n", encoding="utf-8")
    assert sources.load_park_notes("2026-09-08") == {"总": "今天等。", "NVDA": "高位放量，不追。"}


def test_missing_inputs_become_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AI_DIR", tmp_path)
    monkeypatch.setattr(config, "FIN_DIR", tmp_path)
    monkeypatch.setattr(config, "KL_DIR", tmp_path)
    (tmp_path / "2026-09-07-kline-daily-newsletter-unavailable.md").write_text(
        "运行阶段：delivery_publish\n失败原因：OSError\n", encoding="utf-8"
    )
    ai = sources.load_ai("2026-09-07")
    kl, parsed = sources.load_kline("2026-09-07")
    assert ai.status == "missing" and "26-09-07.md" in ai.reason
    assert kl.status == "unavailable" and "delivery_publish" in kl.reason and "OSError" in kl.reason
    assert parsed["assets"] == []
    page = render.render_page("2026-09-07", ai, sources.load_finance("2026-09-07"), kl, parsed, {}, [], {}, {}, {})
    assert page.count("今日不可用") >= 3
    assert "不用上一期冒充今天" in page
