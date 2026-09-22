# 上游合同 · K 线日报

| | |
|---|---|
| 产出方 | [zinan92/equity-research](https://github.com/zinan92/equity-research) |
| 运行时检出 | `~/Library/Application Support/ParkKlineDaily/app`（不在 `~/work`） |
| 定时 | launchd `com.park.market-regime.kline-newsletter` 08:20，带 `--no-feishu --no-snapshots` |
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
- 每个资产块里的 `标的：`、`观察时点：`（`--no-snapshots` 之后上游不再产出 PNG）
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

## 综合解释（今日结论）曾连续三期是占位句

2026-09-08、09-09 重跑、09-10 的「今日结论」都是「本期综合解释尚未生成」。两个根因，都在
equity-research PR #1070 修掉：① thesis 请求构造器读 `analysis["output"]`，而落盘的单资产
分析是扁平的，模型收到 19 个空资产；② Codex 默认推理档下这个请求要 13 分钟以上，运行时只给
360 秒。现在所有 Codex 调用带 `model_reasoning_effort="low"`（`PARK_KLINE_CODEX_REASONING_EFFORT`
可覆盖），实测 83 秒并通过校验。再看到占位句，先看 md 末尾「模型失败披露」那一行。

## 只看日线（2026-09-22 起）

Park：「每一只股票的格式都一样，只看日线，不要整得这么复杂了。」

晨报对宏观资产和个股使用同一个卡片：名称、价格、涨跌、一张日线图、一段描述，
一行三个。宏观多三个标签（位置/状态/倾向），其余完全一致。

因此这些东西已经从晨报移除，不要再加回来：

- Human K-line Review（8932）的盘中总览、`{date}-overview.json` 缓存、`?refresh=true` 预热
- 4 小时 / 30 分钟图槽与 `TF_ORDER` / `TF_LABELS`
- 盘中滞后判断 `series_lag_days` / `STALE_AFTER_DAYS`

`condense_macros` 的提示词也已改为只看日线；再改动时别让它重新提到盘中周期。

## 图表快照已关闭

上游原本用无头浏览器把每个资产渲染成 PNG 存进 md。这一步是 2026-09-12、09-13、
09-14、09-21、09-22 五次 `-unavailable` 的唯一原因（`Page.goto: Timeout 30000ms`），
而晨报本来就把 PNG 引用剥掉、用 lightweight-charts 自己画。2026-09-22 起 launchd 带
`--no-snapshots`：失败模式消失，读者看到的东西不变，代价是 Obsidian 里的 md 只有文字。
