#!/bin/bash
# tl-skills 安装脚本
# 用法:
#   ./install.sh              # 安装所有 skills
#   ./install.sh <skill-name> # 只安装指定 skill
#
# 安装链路（三层）:
#   git repo → ~/.agents/skills/<skill>  (hub 层，绝对链接)
#              └→ ~/.claude/skills/<skill>  (相对链接，../../.agents/skills/<name>)
#              └→ ~/.codex/skills/<skill>   (相对链接，../../.agents/skills/<name>)
#   cursor-rule.mdc → ~/.cursor/rules/<skill>.mdc (绝对链接)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

AGENTS_HUB="$HOME/.agents/skills"
CLAUDE_SKILLS="$HOME/.claude/skills"
CODEX_SKILLS="$HOME/.codex/skills"
CURSOR_RULES="$HOME/.cursor/rules"

# hub 层是必需的
if [ ! -d "$AGENTS_HUB" ]; then
    echo "❌ ~/.agents/skills 不存在，请先安装 agent-skills 支持"
    exit 1
fi

# ── 收集要安装的 skill 列表 ──────────────────────────────────────
if [ -n "$1" ]; then
    SKILLS=("$1")
else
    SKILLS=()
    for dir in "$SCRIPT_DIR"/*/; do
        if [ -f "$dir/SKILL.md" ]; then
            SKILLS+=("$(basename "$dir")")
        fi
    done
fi

echo "tl-skills 安装器"
echo "================"
echo "Hub:    $AGENTS_HUB"
[ -d "$CLAUDE_SKILLS" ] && echo "Claude: $CLAUDE_SKILLS"
[ -d "$CODEX_SKILLS"  ] && echo "Codex:  $CODEX_SKILLS"
[ -d "$CURSOR_RULES"  ] && echo "Cursor: $CURSOR_RULES"
echo ""

# ── 安装每个 skill ───────────────────────────────────────────────
for skill in "${SKILLS[@]}"; do
    SKILL_SRC="$SCRIPT_DIR/$skill"

    if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
        echo "⚠️  跳过 $skill: SKILL.md 不存在"
        continue
    fi

    echo "🔗 $skill"

    # 层 1: hub — 绝对链接指向 git repo
    hub_link="$AGENTS_HUB/$skill"
    [ -e "$hub_link" ] || [ -L "$hub_link" ] && rm -rf "$hub_link"
    ln -sf "$SKILL_SRC" "$hub_link"
    echo "   ✅ hub:    $hub_link → $SKILL_SRC"

    # 层 2: Claude Code — 相对链接指向 hub（匹配既有约定）
    if [ -d "$CLAUDE_SKILLS" ]; then
        claude_link="$CLAUDE_SKILLS/$skill"
        [ -e "$claude_link" ] || [ -L "$claude_link" ] && rm -rf "$claude_link"
        ln -sf "../../.agents/skills/$skill" "$claude_link"
        echo "   ✅ claude: $claude_link"
    fi

    # 层 2: Codex — 相对链接指向 hub
    if [ -d "$CODEX_SKILLS" ]; then
        codex_link="$CODEX_SKILLS/$skill"
        [ -e "$codex_link" ] || [ -L "$codex_link" ] && rm -rf "$codex_link"
        ln -sf "../../.agents/skills/$skill" "$codex_link"
        echo "   ✅ codex:  $codex_link"
    fi

    # Cursor — 单独处理，格式不同（.mdc 单文件）
    if [ -d "$CURSOR_RULES" ] && [ -f "$SKILL_SRC/cursor-rule.mdc" ]; then
        cursor_link="$CURSOR_RULES/$skill.mdc"
        [ -e "$cursor_link" ] || [ -L "$cursor_link" ] && rm -f "$cursor_link"
        ln -sf "$SKILL_SRC/cursor-rule.mdc" "$cursor_link"
        echo "   ✅ cursor: $cursor_link"
    fi
done

echo ""
echo "✨ 完成！修改 $SCRIPT_DIR 下的文件会立即生效，无需重新安装。"
