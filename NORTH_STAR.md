# North Star — park-morning

> Stable intent. Change this only when Park explicitly changes the product
> destination, approved baseline, or success definition.

## What we are building

Park 每天早上真正会读的那一页。三条已经在跑的日报管道各自产出 Markdown，
这个仓库在它们之后加一步：读当天产出、剥掉运维内容、合成一页 HTML、推一条飞书。
读者只有一个入口、一条推送。

它不是新的内容管道，也不重写任何上游。上游改的是内容，这里改的是阅读体验。

## Done looks like

连续 30 期，每期三栏全部是当日正式内容，无人工介入。
当前基线：v4 页面 `https://park-ai-intel.com/daily/2026-09-08.html`。

## Approved foundations

| Item | Canonical artifact / reference | Decision date | Do not reinvent |
| --- | --- | --- | --- |
| 阅读版式 v4：三栏独立滚动、暖纸底、低饱和涨跌色 | `morning/render.py` | 2026-09-08 | yes |
| 三条上游合同 | `contracts/` | 2026-09-08 | yes |
| 模型三级兜底 DeepSeek → Codex CLI → 规则 | `morning/llm.py` | 2026-09-08 | yes |
| 每资产一段 + 最多三张可缩放 K 线 | `morning/render.py` `render_macro` | 2026-09-08 | yes |

## Milestones to the intent

| # | Milestone | Evidence that it is complete | Status |
| --- | --- | --- | --- |
| 1 | 三份日报合成一页、一条推送 | 2026-09-08 上线，上游飞书全部关停 | done |
| 2 | 上游任一失败时页面仍然可读 | K 线自生成兜底 + 09:40 二次运行 | done |
| 3 | 连续 30 期三栏全绿，零人工介入 | `public/daily/status/*.json` 连续 30 天三栏 ok | not started |
| 4 | 编辑不再需要改代码 | Park 手写判断进入页面的路径不经过工程 | partial |

## Non-negotiables

- 上游缺失时显示原因，永远不用前一期冒充今天。
- 页面上不出现运维字段：源状态、生成回执、覆盖窗口、内部 key。
- 模型只描述位置、结构、动能；不出现买卖、建议、目标价、止损。
- 没有数据源的周期不显示，不放占位。
- 不连接券商，不下单。

## Change control

`REGISTRY.md` may report progress through these milestones but cannot redefine
them. Record the rationale for a North Star change in `decision-log.md` and
link the approving decision.
