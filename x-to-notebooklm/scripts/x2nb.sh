#!/usr/bin/env bash
# x-to-notebooklm: Fetch X/Twitter post via Jina, upload to NotebookLM, generate audio + video
set -euo pipefail

URL="${1:?Usage: x2nb.sh <x.com URL> [notebook_title]}"

# Validate URL is x.com or twitter.com
if [[ "$URL" != *"x.com/"* ]] && [[ "$URL" != *"twitter.com/"* ]]; then
  echo "❌ Error: URL must be from x.com or twitter.com" >&2
  exit 1
fi

TITLE="${2:-X Post $(date +%Y%m%d_%H%M%S)}"
JINA_URL="https://r.jina.ai/${URL}"
TMPFILE="/tmp/x2nb_${RANDOM}.txt"

echo "📥 Fetching content via Jina..."
curl -sfS "$JINA_URL" -o "$TMPFILE"
echo "✅ Content saved to $TMPFILE ($(wc -c < "$TMPFILE") bytes)"

echo "📓 Creating notebook: $TITLE"
NB_OUTPUT=$(notebooklm create "$TITLE" 2>&1)
NB_ID=$(echo "$NB_OUTPUT" | grep -oP 'Created notebook: \K[a-f0-9-]+')
if [[ -z "$NB_ID" ]]; then
  echo "❌ Failed to create notebook" >&2
  echo "$NB_OUTPUT" >&2
  exit 1
fi
echo "✅ Notebook: $NB_ID"

echo "📎 Setting notebook context..."
notebooklm use "$NB_ID" >/dev/null 2>&1

echo "📤 Uploading source..."
notebooklm source add "$TMPFILE" 2>&1

# Wait for source processing
echo "⏳ Waiting for source to be processed..."
sleep 10

echo "🎵 Generating audio..."
AUDIO_OUT=$(notebooklm generate audio 2>&1)
AUDIO_TASK=$(echo "$AUDIO_OUT" | grep -oP 'Started: \K[a-f0-9-]+')
if [[ -n "$AUDIO_TASK" ]]; then
  echo "✅ Audio task started: $AUDIO_TASK"
else
  echo "⚠️ Audio generation: $AUDIO_OUT"
fi

echo "🎬 Generating video..."
VIDEO_OUT=$(notebooklm generate video 2>&1)
VIDEO_TASK=$(echo "$VIDEO_OUT" | grep -oP 'Started: \K[a-f0-9-]+')
if [[ -n "$VIDEO_TASK" ]]; then
  echo "✅ Video task started: $VIDEO_TASK"
else
  echo "⚠️ Video generation: $VIDEO_OUT"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Done! Notebook: $TITLE"
echo "📋 Notebook ID: $NB_ID"
if [[ -n "$AUDIO_TASK" ]]; then echo "🎵 Audio task: $AUDIO_TASK"; fi
if [[ -n "$VIDEO_TASK" ]]; then echo "🎬 Video task: $VIDEO_TASK"; fi
echo ""
echo "Check status with:"
echo "  notebooklm artifact list"
echo "  notebooklm artifact wait <task_id>"
