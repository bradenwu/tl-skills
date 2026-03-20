#!/bin/bash
# Think Skill - 10大心智模型思维教练
# 用法: think "你的问题或决策场景"

PROMPT_FILE="$(dirname "$0")/SKILL.md"

if [ -z "$1" ]; then
    echo "🧠 Think Skill - 10大心智模型思维教练"
    echo ""
    echo "用法: think \"你的问题或决策场景\""
    echo ""
    echo "示例:"
    echo "  think \"我最近在纠结要不要跳槽，帮我分析一下\""
    echo "  think \"用逆向思维帮我想想创业可能踩的坑\""
    echo "  think \"我上个月做了一个失败的投资决策，帮我复盘\""
    echo ""
    echo "10大心智模型:"
    echo "  1. 第一性原理  - 从底层事实重新推导"
    echo "  2. 逆向思维    - 想想怎么输，然后避开"
    echo "  3. 二阶思维    - 问「然后呢」看深层后果"
    echo "  4. 复利效应    - 每天做一点，一年后怎样"
    echo "  5. 奥卡姆剃刀  - 最简单的解释是什么"
    echo "  6. 帕累托法则  - 找那 20% 关键的事"
    echo "  7. 能力圈      - 这事我真懂吗"
    echo "  8. 贝叶斯更新  - 新证据来了怎么修正"
    echo "  9. 反脆弱      - 最坏情况能活吗"
    echo "  10. 地图≠疆域  - 计划和现实还对得上吗"
    exit 0
fi

# 将用户输入和技能说明一起发送给 AI
echo "你是一位精通人类顶级心智模型的思维教练。请根据以下技能说明回答用户的问题。"
echo ""
echo "=== 技能说明 ==="
cat "$PROMPT_FILE"
echo ""
echo "=== 用户输入 ==="
echo "$1"
