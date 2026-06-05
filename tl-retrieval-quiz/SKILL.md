---
name: tl-retrieval-quiz
description: Create Obsidian retrieval-practice quiz projects from one or more Markdown notes. Use when the user asks to make a knowledge-consolidation quiz, retrieval practice, review test, interactive HTML quiz, or safe companion review asset for current notes, reading notes, course notes, papers, web clippings, WeRead/Zotero/Readwise synced notes, or a topic spanning multiple sources.
---

# tl-retrieval-quiz

Turn one or more already-read Markdown sources into a vault-level retrieval-practice project:

```text
_retrieval/<topic>/
├── index.md     # single source of truth
└── quiz.html    # generated build artifact
```

`index.md` owns the scope, source list, quiz JSON, review records, and wrong-answer archive. `quiz.html` is rebuilt from `index.md`; do not edit it directly.

## Workflow

### 1. Confirm topic and sources

- Choose a short topic name for `_retrieval/<topic>/`. Ask only if the topic cannot be inferred.
- Collect one or more source Markdown files. Use relative vault paths for vault files.
- Do not modify source notes unless the user explicitly asks.
- Treat `_retrieval/` at vault root as the skill-managed project area.

### 2. Probe source profile

For each source, inspect frontmatter, file path, headings, and representative content.

Record:

- `source_type`: `weread`, `zotero`, `readwise`, `web-clip`, `paper-note`, `course-note`, `book-note`, `manual-note`, or `mixed`.
- `overwrite_risk`: `high` for synced/generated sources (`doc_type: weread-*`, `zotero-*`, `readwise-*`, plugin-sync markers); otherwise `low` unless evidence suggests overwrite risk.
- `ref_granularity`: `block` if usable `^block-id` anchors exist; else `heading` if stable headings exist; else `excerpt`.
- `size`: `small` / `medium` / `large` by total characters and number of highlights/paragraphs.
- `progress_boundary`: frontmatter progress/last-read data, explicit user range, or a concise inferred boundary.

### 3. Define scope and themes

Write clear boundaries before generating questions:

- `included`: 3-7 bullets for content covered.
- `excluded`: bullets for unread, out-of-scope, bibliographic, or unrelated content.
- `themes`: 3-7 core themes, each mapped to at least one source fragment.

Confirm with the user only when the scope is ambiguous, very large, or spans unrelated topics.

### 4. Generate questions in three levels

Use mixed, retrieval-oriented questions. Keep wording concise and avoid trick questions.

- `L1` Recognition: single-choice and true/false; definitions, explicit claims, key facts.
- `L2` Distinction: single-choice, multiple-choice, true/false; confusing concept pairs, misconceptions, counterintuitive claims.
- `L3` Application transfer: scenario single-choice plus 1-3 subjective questions; realistic use, self-explanation, planning, or metacognitive repair.

Subjective count:

- small content: 1 subjective question
- medium content: 2 subjective questions
- large content: 3 subjective questions

Every objective question needs `options`, `answer` as zero-based indexes, and `explain`. Subjective questions need `sample` and `explain`, no auto-grading.

### 5. Attach source references

Every question must include `source_note` and `source_ref`. Use graceful degradation:

```json
{ "type": "block", "value": "path/to/note.md#^block-id" }
{ "type": "heading", "value": "path/to/note.md#Heading" }
{ "type": "excerpt", "value": "short quoted or paraphrased source clue" }
```

Prefer `block`, then `heading`, then `excerpt`. Keep excerpts short (normally ≤30 Chinese characters or equivalent) and only for orientation.

### 6. Write `_retrieval/<topic>/index.md`

Include:

- frontmatter: `type`, `topic`, `created`, `updated`, `sources`, `source_profile`, `maturity`, `last_reviewed`.
- source wikilinks.
- test scope, themes, usage instructions.
- one fenced `quiz-json` block containing valid JSON.
- review record table and wrong-answer archive.

The JSON should include `title`, `topic`, `sources`, `source_profile`, `scope`, `themes`, and `questions`.

### 7. Build `quiz.html`

Run the bundled command from the vault or pass `--vault`:

```bash
/Users/wuzhigang/Code/bradenwu/tl-skills/tl-retrieval-quiz/scripts/quiz <topic> --no-open
```

The command extracts the `quiz-json` block, injects it into `assets/retrieval_quiz_template.html`, escapes `</script>`, writes `_retrieval/<topic>/quiz.html`, and optionally opens it.

### 8. Validate

- `index.md` exists.
- quiz JSON parses with `python3 -m json.tool` if Python is available.
- `quiz.html` exists and starts with the auto-generated warning.
- The HTML is a build artifact; if content changes, rebuild from `index.md`.
- Source notes remain unchanged unless explicitly requested.

## 9. Archive attempts（作答记录归并）

`quiz.html` 在浏览器沙箱内无法直接写回 vault，提交后提供三个出口：

- **① 复习记录行**：一行 Markdown，粘贴进 `index.md` 的「复习记录」表。
- **② 完整作答存档**：含逐题速览表 + 错题/主观题的「你的答案 / 正确答案 / 解析 / 来源」，可复制或下载为 `.md`。
- **下载存档 `.md`**：文件名 `<topic>-attempt-YYYY-MM-DD-HHMM.md`，落到下载目录。

约定回写流程：

1. 用户把下载的存档放进 `_retrieval/<topic>/attempts/`（首次由 agent 创建该目录）。
2. 用户下次让 agent 归并时：读取 `attempts/` 下未归并的存档，把「复习记录行」追加进 `## 复习记录` 表，把反复出错的主题/题目摘要追加进 `## 错题档案`，并更新 frontmatter 的 `last_reviewed`。
3. 归并后可在存档文件名前加 `_merged-` 前缀或移动到 `attempts/merged/`，避免重复归并。
4. 不要篡改用户在主观题里写的原文；归并时原样引用。

提交后 `quiz.html` 不再清空 localStorage 草稿（刷新仍可见上次作答）；只有点「重做」才清空。

## `index.md` skeleton

````markdown
---
type: retrieval-quiz
topic: <topic>
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "path/to/source.md"
source_profile:
  type: mixed
  overwrite_risk: low
  ref_granularity: heading
  progress: ""
maturity: developing
last_reviewed: ""
---

# <topic>：检索巩固

## 源文件
- [[path/to/source|source title]]

## 测试范围
- **主题**：...
- **包含**：...
- **不包含**：...
- **依据**：...

## 核心主题
1. ...

## 答题
- 终端：`quiz <topic>`
- HTML：[[quiz.html]]

## 题目数据
```quiz-json
{
  "title": "<topic>：检索巩固测验",
  "topic": "<topic>",
  "questions": []
}
```

## 复习记录
| 日期 | 得分 | 错题主题 | 下一步 |
|---|---:|---|---|

## 错题档案
<!-- agent may append recurring wrong answers here -->
````
