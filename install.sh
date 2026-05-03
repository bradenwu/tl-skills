#!/bin/bash
# tl-skills 安装脚本
# 用法:
#   ./install.sh              # 安装所有 skills 到所有检测到的工具
#   ./install.sh <skill-name> # 只安装指定 skill

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 检测已安装的工具，构建目标目录列表 ──────────────────────────
TARGETS=()

if [ -d "$HOME/.claude/skills" ]; then
    TARGETS+=("$HOME/.claude/skills")
fi

if [ -d "$HOME/.codex/skills" ]; then
    TARGETS+=("$HOME/.codex/skills")
fi

# Cursor: 单独处理，因为格式不同（.mdc 而非目录软链接）
CURSOR_RULES_DIR=""
if [ -d "$HOME/.cursor/rules" ]; then
    CURSOR_RULES_DIR="$HOME/.cursor/rules"
fi

if [ ${#TARGETS[@]} -eq 0 ] && [ -z "$CURSOR_RULES_DIR" ]; then
    echo "❌ 未找到支持的工具（Claude Code / Codex / Cursor）"
    echo "   请确认以下任一目录存在："
    echo "   ~/.claude/skills  ~/.codex/skills  ~/.cursor/rules"
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
echo "目标工具:"
for target in "${TARGETS[@]}"; do
    echo "  → $target"
done
[ -n "$CURSOR_RULES_DIR" ] && echo "  → $CURSOR_RULES_DIR (Cursor rules)"
echo ""

# ── 为每个 skill 创建软链接 ──────────────────────────────────────
for skill in "${SKILLS[@]}"; do
    SKILL_SRC="$SCRIPT_DIR/$skill"

    if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
        echo "⚠️  跳过 $skill: SKILL.md 不存在"
        continue
    fi

    echo "🔗 $skill"

    # Claude Code / Codex：软链接整个目录
    for target_dir in "${TARGETS[@]}"; do
        link="$target_dir/$skill"
        if [ -e "$link" ] || [ -L "$link" ]; then
            rm -rf "$link"
        fi
        ln -sf "$SKILL_SRC" "$link"
        echo "   ✅ $(basename $target_dir): $link"
    done

    # Cursor：软链接 cursor-rule.mdc（格式不同，单独处理）
    if [ -n "$CURSOR_RULES_DIR" ] && [ -f "$SKILL_SRC/cursor-rule.mdc" ]; then
        cursor_link="$CURSOR_RULES_DIR/$skill.mdc"
        if [ -e "$cursor_link" ] || [ -L "$cursor_link" ]; then
            rm -f "$cursor_link"
        fi
        ln -sf "$SKILL_SRC/cursor-rule.mdc" "$cursor_link"
        echo "   ✅ cursor/rules: $cursor_link"
    fi
done

echo ""
echo "✨ 完成！修改 $SCRIPT_DIR 下的文件会立即生效，无需重新安装。"
