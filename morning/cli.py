"""Command line entry point: build one edition, publish, deliver."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from . import config, delivery, market, render, sources
from . import llm as llm_mod
from .config import BJT
from .text import bjt_today


GENERATED_STAMP = re.compile(r"生成 \d\d:\d\d")


def write_if_changed(path: Path, html: str) -> bool:
    """Write only when the page really differs.

    Every run stamps a new generation time, so a byte comparison would make
    the 09:00 and 09:40 runs each commit the same ~700KB page to the site
    repository. Compare with the stamp removed instead.
    """
    if path.exists():
        strip = lambda text: GENERATED_STAMP.sub("", text)  # noqa: E731
        if strip(path.read_text(encoding="utf-8")) == strip(html):
            return False
    path.write_text(html, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=bjt_today())
    ap.add_argument("--no-ai", action="store_true", help="skip DeepSeek stock notes (use cache only)")
    ap.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"), help="DeepSeek model")
    ap.add_argument("--llm", choices=["auto", "deepseek", "codex", "none"], default=os.environ.get("MORNING_LLM", "codex"))
    ap.add_argument("--codex-model", default=os.environ.get("MORNING_CODEX_MODEL") or None)
    ap.add_argument("--batch", type=int, default=10, help="stocks per LLM call")
    ap.add_argument("--send-feishu", action="store_true")
    ap.add_argument("--alert", action="store_true", help="open a GitHub issue when a section is unavailable")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    date = args.date

    ai, fin = sources.load_ai(date), sources.load_finance(date)
    kl, kline = sources.load_kline(date)
    notes = sources.load_park_notes(date)
    manifest = market.load_manifest()
    macros, stocks = market.build_universe(manifest, config.KLINE_DB)
    llm = None if (args.no_ai or args.dry_run or args.llm == "none") else llm_mod.LLM(args.llm, args.model, args.codex_model)
    fallback_provider = "none"
    if kl.status != "ok" and llm is not None:
        fb_assets, fb_conclusion, fallback_provider = llm_mod.macro_fallback(macros, date, llm)
        if fb_assets:
            kline["assets"], kline["conclusion"] = fb_assets, fb_conclusion
            kl.status = "fallback"
            kl.reason = f"上游不可用（{kl.reason or '无产出'}）；宏观资产分析由晨报按日线统计自生成（{fallback_provider}）"
    model_notes = llm_mod.annotate_stocks(stocks, date, llm, batch=args.batch)
    ai_notes, fallback_count = llm_mod.fill_missing_notes(stocks, model_notes)
    overview = {} if args.dry_run else market.load_review_overview(date)
    analysis_by_key = {a["key"]: a for a in kline["assets"] if a.get("key")}
    condensed, condensed_provider = llm_mod.condense_macros(macros, analysis_by_key, overview, date, llm)
    page = render.render_page(date, ai, fin, kl, kline, macros, stocks, notes, ai_notes, market.load_macro_names(), overview, condensed)

    status = {
        "date": date,
        "generated_at": datetime.now(BJT).isoformat(timespec="seconds"),
        "sections": {s.key: {"status": s.status, "reason": s.reason, **s.meta} for s in (ai, fin, kl)},
        "kline": {"macro_assets": len(macros), "stocks": len(stocks), "model_notes": sum(1 for v in model_notes.values() if v), "rule_notes": fallback_count, "park_notes": len(notes), "macro_fallback": fallback_provider, "condensed": len(condensed), "condensed_provider": condensed_provider, "overview_assets": len(overview.get("assets", {}))},
        "llm": {"active": llm.active if llm else "none", "calls": llm.calls if llm else {}, "errors": llm.errors[:10] if llm else []},
    }
    if args.dry_run:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.OUT_DIR / "status").mkdir(exist_ok=True)
    written = write_if_changed(config.OUT_DIR / f"{date}.html", page)
    status["rewritten"] = written
    (config.OUT_DIR / "status" / f"{date}.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        config.VAULT_HTML_DIR.mkdir(parents=True, exist_ok=True)
        (config.VAULT_HTML_DIR / f"{date}.html").write_text(page, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"[vault] could not save html copy: {exc}\n")
    dates = sorted((p.stem for p in config.OUT_DIR.glob("????-??-??.html")), reverse=True)
    (config.OUT_DIR / "index.html").write_text(render.render_index(dates), encoding="utf-8")
    (config.OUT_DIR / "latest.html").write_text(f'<meta http-equiv="refresh" content="0; url=/daily/{dates[0]}.html">', encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))

    failed = [s for s in (ai, fin, kl) if s.status not in ("ok", "fallback")]
    if args.alert and failed:
        print(delivery.open_alert_issue(date, failed, dry_run=False))
    if args.send_feishu:
        receipt = config.CACHE_DIR / f"{date}-feishu.json"
        statuses = {s.key: s.status for s in (ai, fin, kl)}
        previous = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else None
        improved = bool(previous) and any(statuses[k] == "ok" and previous.get("statuses", {}).get(k) not in (None, "ok") for k in statuses)
        if previous and not improved:
            print("feishu: already sent, nothing new")
        else:
            mark = lambda sec: "✓" if sec.status == "ok" else ("△ 自生成" if sec.status == "fallback" else "✗ " + sec.reason)  # noqa: E731
            head = f"Park 晨报 · {date}" + (" · 已补齐" if improved else "")
            lines = [head, f"01 AI 日报 {mark(ai)}", f"02 财经日报 {mark(fin)}", f"03 K 线日报 {mark(kl)}"]
            if kline.get("conclusion"):
                lines.append(f"今日结论：{kline['conclusion']}")
            lines.append(f"{config.SITE}/daily/{date}.html")
            result = delivery.feishu_send(config.FEISHU_ENV, "\n".join(lines))
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps({"sent_at": datetime.now(BJT).isoformat(), "statuses": statuses, "follow_up": improved, "result": result}, ensure_ascii=False), encoding="utf-8")
            print(f"feishu: {'follow-up ' if improved else ''}{result}")
    return 0
