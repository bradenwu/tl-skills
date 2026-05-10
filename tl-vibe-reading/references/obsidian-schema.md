# Obsidian record schema

Default root: `深度阅读/vibe-reading/`.

Project folder naming:
`YYYY-MM-DD-short-title`, with spaces converted to hyphens when convenient. Keep Chinese titles readable.

Default frontmatter for project files:

```yaml
---
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
type: vibe-reading
stage: map|aim|match|prioritize|intake|compress|feynman|index|source|backlog|critic-log|final-summary
status: todo|active|ongoing|done|skipped
source_title: ""
tags:
  - deep-reading
  - vibe-reading
---
```

`index.md` should be the control panel and link all files with Obsidian wikilinks.

Status labels:
- `todo`: created but not meaningfully filled
- `active`: currently being worked on
- `ongoing`: a continuously maintained file such as `backlog.md` or `critic-log.md`
- `done`: usable result exists
- `skipped`: intentionally skipped

When editing a vault, use relative paths. Do not write absolute iCloud paths into notes.
