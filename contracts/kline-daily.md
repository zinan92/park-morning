# 上游合同 · K 线日报

| | |
|---|---|
| 产出方 | [zinan92/equity-research](https://github.com/zinan92/equity-research) |
| 运行时检出 | `~/Library/Application Support/ParkKlineDaily/app`（不在 `~/work`） |
| 定时 | launchd `com.park.market-regime.kline-newsletter` 08:20，带 `--no-feishu` |
| 交付路径 | `~/park-hands/007_kline daily newsletter/YYYY-MM-DD-kline-daily-newsletter.md` |
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

## 缺失时的行为

晨报读到 `-unavailable.md` 时，改用日线统计让模型自生成 16 个宏观资产的分析，
栏目标「自生成」并写明上游失败原因。缓存在 `{date}-macro-fallback.json`。

## 已知失败模式

| 现象 | 原因 | 处理 |
|---|---|---|
| `OSError:[Errno 11] Resource deadlock avoided` | macOS flock 偶发 EDEADLK | 已修（equity-research PR #1055），重跑即可 |
| `DailySnapshotError:chromium_unavailable` | Playwright chromium 瞬时起不来 | `launchctl kickstart gui/$(id -u)/com.park.market-regime.kline-newsletter` |
| 全线 DeepSeek 402 | 账户余额为 0 | 上游自身有 Codex 兜底；充值是根治 |

## 盘中数据（另一条源）

日线以外的 4 小时、30 分钟来自 Human K-line Review：`http://127.0.0.1:8932/api/overview`，
launchd `com.park.human-kline-review`。晨报每天缓存一次为 `{date}-overview.json`。
拿不到时只显示日线，不放占位。
