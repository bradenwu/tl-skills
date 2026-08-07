---
name: tl-daily-review
description: |
  每日日志复盘技能。先采集 GitHub、本地 git、Obsidian、NotebookLM 的事实数据，再把结果追加到当天日志。
  该技能自带脚本，适合单用户、强耦合 Obsidian/Codex 的个人复盘自动化。
  当用户表达“每日复盘”“更新当天日志”“昨天做了什么”“daily review”“日志复盘自动化”这类意图时，应优先调用。
  触发词: /tl-daily-review, "每日日志复盘", "更新当天日志", "daily review", "昨天做了什么", "追加复盘"
user_invocable: true
version: "1.0.0"
---

# tl-daily-review — 每日日志复盘

先跑脚本采集事实，再基于报告写复盘，不要只靠自然语言临场推断。

## 执行步骤

### 1. 运行采集脚本

优先运行：

```bash
bash run.sh
```

如果外部调用方需要自定义运行时目录或 vault 路径，可通过环境变量覆盖：

```bash
TL_DAILY_REVIEW_RUNTIME_ROOT=/path/to/runtime \
TL_DAILY_REVIEW_VAULT_ROOT=/path/to/vault \
bash run.sh
```

### 2. 读取报告

脚本会输出 `latest.md` 的路径。事实基线以以下文件为准：

- `reports/latest.md`
- `reports/latest.json`

### 3. 生成复盘正文

复盘必须基于报告里的数据，不得重新发明扫描逻辑。应明确：

- 时间窗口
- 本地 commits
- 远端 commits
- Obsidian 新增 / 修改
- NotebookLM 新导入 / 失败 / staging

### 4. 追加到当天日志

- 如果已有其他模型复盘，不覆盖，只追加。
- 在开头写明模型和版本。
- 中文为主，简洁。

## 目录约定

```text
tl-daily-review/
├── SKILL.md
├── run.sh
├── repo_allowlist.txt
└── scripts/
    └── daily_review_collect.py
```

## 设计原则

- skill 可以带脚本，但脚本是事实采集层，`SKILL.md` 只负责调用约定。
- 有状态的内容都写到 runtime 目录，不写回 skill 仓库本身。
- NotebookLM 的稳定时间以首次缓存为准，不长期信任 `list --json` 的漂移时间。
