#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ROOT="${TL_DAILY_REVIEW_RUNTIME_ROOT:-$HOME/.codex/runtime/tl-daily-review}"
VAULT_ROOT="${TL_DAILY_REVIEW_VAULT_ROOT:-/Users/wuzhigang/Library/Mobile Documents/iCloud~md~obsidian/Documents/icloud-ob}"
ALLOWLIST_PATH="${TL_DAILY_REVIEW_ALLOWLIST:-$SKILL_DIR/repo_allowlist.txt}"
SCRIPT="$SKILL_DIR/scripts/daily_review_collect.py"

log() {
  printf '[tl-daily-review][%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" >&2
}

log_block() {
  local title="$1"
  shift || true
  log "$title"
  while [ "$#" -gt 0 ]; do
    log "  $1"
    shift
  done
}

mkdir -p "$RUNTIME_ROOT/reports" "$RUNTIME_ROOT/state" "$RUNTIME_ROOT/staging/NotebookLM"

export TL_DAILY_REVIEW_RUNTIME_ROOT="$RUNTIME_ROOT"
export TL_DAILY_REVIEW_VAULT_ROOT="$VAULT_ROOT"
export TL_DAILY_REVIEW_ALLOWLIST="$ALLOWLIST_PATH"
export TL_DAILY_REVIEW_GH_CONFIG_DIR="${TL_DAILY_REVIEW_GH_CONFIG_DIR:-$HOME/.config/gh}"

# Pin gh to the user's stable config/keychain path and ignore transient token env
# overrides that may be injected by the automation host.
unset GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN
unset XDG_CONFIG_HOME
export GH_CONFIG_DIR="$TL_DAILY_REVIEW_GH_CONFIG_DIR"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
unset http_proxy https_proxy all_proxy
unset NO_PROXY no_proxy

log "启动；runtime=$RUNTIME_ROOT vault=$VAULT_ROOT gh_config=$GH_CONFIG_DIR"
log "开始执行采集脚本：$SCRIPT"
python3 "$SCRIPT"
