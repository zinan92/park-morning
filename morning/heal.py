"""Re-run an upstream daily that did not produce today's file.

Each upstream runs once in the morning and nobody retries it. Over the last
fourteen days that cost the brief a column on nine of them, and every manual
retry succeeded on the first attempt. This module makes that retry automatic:
at most one attempt per section per day, skipped while the upstream is still
running, and recorded in a receipt next to the other caches.

The commands are the ones documented in ../contracts/. Feishu delivery stays
off in every one of them; the brief is the only thing that talks to Feishu.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

from . import config
from .config import BJT

HOME = str(config.HOME)

HEALERS: dict[str, dict] = {
    "ai": {
        "label": "AI 日报",
        "cmd": ["/bin/bash", f"{HOME}/work/input-to-park/push-digest.sh"],
        "cwd": f"{HOME}/work/input-to-park",
        "busy": "push-digest.sh|build-digest.py|summarize.py",
        "timeout": 900,
        "env": {},
    },
    "finance": {
        "label": "财经日报",
        "cmd": [f"{HOME}/work/trading-co/park-intel-production/.venv/bin/python",
                "scripts/publish_finance_daily_newsletter.py"],
        "cwd": f"{HOME}/work/trading-co/park-intel-production",
        "busy": "publish_finance_daily_newsletter",
        "timeout": 900,
        "env": {"PYTHONPATH": ".", "PARK_INTEL_SKIP_FEISHU": "1"},
    },
    "kline": {
        "label": "K 线日报",
        "cmd": ["/bin/launchctl", "kickstart", f"gui/{os.getuid()}/com.park.market-regime.kline-newsletter"],
        "cwd": HOME,
        "busy": "run_market_regime_daily_delivery",
        "timeout": 120,   # kickstart returns immediately; the job keeps running
        "env": {},
        "async": True,
    },
}


def is_busy(pattern: str) -> bool:
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def heal(keys: list[str], date: str, *, dry_run: bool = False) -> dict[str, str]:
    """Attempt one re-run per named section. Returns {key: outcome}."""
    if not keys:
        return {}
    receipt_path = config.CACHE_DIR / f"{date}-heal.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    out: dict[str, str] = {}
    for key in keys:
        spec = HEALERS.get(key)
        if spec is None:
            out[key] = "no healer"
        elif key in receipt:
            out[key] = f"already attempted at {receipt[key].get('at', '?')}"
        elif is_busy(spec["busy"]):
            out[key] = "upstream still running, left alone"
        elif dry_run:
            out[key] = "would run " + " ".join(spec["cmd"])
        else:
            started = datetime.now(BJT)
            try:
                proc = subprocess.run(
                    spec["cmd"], cwd=spec["cwd"], capture_output=True, text=True,
                    timeout=spec["timeout"], env={**os.environ, **spec["env"]},
                )
                seconds = round((datetime.now(BJT) - started).total_seconds())
                out[key] = f"exit {proc.returncode} in {seconds}s" + (" (async)" if spec.get("async") else "")
            except subprocess.TimeoutExpired:
                out[key] = f"timed out after {spec['timeout']}s"
            except OSError as exc:
                out[key] = f"could not start: {exc}"
            receipt[key] = {"at": started.isoformat(timespec="seconds"), "outcome": out[key]}
    if receipt and not dry_run:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def wait_for(keys: list[str], seconds: int = 420) -> None:
    """Give asynchronous healers (launchctl kickstart) time to finish."""
    import time

    patterns = [HEALERS[k]["busy"] for k in keys if HEALERS.get(k, {}).get("async")]
    deadline = time.time() + seconds
    while patterns and time.time() < deadline:
        if not any(is_busy(p) for p in patterns):
            return
        time.sleep(10)
