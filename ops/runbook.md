# Runbook

## 正常的一天

| 时间 | 发生什么 |
|---|---|
| 08:00 | 财经日报写入 vault |
| 08:15 | datafeed 把 107 个 instrument 的日线写入 `~/park-data/market/kline.db` |
| 08:20 | K 线日报写入 vault（`--no-feishu`） |
| 08:30 | AI 日报写入 vault（只生成，不推送） |
| 09:00 | 晨报第一次运行：合成、发布、一条飞书 |
| 09:40 | 晨报第二次运行：只有栏目从缺失变正式时才补发一条「已补齐」 |

三条上游各自的飞书推送已全部关停，读者只收到晨报这一条。

## 早上打开发现某一栏是「今日不可用」

先看是哪一栏，再按对应合同里的「已知失败模式」重跑上游，最后重跑晨报：

```bash
cd ~/work/park-morning && ./build-morning.py --send-feishu
cd ~/work/park-ai-intel && /bin/bash scripts/refresh-morning.sh   # 或直接跑这一条，它包含构建
```

09:40 那次会自动做这件事，所以多数情况下不需要手动介入。

## 常用命令

```bash
./build-morning.py --dry-run                    # 只看三条上游今天在不在，不写文件
./build-morning.py --date 2026-09-08            # 重建某一天
./build-morning.py --no-ai                      # 不调模型，用缓存和规则描述
./build-morning.py --llm deepseek               # 强制 DeepSeek（默认 codex）
MORNING_SITE_REPO=/tmp/x ./build-morning.py     # 构建到别处，不碰线上
```

## 停掉它

```bash
launchctl bootout gui/$(id -u)/com.wendy.park-morning     # 停止定时
touch ~/.park-morning.off                                 # 保留定时但跳过运行
```

## 缓存

都在 `~/park-hands/007_kline daily newsletter/park-morning-cache/`，按日期命名：

| 文件 | 内容 | 删了会怎样 |
|---|---|---|
| `{date}-stock-notes.json` | 91 只个股的一句描述 | 重新调用模型，约 10 次 |
| `{date}-macro-condensed.json` | 16 个宏观资产的压缩段落 | 重新调用模型，1 次 |
| `{date}-macro-fallback.json` | 上游缺失时的自生成分析 | 同上 |
| `{date}-overview.json` | 盘中 K 线数据 | 重新拉一次 8932 |
| `{date}-feishu.json` | 当天飞书回执与三栏状态 | 会重复发一条 |

## Codex CLI 的两个坑

从 Python 子进程调 `codex exec` 时：

1. 必须 `stdin=subprocess.DEVNULL`，否则继承管道会无限等待。
2. cwd 用空临时目录，在仓库里跑会加载项目上下文，一次调用能卡几分钟。

不要用 `pkill -f "codex exec"` 清理，会误杀别的会话的 Codex；按 PID 杀。
