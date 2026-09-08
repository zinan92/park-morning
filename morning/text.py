"""Markdown and front-matter helpers."""
from __future__ import annotations

import html
import re
from datetime import datetime

from .config import BJT

try:
    import markdown as md_lib
except ImportError:  # pragma: no cover
    md_lib = None


def bjt_today() -> str:
    return datetime.now(BJT).strftime("%Y-%m-%d")


def short_date(d: str) -> str:
    return d[2:]


def md_to_html(text: str) -> str:
    if md_lib is None:
        return f"<pre>{html.escape(text)}</pre>"
    return md_lib.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def strip_front_matter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end].strip()
            meta = {}
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
            return meta, text[end + 4:].lstrip("\n")
    return {}, text


def drop_first_h1(text: str) -> str:
    return re.sub(r"^# [^\n]*\n", "", text, count=1)
