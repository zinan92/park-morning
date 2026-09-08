<div align="center">

# park-morning

**把三份各自生成的日报，合成 Park 每天早上真正会读的那一页。**

[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-14%20passing-2E7D32.svg)](tests/)
[![Schedule](https://img.shields.io/badge/launchd-09%3A00%20%2B%2009%3A40-8b6a3e.svg)](ops/launchd/)
[![License](https://img.shields.io/badge/license-MIT-16794C.svg)](LICENSE)

</div>

---

```text
in   AI 日报 / 财经日报 / K 线日报 的当日 Markdown（vault）
   + kline.db 日线 + Human K-line Review 的 4 小时与 30 分钟
   + Park 手写判断（可选）
out  一页 HTML：三栏独立滚动 + 16 个宏观资产 + 91 只个股 + 一条飞书
fail 上游缺失     → 该栏显示「今日不可用」和原因，不回填前一期
fail K 线上游缺失 → 16 个宏观资产按日线统计自生成，标「自生成」
fail 模型不可用   → 个股描述退回规则生成，页面注明
fail 周期无数据源 → 不显示该周期，不放占位
```

## 它解决什么

三条管道各自生成、各自推送，Park 每天早上要看三个地方、两个飞书群、一个本地端口。
这个仓库不重写任何一条管道，只在它们之后加一步：读当天的产出，剥掉运维内容，
合成一页，推一条。三条上游的飞书推送已经全部关停。

## 快速开始

```bash
./build-morning.py --dry-run          # 看三条上游今天在不在
./build-morning.py                    # 构建今天，写进站点仓库
./build-morning.py --date 2026-09-08  # 重建某一天
```

构建默认写进 `~/work/park-ai-intel/public/daily`，由该仓库部署到
`park-ai-intel.com/daily/`。用 `MORNING_SITE_REPO` 指向别处即可离线试。

## 页面长什么样

桌面端左中右三栏，各自独立滚动，页面本身不滚动。窄屏堆叠。

| 栏 | 内容 |
|---|---|
| AI 日报 | 上游原样，它本来就没有运维段落 |
| 财经日报 | 今日交易地图、过去 24 小时、A 股映射、今天不该追的 |
| K 线日报 | 今日结论 + 折叠的跨资产叙事；16 个宏观资产每个是「三张可缩放 K 线 + 一段带位置/状态/倾向标签的话」；美国国债三块；91 只个股每只两行一图 |

## 代码结构

| 模块 | 职责 |
|---|---|
| `morning/config.py` | 路径、常量、宏观资产关键词映射。测试只需 patch 这一个模块 |
| `morning/sources.py` | 三条上游：定位当天文件、解析、剥离运维内容 |
| `morning/market.py` | K 线、统计、迷你 SVG、盘中数据 |
| `morning/llm.py` | DeepSeek → Codex CLI → 规则，三级兜底 |
| `morning/render.py` | HTML 渲染 |
| `morning/delivery.py` | 飞书消息与告警 issue |
| `morning/cli.py` | 命令行入口 |

上游合同在 [`contracts/`](contracts/)，出问题看 [`ops/runbook.md`](ops/runbook.md)。

## 模型

默认 Codex CLI（`--llm codex`），DeepSeek 需要显式指定。任何一个 provider
因为余额或缺失而失败，会被标记为本轮不可用，不再逐条重试。都不可用时，
个股描述退回按日线统计的规则生成，页面注明。

个股描述与宏观段落只描述位置、结构和动能，不出现买卖、建议、目标价、止损这类词；
生成结果经过关键词过滤，命中即丢弃。

## 验证

```bash
python3 -m pytest        # 14 passed
```

## 边界

不连接券商，不下单，不给投资建议。所有分析只基于当日行情统计和上游已发布的内容。
