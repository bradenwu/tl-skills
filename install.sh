#!/bin/bash
# tl-skills 安装脚本
# 用法: ./install.sh [skill-name]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.openclaw/workspace/skills"
BIN_DIR="/usr/local/bin"

# 如果指定了技能名，只安装该技能
if [ -n "$1" ]; then
    SKILLS=("$1")
else
    # 安装所有技能
    SKILLS=()
    for dir in "$SCRIPT_DIR"/*/; do
        if [ -f "$dir/SKILL.md" ]; then
            SKILLS+=("$(basename "$dir")")
        fi
    done
fi

echo "🦞 tl-skills 安装器"
echo "==================="
echo ""

for skill in "${SKILLS[@]}"; do
    SKILL_DIR="$SCRIPT_DIR/$skill"
    
    if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
        echo "❌ 跳过 $skill: SKILL.md 不存在"
        continue
    fi
    
    echo "📦 安装 $skill..."
    
    # 创建目标目录
    mkdir -p "$SKILLS_DIR/$skill"
    
    # 复制技能文件
    cp -r "$SKILL_DIR"/* "$SKILLS_DIR/$skill/"
    
    # 如果有可执行脚本，创建符号链接
    if [ -f "$SKILL_DIR/$skill.sh" ]; then
        chmod +x "$SKILLS_DIR/$skill/$skill.sh"
        sudo ln -sf "$SKILLS_DIR/$skill/$skill.sh" "$BIN_DIR/$skill"
        echo "   ✅ 命令已链接: $skill"
    fi
    
    echo "   ✅ $skill 安装完成"
done

echo ""
echo "✨ 安装完成！"
