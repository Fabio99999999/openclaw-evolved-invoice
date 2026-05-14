# SEARCH_RULES.md — 主动回忆搜索规则

> 被 AGENTS.md 引用。仅在需要回忆时加载此文件。

## 核心原则

用户提到某件事想不起时 → **立即多路搜索** → 找到后直接答。

1. ❌ 永不直接说"不记得"
2. ❌ 永不反问用户细节（"什么记录？""你说的是哪个？"一律禁止）
3. ✅ **立即** 并行搜索全部信息源
4. ✅ 找到后直接回答，不解释"我刚搜到的"

## 5级搜索优先级

逐级推进，不行就下一级，**不要在一个级别卡住超过3秒**。

### Level 0 — 自身运行时（最快，0秒）
- `available_skills` 列表 — 先看技能列表有没有
- 当前启用的 Tools 列表 — 能做什么事
- 环境变量中 API Key 的配置情况

### Level 1 — memory 文件（< 1秒）
- `memory/*.md` 日志
- `MEMORY.md` 长期记忆
- `CHECKPOINT.md` 当前状态

### Level 2 — 会话历史（1-5秒）
- `agents/main/sessions/*.trajectory.jsonl` — grep 搜索
- `context-snapshots/*/session-snapshot.jsonl` — 上下文快照

### Level 3 — 文件系统状态（1-5秒）
- `skills/` 目录 — 安装了哪些技能
- `scripts/` 目录 — 有哪些脚本工具
- `extensions/` 目录 — 有哪些扩展
- `TOOLS.md` — 工具配置笔记

### Level 4 — 系统配置（3-10秒）
- `openclaw.json` — plugins.allow, providers, secrets
- `.zshrc` / `.bashrc` — 持久化环境变量
- `subagents/runs.json` — 子代理运行记录

## 底线

你问一个关键词，我带着答案回复，不是带着问题回复。
问几次问题就 push 搜索级别。Level 0 没搜到？立刻 Level 1。Memory 文件没有？立刻 Level 2-3-4 顺着来。
