#!/usr/bin/env python3
"""How many tokens did the four daily pipelines actually spend?

Each of the four Codex call sites (AI daily, finance daily, K-line daily,
this brief's own stock/macro notes) now appends one JSON line per call to its
own file under ~/park-data/llm-usage/. This just reads those four files and
totals them, optionally filtered to one day.

Usage:
    ops/token_usage.py                  # everything ever logged
    ops/token_usage.py --date 2026-09-11
    ops/token_usage.py --since 2026-09-05

Two of the four logs (ai-daily, morning-brief) only have Codex's rounded
"tokens used" total (a single `tokens` field — no input/cached/output split,
because those two call sites never asked Codex for --json). The other two
(finance-daily, kline-daily) have the full split from the --json event
stream. The report shows both shapes without pretending they are the same
thing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

USAGE_DIR = Path.home() / "park-data" / "llm-usage"
LOGS = {
    "ai-daily": USAGE_DIR / "ai-daily.jsonl",
    "finance-daily": USAGE_DIR / "finance-daily.jsonl",
    "kline-daily": USAGE_DIR / "kline-daily.jsonl",
    "morning-brief": USAGE_DIR / "morning-brief.jsonl",
}


def _date_of(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return ts[:10]


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def billed_tokens(row: dict) -> int:
    """The number that actually counts against usage limits.

    Cached input tokens are steeply discounted (often free); showing raw
    input_tokens as "cost" overstates it by whatever fraction was cached.
    """
    if "tokens" in row:
        return int(row.get("tokens") or 0)
    inp = int(row.get("input_tokens") or 0)
    cached = int(row.get("cached_input_tokens") or 0)
    out = int(row.get("output_tokens") or 0)
    return max(0, inp - cached) + out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="Only this day (YYYY-MM-DD, by each row's own timestamp).")
    parser.add_argument("--since", help="This day onward (YYYY-MM-DD).")
    args = parser.parse_args()

    grand_total = 0
    grand_calls = 0
    print(f"{'pipeline':<16} {'calls':>6} {'billed tokens':>14} {'raw input':>12} {'cached':>10} {'output':>10}")
    for name, path in LOGS.items():
        rows = load_rows(path)
        if args.date:
            rows = [r for r in rows if _date_of(r.get("ts", "")) == args.date]
        elif args.since:
            rows = [r for r in rows if _date_of(r.get("ts", "")) >= args.since]
        billed = sum(billed_tokens(r) for r in rows)
        raw_in = sum(int(r.get("input_tokens") or 0) for r in rows)
        cached = sum(int(r.get("cached_input_tokens") or 0) for r in rows)
        out = sum(int(r.get("output_tokens") or 0) for r in rows)
        grand_total += billed
        grand_calls += len(rows)
        raw_in_s = f"{raw_in:,}" if raw_in else "—"
        cached_s = f"{cached:,}" if cached else "—"
        out_s = f"{out:,}" if out else "—"
        print(f"{name:<16} {len(rows):>6} {billed:>14,} {raw_in_s:>12} {cached_s:>10} {out_s:>10}")
    print("-" * 72)
    print(f"{'total':<16} {grand_calls:>6} {grand_total:>14,}")
    if not any(load_rows(p) for p in LOGS.values()):
        print("\n(no rows logged yet in any of the four files — this only covers calls made after the usage-logging patch landed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
