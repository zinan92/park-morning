"""Model layer: DeepSeek first, Codex CLI second, deterministic rules last.

A provider that fails on billing or is missing is marked dead for the rest of
the run instead of being retried per item.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
import time
import urllib.request
from pathlib import Path

from . import config, market
from .config import MACRO_ORDER, TF_LABELS


FORBIDDEN = ("买", "卖", "建议", "推荐", "加仓", "减仓", "抄底", "止损", "目标价")


STAT_KEYS = ("as_of", "close", "chg1d", "chg5d", "chg20d", "chg60d", "vs_ema20", "vs_ema50", "pos20", "vol_ratio")


def stats_facts(stats: dict) -> dict:
    return {k: stats.get(k) for k in STAT_KEYS}


def batch_prompt(items: list[dict]) -> list[dict]:
    """items: [{id, name, symbol, stats}] → one JSON object {id: sentence}."""
    payload = {it["id"]: {"name": it["name"], "symbol": it["symbol"], **stats_facts(it["stats"])} for it in items}
    return [
        {"role": "system", "content": "你是 K 线结构描述员。对每个标的只用一句中文描述价格所处位置、结构和动能，不超过 40 个字，不使用任何买卖、建议、目标价、止损之类的词，不预测方向。只输出一个 JSON 对象，键为标的 id，值为那一句，不要其它文字。"},
        {"role": "user", "content": "字段含义：chg 为收益率百分比，vs_ema 为相对均线百分比，pos20 为 20 日区间位置百分位，vol_ratio 为 5 日/20 日量比。\n" + json.dumps(payload, ensure_ascii=False)},
    ]


def deepseek_call(messages: list[dict], model: str, key: str, timeout: int = 60) -> str:
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 1200}).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if "error" in payload:
        raise RuntimeError(payload["error"].get("message", "deepseek error"))
    return payload["choices"][0]["message"]["content"].strip()


CODEX_BIN = Path("/opt/homebrew/bin/codex")
USAGE_LOG = Path.home() / "park-data" / "llm-usage" / "morning-brief.jsonl"
_TOKENS_USED_RE = re.compile(r"tokens used\s*\n\s*([\d,]+)")


def _log_codex_usage(call: str, stderr: str) -> None:
    """Codex prints a rounded 'tokens used' total to stderr on every call, win or
    lose the timeout race. Nothing before this read it, so there was no record
    of what the daily brief actually spends. Best-effort: a log miss must never
    break the call it is logging."""
    m = _TOKENS_USED_RE.search(stderr or "")
    if not m:
        return
    try:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(config.BJT).isoformat(timespec="seconds"),
                "call": call,
                "provider": "codex",
                "tokens": int(m.group(1).replace(",", "")),
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def codex_call(messages: list[dict], model: str | None, timeout: int = 150, *, call: str = "unlabeled") -> str:
    """Non-interactive Codex CLI call; returns the last assistant message."""
    prompt = "\n\n".join(m["content"] for m in messages)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        out_path = Path(fh.name)
    cmd = [str(CODEX_BIN), "exec", "--skip-git-repo-check", "-s", "read-only", "-c", 'model_reasoning_effort="low"', "-o", str(out_path)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    env = {**os.environ, "CODEX_NOTIFY_DISABLE": "1"}
    # Empty scratch cwd (no project context) and a closed stdin: with an inherited pipe Codex waits forever.
    with tempfile.TemporaryDirectory(prefix="morning-codex-") as scratch:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=scratch, check=False, stdin=subprocess.DEVNULL)
            _log_codex_usage(call, result.stderr)
            return out_path.read_text(encoding="utf-8").strip() if out_path.exists() else ""
        except subprocess.TimeoutExpired:
            return ""
        finally:
            out_path.unlink(missing_ok=True)


class LLM:
    """DeepSeek first, Codex CLI second. A provider that fails hard (no balance, no binary) is skipped for the rest of the run."""

    def __init__(self, prefer: str = "auto", deepseek_model: str = "deepseek-chat", codex_model: str | None = None) -> None:
        self.deepseek_model, self.codex_model = deepseek_model, codex_model
        self.key = config.DEEPSEEK_KEY.read_text(encoding="utf-8").strip() if config.DEEPSEEK_KEY.exists() else ""
        order = {"auto": ["deepseek", "codex"], "deepseek": ["deepseek"], "codex": ["codex"], "none": []}[prefer]
        self.providers = [p for p in order if (p == "deepseek" and self.key) or (p == "codex" and CODEX_BIN.exists())]
        self.dead: set[str] = set()
        self.calls: dict[str, int] = {"deepseek": 0, "codex": 0}
        self.errors: list[str] = []

    def complete(self, messages: list[dict], timeout: int = 240, *, call: str = "unlabeled") -> tuple[str, str]:
        for name in self.providers:
            if name in self.dead:
                continue
            try:
                self.calls[name] += 1
                text = deepseek_call(messages, self.deepseek_model, self.key, timeout=min(timeout, 90)) if name == "deepseek" else codex_call(messages, self.codex_model, timeout=timeout, call=call)
                if text:
                    return text, name
                self.errors.append(f"{name}: empty response")
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.errors.append(f"{name}: {msg[:120]}")
                if name == "deepseek" and any(k in msg for k in ("Insufficient Balance", "401", "402", "invalid_request_error")):
                    self.dead.add(name)
        return "", "none"

    @property
    def active(self) -> str:
        return next((p for p in self.providers if p not in self.dead), "none")


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def sanitize_note(text: str) -> str:
    text = text.strip().strip("“”\"'").replace("\n", " ")
    if any(w in text for w in FORBIDDEN):
        return ""
    return text[:60]


def rule_note(stats: dict) -> str:
    """Deterministic one-liner from the daily stats; used when no model is available."""
    if not stats:
        return ""
    pos, e20, e50, chg20, vr = stats.get("pos20"), stats.get("vs_ema20"), stats.get("vs_ema50"), stats.get("chg20d"), stats.get("vol_ratio")
    where = "20 日区间上沿" if pos is not None and pos >= 80 else "20 日区间下沿" if pos is not None and pos <= 20 else "20 日区间中部"
    if e20 is not None and e50 is not None:
        trend = "均线上方，短中期同向" if e20 > 0 and e50 > 0 else "均线下方，短中期同向" if e20 < 0 and e50 < 0 else "均线之间，短中期背离"
    else:
        trend = "均线数据不足"
    mom = f"20 日 {'+' if (chg20 or 0) > 0 else ''}{chg20:.1f}%" if chg20 is not None else "20 日涨跌未知"
    vol = "放量" if vr and vr >= 1.3 else "缩量" if vr and vr <= 0.7 else "量能平稳"
    return f"{where}，{trend}；{mom}，{vol}。"


def annotate_stocks(stocks: list[dict], date: str, llm: LLM | None, batch: int = 10) -> dict[str, str]:
    cache_path = config.CACHE_DIR / f"{date}-stock-notes.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    if llm is None or llm.active == "none":
        return {s["id"]: cache.get(s["id"], {}).get("note", "") for s in stocks}
    todo = [s for s in stocks if s["stats"] and (cache.get(s["id"], {}).get("as_of") != s["stats"].get("as_of") or not cache.get(s["id"], {}).get("note"))]
    for i in range(0, len(todo), batch):
        chunk = todo[i : i + batch]
        text, provider = llm.complete(batch_prompt(chunk), call="stock_note")
        answers = extract_json(text) if text else {}
        for s in chunk:
            note = sanitize_note(str(answers.get(s["id"], "")))
            cache[s["id"]] = {"as_of": s["stats"].get("as_of"), "note": note, "provider": provider if note else "none"}
        if llm.active == "none":
            break
    if todo:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return {s["id"]: cache.get(s["id"], {}).get("note", "") for s in stocks}


MACRO_FIELDS = ("位置", "结构", "赔率", "综合结论")


def macro_fallback(macros: dict[str, dict], date: str, llm: LLM | None) -> tuple[list[dict], str, str]:
    """When the upstream K-line newsletter is missing, synthesise the 16 macro blocks from the daily stats.

    Returns (assets in parse_kline_md shape, conclusion line, provider)."""
    if llm is None or llm.active == "none" or not macros:
        return [], "", "none"
    cache_path = config.CACHE_DIR / f"{date}-macro-fallback.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached["assets"], cached["conclusion"], cached["provider"]
    payload = {key: {"name": e["name"], **stats_facts(e["stats"])} for key, e in macros.items() if e["stats"]}
    messages = [
        {"role": "system", "content": "你是宏观 K 线日报的撰稿人，只基于给出的日线统计写作，不引用任何外部消息。对每个资产输出四项：位置（价格在区间和均线的位置）、结构（趋势强弱与方向）、赔率（是否形成，一句话）、综合结论（一句话）。每项不超过 45 个字，不给买卖建议。另外给一句不超过 60 字的跨资产今日结论，以「等待」「偏进攻」「偏防守」之一开头。只输出 JSON：{\"conclusion\": \"...\", \"assets\": {key: {\"位置\":..,\"结构\":..,\"赔率\":..,\"综合结论\":..}}}，不要其它文字。"},
        {"role": "user", "content": "字段含义：chg 为收益率百分比，vs_ema 为相对均线百分比，pos20 为 20 日区间位置百分位，vol_ratio 为 5 日/20 日量比。\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    text, provider = llm.complete(messages, timeout=240, call="macro_fallback")
    data = extract_json(text) if text else {}
    assets = []
    for key, entry in macros.items():
        fields = data.get("assets", {}).get(key, {}) if isinstance(data.get("assets"), dict) else {}
        clean = {k: sanitize_note(str(fields.get(k, ""))) for k in MACRO_FIELDS if fields.get(k)}
        if clean:
            assets.append({"name": entry["name"], "ticker": entry["symbol"], "as_of": entry["stats"].get("as_of", ""), "fields": clean, "key": key})
    conclusion = sanitize_note(str(data.get("conclusion", ""))) if assets else ""
    if assets:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"assets": assets, "conclusion": conclusion, "provider": provider}, ensure_ascii=False, indent=1), encoding="utf-8")
    return assets, conclusion, provider


def fill_missing_notes(stocks: list[dict], notes: dict[str, str]) -> tuple[dict[str, str], int]:
    """Any stock without a model note gets a rule-based line; returns (notes, fallback_count)."""
    out, fallback = dict(notes), 0
    for s in stocks:
        if not out.get(s["id"]) and s["stats"]:
            out[s["id"]] = rule_note(s["stats"])
            fallback += 1
    return out, fallback


def condense_macros(macros: dict[str, dict], analysis_by_key: dict[str, dict], overview: dict, date: str, llm: LLM | None) -> tuple[dict[str, dict], str]:
    """One paragraph per macro asset: position / regime / lean + reasoning, from the upstream analysis and 1d/4h/30m stats."""
    cache_path = config.CACHE_DIR / f"{date}-macro-condensed.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached["items"], cached["provider"]
    if llm is None or llm.active == "none":
        return {}, "none"
    payload = {}
    for key in MACRO_ORDER:
        entry = macros.get(key)
        if not entry:
            continue
        payload[key] = {
            "name": entry["name"],
            "upstream": (analysis_by_key.get(key) or {}).get("fields", {}),
            "stats": {TF_LABELS[tf]: stats_facts(st) for tf, st in market.tf_stats(overview, key).items()} or {"日线": stats_facts(entry["stats"])},
        }
    messages = [
        {"role": "system", "content": "你是 Park 的 K 线日报编辑。对每个资产只写一段 90–150 字的中文，先给三个标签再给理由：位置（高位/中位/低位）、状态（趋势/震荡）、倾向（偏多/偏空/观望），并说明日线、4 小时、30 分钟三个周期是否一致、关键位在哪。只基于给出的上游分析与统计，不引用外部消息，不给具体点位建议。只输出 JSON：{key: {\"位置\":..,\"状态\":..,\"倾向\":..,\"段落\":..}}，不要其它文字。"},
        {"role": "user", "content": "统计字段含义：chg 为收益率百分比，vs_ema 为相对均线百分比，pos20 为 20 根 K 线区间位置百分位，vol_ratio 为 5/20 量比。\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    text, provider = llm.complete(messages, timeout=240, call="macro_condense")
    data = extract_json(text) if text else {}
    items = {}
    for key in payload:
        row = data.get(key) if isinstance(data, dict) else None
        if isinstance(row, dict) and row.get("段落"):
            item = {k: str(row.get(k, "")).strip() for k in ("位置", "状态", "倾向", "段落")}
            # drop a leading "高位｜震荡｜观望。" echo of the tags
            item["段落"] = re.sub(r"^(?:[高中低]位|趋势|震荡|偏多|偏空|观望)(?:\s*[｜|/·，,]\s*(?:[高中低]位|趋势|震荡|偏多|偏空|观望))*\s*[。：:]\s*", "", item["段落"])
            items[key] = item
    if items:
        cache_path.write_text(json.dumps({"items": items, "provider": provider}, ensure_ascii=False, indent=1), encoding="utf-8")
    return items, provider if items else "none"
