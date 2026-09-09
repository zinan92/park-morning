# 上游合同 · AI 日报

| | |
|---|---|
| 产出方 | [zinan92/daily-newsletter](https://github.com/zinan92/daily-newsletter) |
| 本机检出 | `~/work/input-to-park` |
| 定时 | launchd `com.wendy.parkio-push` 08:30（`push-digest.sh`，只生成不推送） |
| 交付路径 | `~/park-hands/006_ai daily newsletter/YY-MM-DD.md` |
| 截止时间 | 09:00（晨报第一次运行）。实测落盘时间 08:37–08:50 |

## 晨报读什么

- 去掉第一个 `# ` 标题，其余 Markdown 原样渲染。
- 摘要行统计：`^- \*\*` 的条数，显示为「N 条」。
- 「今天先看」取第一条深读标题 `### [标题](链接)`，没有深读时取第一条快讯标题。

## 晨报不读什么

这份日报目前没有任何运维段落，保持这样。若将来加入源状态、生成回执、覆盖窗口一类内容，
必须同时在 `morning/sources.py` 的 `load_ai` 里剥掉，否则会出现在读者面前。

## 模型

`PARKIO_LLM_PROVIDER=codex`（launchd 环境变量），`PARKIO_LLM_FALLBACK_PROVIDER=deepseek`。
Codex 是主力，DeepSeek 只在 Codex 失败时才被调用——余额为 0 时它会直接失败，
一旦充值就自动成为真正的备份，不需要再改配置。

## 耗时

整条管道端到端约 16 分钟（2026-09-09 实测，Codex low 推理档，54 条原料、17 个理解分块）。
自愈给它 40 分钟。Codex 单次调用约 20–35 秒；默认推理档会超过 180 秒下限并整轮失败，
所以 `PARKIO_CODEX_REASONING_EFFORT=low` 是必须的，不是优化。

## 缺失时的行为

栏目显示「今日不可用 · 未找到 26-09-08.md」，不回填前一期。`--alert` 会开一张 issue。

## 已知失败模式

- Codex 偶发输出重复 item card id，被自家 schema 拦下，整轮失败（2026-09-08 出现一次，
  重跑即过）。自愈会自动重跑；手动重跑用 `cd ~/work/input-to-park && ./push-digest.sh`
  （不要用 `push-feishu-digest.sh`，那会再推一条飞书）。
- 站点发布脚本（`park-ai-intel/scripts/refresh-newsletter.sh`）与晨报无关，它只更新
  `/newsletter` 归档页。
