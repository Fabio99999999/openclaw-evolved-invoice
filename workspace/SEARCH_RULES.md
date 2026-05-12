# SEARCH_RULES.md — 5级主动回忆搜索规则

## 核心原则

用户提的事想不起 → 立即多路搜索 → 找到后直接答。

1. ❌ 不反问用户细节
2. ✅ 并行搜索全部信息源

## 5级搜索优先级

| 级别 | 搜索源 | 时机 |
|------|--------|------|
| L1 | MEMORY.md + memory/*.md | 每次启动 |
| L2 | 当前会话历史 | 启动恢复 |
| L3 | `memory_search` (语义搜索) | L1不够时 |
| L4 | `ls -t agents/main/sessions/*.trajectory.jsonl \| head -2` -> grep | L3不够时 |
| L5 | 配置文件 ~/.openclaw/openclaw.json | 配置/系统问题 |

搜索优先级依次递进，搜到即停，不搜索所有级别。
