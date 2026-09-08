"""Paths, constants and the macro-asset keyword map.

Everything the build reads from disk is declared here, so tests can point the
whole pipeline at a temporary directory by patching one module.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo
# This repository. Alert issues are opened here.
REPO = Path(__file__).resolve().parent.parent
# The site repository that hosts published editions; override to build without
# touching the live site.
SITE_REPO = Path(os.environ.get("MORNING_SITE_REPO", str(Path.home() / "work" / "park-ai-intel")))
OUT_DIR = SITE_REPO / "public" / "daily"
HOME = Path.home()
VAULT = HOME / "park-hands"
AI_DIR = VAULT / "006_ai daily newsletter"
FIN_DIR = VAULT / "007_finance daily newsletter"
KL_DIR = VAULT / "007_kline daily newsletter"
PARK_DIR = KL_DIR / "park"
CACHE_DIR = KL_DIR / "park-morning-cache"
KLINE_DB = HOME / "park-data" / "market" / "kline.db"
MANIFEST = HOME / "datafeed-runtime-watchlist-151" / "configs" / "watchlist_registry_manifest.json"
WATCHLIST_YAML = HOME / "work" / "watchlist" / "watchlist.yaml"
DEEPSEEK_KEY = VAULT / "_secrets" / "deepseek-key"
FEISHU_ENV = VAULT / ".system" / "content-ops" / "secrets" / "feishu-digest.env"
SITE = "https://park-ai-intel.com"
REVIEW_OVERVIEW_URL = os.environ.get("MORNING_REVIEW_URL", "http://127.0.0.1:8932/api/overview")
VAULT_HTML_DIR = VAULT / "009_morning brief"
TF_LABELS = {"daily": "日线", "four_hour": "4 小时", "thirty_minute": "30 分钟"}
TF_ORDER = ("daily", "four_hour", "thirty_minute")
CHART_BARS = 160
BJT = ZoneInfo("Asia/Shanghai")
MACRO_ORDER = ["DXY", "SPX", "NDX", "SCHD", "VIX", "GOLD", "SILVER", "WTI", "BTC", "ETH", "HYPE", "SHCOMP", "STAR50", "DIVIDEND", "N225", "KOSPI"]
MACRO_KEYWORDS = [
    ("黄金", "GOLD"), ("白银", "SILVER"), ("原油", "WTI"), ("上证红利", "DIVIDEND"), ("中证红利", "DIVIDEND"), ("SCHD", "SCHD"), ("红利", "SCHD"),
    ("上证", "SHCOMP"), ("科创", "STAR50"), ("日经", "N225"), ("KOSPI", "KOSPI"), ("韩国", "KOSPI"),
    ("比特", "BTC"), ("以太", "ETH"), ("HYPE", "HYPE"), ("美元", "DXY"), ("标普", "SPX"),
    ("纳斯达克", "NDX"), ("纳指", "NDX"), ("恐慌", "VIX"), ("VIX", "VIX"), ("N225", "N225"), ("Nikkei", "N225"), ("MGC", "GOLD"), ("SIL", "SILVER"), ("BTC", "BTC"), ("ETH", "ETH"),
]
STOCK_FIELDS = ("日线", "位置", "结构", "赔率", "综合结论")
FINANCE_OPS_HEADINGS = ("Source Status", "Source Health", "Processing Status")
KLINE_OPS_HEADINGS = ("数据边界", "来源与状态")
KLINE_SUMMARY_ORDER = ("今日结论", "世界模型", "盘面领导与落后", "资金迁移（价格关系推断）", "理论机制", "接下来观察", "操作框架", "失效条件")


def macro_key(name: str, ticker: str = "") -> str | None:
    hay = f"{name} {ticker}"
    for kw, key in MACRO_KEYWORDS:
        if kw in hay:
            return key
    return None
