"""Feishu message and GitHub alert issue."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from . import config
from .sources import Section


def feishu_send(env_path: Path, text: str) -> dict:
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    url, secret = env.get("FEISHU_WEBHOOK_URL", ""), env.get("FEISHU_WEBHOOK_SECRET", "")
    if not url:
        raise RuntimeError("FEISHU_WEBHOOK_URL missing")
    ts = str(int(time.time()))
    body: dict = {"msg_type": "text", "content": {"text": text}}
    if secret:
        digest = hmac.new(f"{ts}\n{secret}".encode(), b"", hashlib.sha256).digest()
        body.update({"timestamp": ts, "sign": base64.b64encode(digest).decode()})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def open_alert_issue(date: str, failed: list[Section], dry_run: bool) -> str:
    title = f"晨报 {date} · {'、'.join(s.title for s in failed)} 不可用"
    body = "\n".join(f"- {s.title}: {s.reason or '无产出'}" for s in failed) + f"\n\n页面：{config.SITE}/daily/{date}.html"
    if dry_run:
        return f"[dry-run] would open issue: {title}"
    existing = subprocess.run(["gh", "issue", "list", "--state", "open", "--search", f'"{title}" in:title', "--json", "number", "--jq", "length"], capture_output=True, text=True, cwd=config.REPO)
    if existing.returncode == 0 and existing.stdout.strip() not in ("", "0"):
        return "issue already open"
    res = subprocess.run(["gh", "issue", "create", "--title", title, "--body", body, "--label", "morning-down"], capture_output=True, text=True, cwd=config.REPO)
    return res.stdout.strip() or res.stderr.strip()
