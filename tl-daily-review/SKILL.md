---
name: tl-daily-review
description: |
  每日日志复盘技能。先采集 GitHub、本地 git、Obsidian、NotebookLM 与 Agent History Bank 的事实数据，
  再把结果追加到当天日志。该技能自带脚本，适合单用户、强耦合 Obsidian/Codex 的个人复盘自动化。
  除活动统计外，复盘后必须继续完成增值动作：基于事实基线的启发式发散、针对昨日所有修改文件的知识检索回顾（retrieval quiz），以及必要时的采集层修复闭环。
  当用户表达“每日复盘”“更新当天日志”“昨天做了什么”“daily review”“日志复盘自动化”这类意图时，应优先调用。
  触发词: /tl-daily-review, "每日日志复盘", "更新当天日志", "daily review", "昨天做了什么", "追加复盘"
user_invocable: true
version: "1.2.1"
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
- Agent History（昨天与 AI 的所有对话会话清单）

### 4. 追加到当天日志

- 如果已有其他模型复盘，不覆盖，只追加。
- 在开头写明模型和版本。
- 中文为主，简洁。
- 注意：复盘对象通常是“昨天”，但追加目标是**运行当天日志**（例如 08-12 运行时，应写入 `04_日志/2026-08-12.md` 的“昨日复盘”，而不是写回 `04_日志/2026-08-11.md`）。

### 5. 必选增值动作

完成复盘正文并追加后，必须继续执行下文「复盘之后（必选增值动作）」：

1. 生成基于事实的启发式发散。
2. 基于昨日所有修改文件生成知识检索回顾（retrieval quiz）HTML。
3. 若本次报告暴露数据质量问题，完成采集层修复闭环；若没有问题，明确记录“本次无采集层修复”。

## 目录约定

```text
tl-daily-review/
├── SKILL.md
├── run.sh
├── repo_allowlist.txt
└── scripts/
    ├── daily_review_collect.py
    └── quiz_template.html
```

## Agent History Bank（ahb）集成

采集脚本会在运行时自动调用 [Agent History Bank](https://github.com/bradenwu/agent-history-bank)（`ahb`）：

1. 先执行 `ahb sync` 增量归档最新的 Claude Code / Codex 对话历史（幂等，可安全重复运行）。
2. 再读取 Obsidian 中 `Agent History/Daily/<昨天日期>.md` 的会话索引，
   汇总到报告的 `agent_history` 字段与 `## Agent History（AI 对话）` 章节。

这样每日复盘时可以直接参考昨天与 AI 的全部对话会话，作为反思的事实基线。

相关环境变量（可选）：

- `TL_DAILY_REVIEW_AHB_BIN`：指定 `ahb` 二进制绝对路径（默认探测 PATH 及 `~/Code/bradenwu/agent-history-bank/ahb`）。
- `TL_DAILY_REVIEW_AHB_CONFIG`：指定 ahb 配置文件路径（默认 `~/.ahb/config.toml`）。

若 `ahb` 未安装或 sync 失败，采集不会中断，报告会标注 FAIL 并跳过该章节的会话清单。

> **注意**：ahb 配置了本地 Ollama 富集（`enrich_provider = local`）时，首次运行需要为存量通用标题会话批量生成标题，
> 可能耗时数分钟（受 `max_per_run` 与软失败保护限制）。核心 sync（含 Daily 笔记写入）在富集之前完成，
> 因此即使富集阶段超时（脚本设 600 秒上限），Daily 笔记仍可正常读取。富集为增量，首次回填后日常运行很快。

## 已知数据质量护栏

采集脚本会把原始数据转成事实基线，但有几类已知瑕疵，叙事前必须心里有数，否则会基于错误数据编故事——本节就是从一次时区误读的踩坑中沉淀出来的。

- **时区（脚本侧已修复，读原始来源时仍要警惕）**：`agent_history.daily_entries[].sessions[].timestamp` 经脚本转换后已是 CST 可读串（如 `2026-08-10 08:07:05 CST`），`timestamp_utc` 保留原始 UTC 供溯源。**但如果直接读 ahb 的 `Agent History/Daily/*.md` 原始笔记，时间戳仍是 UTC（带 `Z`，如 `2026-08-10T00:07:05.684Z`），叙事前必须换算**——`00:07Z` 不是凌晨，是早上 08:07。这正是"凌晨高密度协作"伪命题的根源。
- **采集噪音**：磁盘扫描会把 `.DS_Store` 等系统/编辑器残留文件计入 Obsidian 新增/修改列表，叙事时需剔除（未来可在采集层加后缀黑名单）。
- **ahb 未识别率**：ahb 对 codex 来源会话的标题识别率可能偏低（实测可达 63% 的 codex 会话标题是 `Codex Session` 占位符），导致会话清单可读性下降、会话总数语义偏弱，叙事时应标注"含若干未识别标题"。

## 设计原则

- skill 可以带脚本，但脚本是事实采集层，`SKILL.md` 只负责调用约定。
- 有状态的内容都写到 runtime 目录，不写回 skill 仓库本身。
- NotebookLM 的稳定时间以首次缓存为准，不长期信任 `list --json` 的漂移时间。

## 复盘之后（必选增值动作）

以下动作是每日复盘的**必选收尾**，不需要用户额外触发。默认流程不再止于「追加到当天日志」，而是必须继续完成启发式发散、知识检索回顾，并检查是否需要采集层修复。

### A. 启发式发散

基于本次事实基线 + 对用户近期目标/兴趣的记忆，主动给"接下来可以做什么"的头脑风暴：

- 哪条线索值得深挖（一个 commit 引出待办，一次会话引出一篇笔记）
- 哪个能力缺口被本次复盘暴露（某工具反复查文档 = 该系统化学了）
- 哪些摄入可以转产出（读了 X，可以写 Y）

每条建议都要标注**依据的事实**（来自报告哪一段），避免空泛。

### B. 知识检索回顾（retrieval quiz）

针对"学到了什么"出题，而非"做了什么"统计。记忆衰退曲线最陡处收益最高，所以**优先考最新摄入**。

**数据源扫描**：昨日所有修改文件。

以本次事实报告中的“昨日修改文件”为准，不再按固定目录扫描近 N 天摄入源。优先级如下：

1. `reports/latest.json` 中 `obsidian.modified_files` 与 `obsidian.new_files`：vault 内昨日修改/新增的 Markdown、图片旁注、NotebookLM 卡片、Clippings、日志、wiki 等。
2. `reports/latest.json` 中 `disk.modified_files` 与 `disk.new_files`：vault 外扫描目录（如 `~/Work`）昨日修改/新增的教学、项目、文档文件。
3. 若报告未来提供 git touched files，再纳入本地/远端 commit 触及的文件；当前只用 commit subject 作为辅助线索，不临时重写 git 扫描逻辑。

筛选规则：

- 优先读取 Markdown / 文本 / 课程材料 / NotebookLM 卡片 / Clippings / wiki 笔记等可形成知识题的文件。
- 跳过明显噪音与低知识密度文件，如 `.DS_Store`、`.pytest_cache/`、二进制缓存、纯索引回填、AI 会话原始镜像中无明确主题的通用标题文件。
- 如果昨日修改文件数量很多，先聚类主题，再从每个高价值主题抽样；不要只按目录偏好取样。

**出题原则**：

1. 优先最新摄入（刚读、刚划线的）
2. 概念辨析用**选择**题（多个相似概念并排辨析）
3. 术语/定义回忆用**填空**题
4. 每题带 `why`（解析）+ `ref`（出处）；**正确答案后必须紧跟出题依据/材料出处**，方便用户答完后立刻回查复习；答错时尤其要把出处讲清

**产物**：用 `scripts/quiz_template.html` 生成单文件 HTML，写到当天日志旁（如 `04_日志/YYYY-MM-DD-review.html`）。流程：读取昨日修改文件清单 → 筛选高价值知识源 → 读模板 → 填题库 `Q` 数组 → 写出文件 → 在当天日志中追加/更新 quiz 链接（例如 `[[2026-08-12-review.html]]`），无需从零写样式。

**题库字段要求**：

- `ref` 必填，写可回查的材料出处；vault 内材料优先用 Obsidian wikilink，外部/绝对路径材料写清文件路径或标题。
- 选择题的正确答案显示格式应包含：`正确答案：<选项文本>（依据：<ref>）`。
- 填空题的正确答案显示格式应包含：`正确答案：<answer>（依据：<ref>）`。
- 不要只在 `why` 里泛泛提来源；答案旁边必须能直接看到依据。

### C. 采集层修复闭环

发现报告数据质量问题时（时区错位、噪音文件、ahb 未识别率高），要么：

- 回写 `scripts/daily_review_collect.py` 在采集层根治，或
- 在上文「已知数据质量护栏」补一条规则，提醒下次叙事时手动处理

不要把数据质量问题留给临场叙事去"心算"——那正是时区误读的根源。
