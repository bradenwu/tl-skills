# TL Skills

Braden 的个人技能收集仓库。

---

## 技能列表

### think - 10大心智模型思维教练

基于顶级心智模型的思维教练技能，支持分析、复盘、引导三种模式。

**模型库：**
1. 第一性原理 - 从底层事实重新推导
2. 逆向思维 - 想想怎么输，然后避开
3. 二阶思维 - 问「然后呢」看深层后果
4. 复利效应 - 每天做一点，一年后怎样
5. 奥卡姆剃刀 - 最简单的解释是什么
6. 帕累托法则 - 找那 20% 关键的事
7. 能力圈 - 这事我真懂吗
8. 贝叶斯更新 - 新证据来了怎么修正
9. 反脆弱 - 最坏情况能活吗
10. 地图≠疆域 - 计划和现实还对得上吗

**使用方法：**
```bash
think "我最近在纠结要不要跳槽，帮我分析一下"
think "用逆向思维帮我想想创业可能踩的坑"
think "我上个月做了一个失败的投资决策，帮我复盘"
```

---

## 安装方法

```bash
# 克隆仓库
git clone https://github.com/bradenwu/tl-skills.git

# 安装所有技能
cd tl-skills
chmod +x install.sh
./install.sh

# 或安装单个技能
./install.sh think
```

---

## 项目结构

```
tl-skills/
├── install.sh          # 安装脚本
├── README.md           # 项目说明
└── think/              # think 技能
    ├── SKILL.md        # 技能定义（YAML frontmatter + Markdown）
    └── think.sh        # 命令行入口
```
