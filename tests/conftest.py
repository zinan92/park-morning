import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture
def candles():
    def make(n=70, start=100.0, step=1.0):
        out = []
        price = start
        for i in range(n):
            o = price
            c = price + step * (1 if i % 3 else -1)
            out.append(dict(t=f"2026-06-{(i % 28) + 1:02d}", o=o, h=max(o, c) + 0.5, l=min(o, c) - 0.5, c=c, v=1000 + i))
            price = c
        return out

    return make


KLINE_MD = """---
title: 宏观 K 线日报
date: 2026-09-06
---

# 宏观 K 线日报｜2026-09-06

## 今日结论

**等待** · 跨资产表现分化，利率仍处高位。

## 世界模型

高利率约束下的轮动。

## 共有 16 个资产的综合结论与市场含义

### 美元 ETF（UUP）
标的：UUP
观察时点：2026-09-04T00:00:00Z

![美元 ETF（UUP）｜日线 K 线图](snapshots/abc.png)

**日线**：日线显示 UUP 报 28.08。

**位置**：位置：日线处于高位。
**结构**：结构：日线趋势减弱。
**综合结论**：偏中性略弱。

### 黄金 ETF（GLD）
标的：GLD
观察时点：2026-09-04T00:00:00Z

**日线**：黄金走强。
"""
