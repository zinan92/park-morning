"""End to end: one edition is written, and Feishu only hears about real changes."""
import json

from morning import cli, config, delivery


def test_feishu_follow_up_only_when_a_section_recovers(tmp_path, monkeypatch):
    for name in ("CACHE_DIR", "AI_DIR", "FIN_DIR", "KL_DIR"):
        monkeypatch.setattr(config, name, tmp_path)
    monkeypatch.setattr(config, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "VAULT_HTML_DIR", tmp_path / "vault")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "none.json")
    monkeypatch.setattr(config, "KLINE_DB", tmp_path / "none.db")
    sent = []
    monkeypatch.setattr(delivery, "feishu_send", lambda env, text: sent.append(text) or {"ok": 1})

    # Nothing upstream yet: one message that says so.
    cli.main(["--date", "2026-09-09", "--no-ai", "--send-feishu"])
    assert len(sent) == 1 and "已补齐" not in sent[0]
    assert (tmp_path / "out" / "2026-09-09.html").exists()

    # Still nothing: silence.
    cli.main(["--date", "2026-09-09", "--no-ai", "--send-feishu"])
    assert len(sent) == 1

    # The AI daily lands: one follow-up.
    (tmp_path / "26-09-09.md").write_text("# AI Daily\n## 快讯\n- **a** | [t](http://x)\n", encoding="utf-8")
    cli.main(["--date", "2026-09-09", "--no-ai", "--send-feishu"])
    assert len(sent) == 2 and "已补齐" in sent[1] and "01 AI 日报 ✓" in sent[1]


def test_edition_is_also_saved_to_the_vault(tmp_path, monkeypatch):
    for name in ("CACHE_DIR", "AI_DIR", "FIN_DIR", "KL_DIR"):
        monkeypatch.setattr(config, name, tmp_path)
    monkeypatch.setattr(config, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "VAULT_HTML_DIR", tmp_path / "vault")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "none.json")
    monkeypatch.setattr(config, "KLINE_DB", tmp_path / "none.db")
    cli.main(["--date", "2026-09-10", "--no-ai"])
    assert (tmp_path / "vault" / "2026-09-10.html").exists()
    assert (tmp_path / "out" / "status" / "2026-09-10.json").exists()


def test_page_is_not_rewritten_when_only_the_timestamp_moves(tmp_path, monkeypatch):
    """Two runs a day must not commit the same 700KB page twice."""
    for name in ("CACHE_DIR", "AI_DIR", "FIN_DIR", "KL_DIR"):
        monkeypatch.setattr(config, name, tmp_path)
    monkeypatch.setattr(config, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "VAULT_HTML_DIR", tmp_path / "vault")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "none.json")
    monkeypatch.setattr(config, "KLINE_DB", tmp_path / "none.db")
    page = tmp_path / "out" / "2026-09-11.html"

    cli.main(["--date", "2026-09-11", "--no-ai"])
    first = page.stat().st_mtime_ns
    assert json.loads((tmp_path / "out" / "status" / "2026-09-11.json").read_text())["rewritten"] is True

    cli.main(["--date", "2026-09-11", "--no-ai"])
    assert page.stat().st_mtime_ns == first
    assert json.loads((tmp_path / "out" / "status" / "2026-09-11.json").read_text())["rewritten"] is False

    # real content change still writes
    (tmp_path / "26-09-11.md").write_text("# AI Daily\n## 快讯\n- **a** | [t](http://x)\n", encoding="utf-8")
    cli.main(["--date", "2026-09-11", "--no-ai"])
    assert page.stat().st_mtime_ns != first
