# MEMORY.md — 长期记忆（结构化版）

> 版本: 1 | 发票自动化专用 | 上次更新: 2026-04-28

---

## ▎核心能力

- **进化版 OpenClaw**：已集成了企业级 AI 助手所需的进化特性
  - 智能记忆管理、会话恢复、心跳主动检查
  - 多层模型 fallback、预算控制、速率限制
  - 技能驱动的能力扩展
- **发票自动化能力**：
  - OCR 文字识别（支持中英文发票）
  - 发票结构化数据提取
  - 多格式支持（PDF/图片/JPG/PNG）
  - 自动归档与报表生成

---

## ▎系统配置

```json
{
  "config_version": 1,
  "cost_daily_max": 3,
  "cost_monthly_max": 50,
  "models": {
    "primary": "deepseek/deepseek-chat",
    "fallback": "deepseek/deepseek-reasoner"
  }
}
```

---

> 此文件将随着你对发票自动化系统的使用而持续更新。
> 新用户请先填写 USER.md，让 AI 了解你的具体需求。
