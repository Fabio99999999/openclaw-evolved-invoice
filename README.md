# 🦞 OpenClaw 进化版 v0.2

> 基于 OpenClaw 深度进化配置 — 从 **发票自动化** 到 **全能办公助手**。
> 开箱即用，3 分钟部署。

## ✨ v0.2 升级亮点

| 变化 | 详情 |
|------|------|
| 🔄 **AGENTS.md 精简 43%** | 更高效的会话初始化，去冗余规则 |
| 🔍 **5 级主动回忆搜索** | SEARCH_RULES.md 独立模块，召回更快 |
| 🧠 **自我进化能力** | 新增 proactivity + self-improving-agent 技能 |
| 📊 **可视化控制台** | 新增 openclaw-control-center、openclaw-dashboard |
| 🔧 **技能扩容 16→22** | 更多通用技能，满足办公自动化全场景 |
| ⚡ **配置优化** | 双模型链 (DeepSeek + 备选)，成本可控 |
| 🔒 **安全加固** | 更严格的安全准则和权限控制 |

## 特点

- 🧠 **进化版人格系统** — SOUL.md + AGENTS.md 行为框架，比你见过的 AI 助手聪明一个档次
- 📄 **发票自动化就绪** — OCR、验证、归档、报表一站搞定
- 🔧 **技能驱动** — 16+ 精选预装技能，按需扩展
- 💰 **成本优化** — 默认 DeepSeek Chat 轻量模型，发票任务月费 < $3
- 🚀 **3分钟部署** — 跑个脚本就完事

## 一键安装

```bash
# 1. 克隆
git clone https://github.com/Fabio99999999/openclaw-evolved-invoice.git
cd openclaw-evolved-invoice

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 3. 一键安装
chmod +x install.sh
./install.sh
```

**脚本会自动：**
1. 安装 OpenClaw
2. 部署进化后的 workspace（人格、规则、技能）
3. 生成配置文件
4. 启动服务

安装完成后访问 **http://localhost:3100** 即可开始使用。

## 内含技能

| 技能 | 用途 |
|------|------|
| `web-content-fetcher` | 提取网页/文档内容 |
| `email-assistant` | 邮件发票抓取 |
| `agent-browser` | 浏览器自动化（税局网站） |
| `anspire-search` | 实时搜索税务信息 |
| `skill-finder-cn` | 中文技能搜索 |
| `skill-hunter` | 发现更多技能 |
| `skill-vetter` | 技能安全检查 |
| `delegate-task` | 委派复杂任务 |
| `humanizer` | 文字润色 |
| `memory-setup` | 记忆管理 |
| `openclaw-control-center` | 系统控制台 |
| `openclaw-dashboard` | 运行监控面板 |
| `proactivity` | 主动式 AI |
| `self-improving-agent` | 自我进化能力 |
| `skill-discovery` | 技能发现 |

## 目录结构

```
openclaw-evolved-invoice/
├── install.sh              ← 一键安装脚本
├── .env.example            ← API Key 模板
├── .gitignore              ← 安全过滤
├── workspace/              ← 进化版人格/规则/配置
│   ├── SOUL.md             ← 你的灵魂
│   ├── AGENTS.md           ← 行为规则（精简版）
│   ├── SEARCH_RULES.md     ← 5级主动回忆搜索
│   ├── IDENTITY.md         ← 你的名字
│   ├── USER.md             ← 用户信息（需填写）
│   ├── TOOLS.md            ← 工具笔记
│   ├── HEARTBEAT.md        ← 主动检查项
│   ├── CHECKPOINT.md       ← 工作进度
│   └── MEMORY.md           ← 长期记忆
├── skills/                 ← 预装技能（22个）
└── README.md               ← 本文件
```

## 发票自动化快速上手

安装完成后，在 WebChat 中直接说：

| 指令 | 效果 |
|------|------|
| "帮我设置发票处理目录" | 配置发票输入/输出文件夹 |
| "扫描这张发票" | 上传图片 → OCR → 提取结构化数据 |
| "创建发票归档任务" | 配置 cron 定时处理 |
| "生成本月发票报表" | 自动统计并生成报表 |
| "把发票录入金蝶" | 对接财务系统（需配置 API） |

## 从 v0.1 升级

如果已安装 v0.1：

```bash
git pull origin main
./install.sh
# 或者手动复制 workspace/ 目录覆盖
cp -r workspace ~/.openclaw/
```

## 自定义

1. 编辑 `~/.openclaw/workspace/USER.md` — 告诉 AI 你是谁
2. 编辑 `~/.openclaw/workspace/SOUL.md` — 调整 AI 的性格
3. 在 WebChat 中直接说 "帮我安装 XX 技能" 扩展能力

## 需要更多？

- [OpenClaw 官方文档](https://docs.openclaw.ai)
- [技能市场 ClawHub](https://clawhub.ai)
- 有问题直接在 WebChat 里问 AI 就行 😄

---

**Made with ❤️ by OpenClaw 进化版 | v0.2**
