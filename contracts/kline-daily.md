# 上游合同 · K 线日报

| | |
|---|---|
| 产出方 | [zinan92/equity-research](https://github.com/zinan92/equity-research) |
| 运行时检出 | `~/Library/Application Support/ParkKlineDaily/app`（不在 `~/work`） |
| 定时 | launchd `com.park.market-regime.kline-newsletter` 08:20，带 `--no-feishu` |
| 交付路径 | `~/park-hands/007_kline daily newsletter/YYYY-MM-DD-kline-daily-newsletter.md`；重跑不覆盖，写 `…-newsletter-<hash>.md`，晨报取当天最新的一份 |
| 失败时写 | 同目录 `…-kline-daily-newsletter-unavailable.md`，含运行阶段与失败原因 |
| 截止时间 | 09:00 |

## 晨报读什么

- 跨资产总览八节，见 `morning/config.KLINE_SUMMARY_ORDER`。今日结论作为大字导语，其余折叠。
- `## 共有 16 个资产…` 之后的每个 `### 资产` 块：日线、位置、结构、赔率、综合结论。
- `## 美国国债` 之后的三块单独成组。
- 资产名与 `morning/config.MACRO_KEYWORDS` 匹配出宏观键，用来对齐行情与图表。
  **关键词有先后顺序**：「中证红利」必须排在「红利」前面，否则会覆盖 SCHD。

## 晨报剥掉什么

- 整节：`## 数据边界`、`## 来源与状态`
- 每个资产块里的 `标的：`、`观察时点：`、PNG 引用
- `**市场含义**`：每天逐字重复，不是当日信息
- `**赔率**：赔率尚未形成`：16 个资产全都一样时没有信息量

## 模型

launchd 传 `--primary-provider codex`：不再对每个资产先试一次 DeepSeek。
代价是这条线目前只有 Codex 一个 provider（Codex 自身会重试；资产 1 次、thesis 2 次）。
DeepSeek 充值后把 flag 改回 `deepseek` 即可恢复两个 provider。

## 缺失时的行为

晨报读到 `-unavailable.md` 时，改用日线统计让模型自生成 16 个宏观资产的分析，
栏目标「自生成」并写明上游失败原因。缓存在 `{date}-macro-fallback.json`。

## 已知失败模式

| 现象 | 原因 | 处理 |
|---|---|---|
| `OSError:[Errno 11] Resource deadlock avoided` | macOS flock 偶发 EDEADLK | 已修（equity-research PR #1055），重跑即可 |
| `DailySnapshotError:chromium_unavailable` | Playwright chromium 瞬时起不来 | `launchctl kickstart gui/$(id -u)/com.park.market-regime.kline-newsletter` |
| 全线 DeepSeek 402 | 账户余额为 0 | 上游自身有 Codex 兜底；充值是根治 |
| 图表与「观察时点」停在几天前，但上游正常产出 | 08:15 的 datafeed 种子没跑：`sync_watchlist_registry` 查 GitHub ref 时匿名额度（60/h，按 IP）用尽返回 403，`&&` 后面的种子被跳过，kline.db 整天没有新柱 | 已修（datafeed PR #181）：查询带 token（`GITHUB_TOKEN_FILE`），查询失败时沿用旧清单继续种子。手动补：`launchctl kickstart gui/$(id -u)/com.wendy.datafeed.watchlist-daily`，再依次刷新 8932（`/api/overview?refresh=true`）、kickstart K 线日报、删 `{date}-overview.json` `{date}-macro-condensed.json` `{date}-stock-notes.json`、重跑晨报 |

## 上游的上游：datafeed 日线种子

K 线日报、8932 盘中总览和晨报里的日线全部来自 `~/park-data/market/kline.db`，
由 launchd `com.wendy.datafeed.watchlist-daily` 08:15 写入（107 个 instrument）。
它是整条 K 线链的第一环，回执在 `~/park-data/market/watchlist-latest.json`
（`instrument_status_counts`）和 `watchlist-registry-receipt.json`（`status`）。
晨报判断新鲜度最省事的办法：`sqlite3 ~/park-data/market/kline.db "select max(timestamp) from mvp_candles where instrument_id='WATCH.CROSS.SPX' and timeframe='1d'"`。

## 综合解释（今日结论）经常是占位句

上游的「今日结论」由 thesis 步骤生成，校验极严（证据 ID、数字必须绑定、禁用词、限定词）。
`--primary-provider codex` 之后只有 Codex 一个候选，输出没过校验就写占位句
「本期综合解释尚未生成」，`## 来源与状态` 里会有一行「模型失败披露：…备用模型：validation_error」。
2026-09-08、09-09 重跑、09-10 三次都是这样，09-09 08:28 那次成功。晨报把占位句原样显示为导语，
不用旧结论冒充。

## 盘中数据（另一条源）

**日线一律来自 kline.db**（08:15 写入，永远是最新的）；4 小时、30 分钟来自 Human K-line Review：
`http://127.0.0.1:8932/api/overview`，launchd `com.park.human-kline-review`。
这个服务只在被要求时才重新拉数据：2026-09-10 早上它的 bundle 还是前一天 02:00Z 的，
所有盘中图落后一天。晨报从 v5 起先请求 `?refresh=true`（最多等 8 分钟），超时再读旧 bundle，
每天缓存一次为 `{date}-overview.json`。拿不到时只显示日线，不放占位。

### 各资产实际能拿到哪些周期（2026-09-08 实测）

| 资产 | 日线 | 4 小时 | 30 分钟 |
|---|---|---|---|
| VIX、BTC、ETH、HYPE | 有 | 有 | 有 |
| GOLD、SILVER、WTI | 有 | 有 | 有 |
| DXY、SPX、NDX、SCHD | 有 | **没有** | 有 |
| N225、KOSPI | 有 | 没有 | 没有 |
| SHCOMP、STAR50、DIVIDEND | 有（来自 kline.db） | 没有 | 没有 |

四个美股 ETF 没有 4 小时不是故障：datafeed 返回
`timeframe_not_supported · Source yahoo_finance does not serve SPY at 4h`，
是数据源本身不提供。A 股与日韩指数没有盘中源。这些情况下晨报只显示有的周期。

### 不要用上游的 stale 标记判断新鲜度

Human K-line Review 按墙上时钟判断 `status: stale`。美国假日后的早上，
盘中序列合法地停在上一个交易日，会被它标成 stale。晨报改为把盘中序列的
最后一根与**同一资产自己的日线**比较，落后超过 `market.STALE_AFTER_DAYS` 天才提示。
2026-09-07 是美国劳动节，当天早上四个商品的 4 小时停在 09-04，属于正常。
