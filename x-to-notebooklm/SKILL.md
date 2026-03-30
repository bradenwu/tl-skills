---
name: x-to-notebooklm
description: >
  Fetch X/Twitter post content and upload to NotebookLM with auto-generated audio and video.
  Use when the user provides an x.com or twitter.com URL and wants to import it into NotebookLM,
  or says phrases like "把这条推文导入NotebookLM", "把这个X帖子生成播客/视频".
---

# X to NotebookLM

Import X/Twitter posts to NotebookLM and generate audio + video.

## Usage

Run the bundled script:

```bash
bash scripts/x2nb.sh "<x.com_url>"
```

### Parameters

- **URL** (required): x.com or twitter.com post URL

### Examples

```bash
bash scripts/x2nb.sh "https://x.com/user/status/123456"
```

## How It Works

1. Validate URL is from x.com/twitter.com
2. Fetch content via `https://r.jina.ai/<URL>` (Jina Reader → Markdown)
3. Save content as temp file
4. Create NotebookLM notebook
5. Upload content as source
6. Trigger audio generation
7. Trigger video generation

## Check Generation Status

Audio and video take 3-8 minutes. Check with:

```bash
notebooklm artifact list
notebooklm artifact wait <task_id>
```

## Dependencies

- `notebooklm` CLI (pip install git+https://github.com/teng-lin/notebooklm-py.git)
- `curl`
- NotebookLM authentication (`notebooklm login`)
