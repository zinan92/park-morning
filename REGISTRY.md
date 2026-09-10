# park-morning

> 当前快照。完成推进或 Good Night 结算时更新；历史留在 `daily/` 与 `decision-log.md`。

## 要去哪里

Park 每天早上真正会读的那一页：三份日报合成一页 HTML，一条飞书，读者只有一个入口。

## 现在在哪里（2026-09-10）

- 代码从 `park-ai-intel/scripts/build-morning.py`（1037 行单文件）搬到本仓，拆成
  `morning/` 七个模块。搬迁前后用同一天的输入构建，产物逐字节相同（685,017 字节）。
- 测试 20 passed（搬迁前 11）。新增：财经运维段剥离、vault 存档、只有上游恢复才补发飞书、
  页面无实质变化时不重写、盘中滞后判断、自愈的四条规则。
- launchd `com.wendy.park-morning` 09:00 与 09:40 各跑一次，指向本仓
  `ops/refresh-morning.sh`；构建产物写进 `park-ai-intel/public/daily` 并由该仓库部署。
- 三条上游的飞书推送已全部关停：AI 日报改跑 `push-digest.sh`；财经加
  `PARK_INTEL_SKIP_FEISHU=1`；K 线加 `--no-feishu`（equity-research PR #1064）。
- 已发布两期：2026-09-07（首期，两栏缺失）、2026-09-08（三栏全绿，v4 版式）。

- 09:30 之后的运行带 `--heal`：当天没有产出的上游各重跑一次。近 14 天上游到达率
  AI 13/14、财经 12/14、K 线 10/14，三条同时到齐约 57%；每次人工重跑都一次成功，
  所以把这一步自动化。

- 三条上游全部改为 Codex CLI 优先：AI 日报 `PARKIO_LLM_PROVIDER=codex`（备份 deepseek）、
  财经 `_llm_order()` 默认 codex（intel PR #127）、K 线 `--primary-provider codex`
  （equity-research PR #1069）。此前每次运行都先花一次请求换一个 HTTP 402。

- 2026-09-09 第三期：09:00 两栏、09:55 自愈重跑 AI 日报（超时 900s 被杀，改 2400s 后人工补齐）、
  10:06 三栏全绿。但 K 线图停在 09-04/09-07：datafeed 08:15 种子因 GitHub 匿名限流没跑。
  修了两处：datafeed PR #181（查询带 token、查询失败沿用旧清单），晨报改读当天最新一份
  K 线日报（重跑不覆盖，写 `-<hash>.md`）。10:41 重建，全部资产日线到 09-08。

- 2026-09-10 v5 版式（Park 反馈：三栏难读、上证/黄金/白银/WTI 没图、个股要先分市场、K 线太小）。
  单栏 1180px + 粘性导航；宏观图槽改按宏观键命名（之前 GC=F 等八个资产的槽永远找不到数据）；
  日线改直接取 kline.db，8932 只供盘中并且先 `?refresh=true`；个股先 A 股/港股/美股/韩股再赛道，
  每只一张 150px 交互图。页面从 700KB 涨到 1.4MB（内嵌 91 只个股的 80 根日线 + SVG 占位）。
  上游今日结论连续三次是占位句（Codex 输出过不了 thesis 校验），正在查。

## 下一步

1. 连续 30 期三栏全绿，零人工介入。当前连续 2 期，两期都有人工介入（09-08 重跑、09-09 补种子）。
   「三栏绿」不等于「数据新」：新鲜度要看 kline.db 最新柱，见 runbook。
2. 每期 HTML 约 1.4MB（v5 起）提交进站点仓库，一年约 500MB。到 30 期时决定是否改为
   Cloudflare Pages 独立托管，只把 `status/*.json` 留在 git 里。
3. Park 手写判断目前需要在 vault 里建文件；观察实际使用频率后再决定要不要页面入口。
4. 盘中数据已查清，不是故障：四个美股 ETF 的 4 小时是 Yahoo 不提供，A 股与日韩指数
   没有盘中源，实测表格在 `contracts/kline-daily.md`。上游的 stale 标记按墙上时钟判断，
   假日后会误报，已改为与同资产日线比对。

## Appendix（历史沉淀）

- 2026-09-07 首期上线（PR park-ai-intel#93）。当天三条上游在各自时间点全部失败，
  根因是 DeepSeek 余额为 0，Codex 兜底在三条线上都是第一次真实跑。
- 2026-09-08 v2 模型层兜底、v3 K 线压缩与交互图、v4 三栏阅读版式，
  分别为 park-ai-intel PR #94 #96 #97 #98。
