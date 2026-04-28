# 🦞 OpenClaw 进化版 — 发票自动化专用

> 基于 OpenClaw 深度进化配置，专为 **发票自动化** 场景优化。
> 开箱即用，无需从零搭建。

## 特点

- 🧠 **进化版人格系统** — SOUL.md + AGENTS.md 行为框架，比你见过的 AI 助手聪明一个档次
- 📄 **发票自动化就绪** — OCR、验证、归档、报表一站搞定
- 🔧 **技能驱动** — 10+ 精选预装技能，按需扩展
- 💰 **成本优化** — 默认 DeepSeek Chat 轻量模型，发票任务月费 < $3
- 🚀 **3分钟部署** — 跑个脚本就完事

## 一键安装

```bash
# 1. 克隆
git clone https://github.com/你的用户名/openclaw-evolved-invoice.git
cd openclaw-evolved-invoice

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 3. 一键安装
chmod +x install.sh
./install.sh
```

**就这么简单。** 脚本会自动：
1. 安装 OpenClaw
2. 部署进化后的 workspace（人格、规则、技能）
3. 生成配置文件
4. 启动服务

安装完成后访问 **http://localhost:3100** 即可开始使用。

## 手动安装（3 步）

如果不想用一键脚本：

```bash
# 1. 安装 OpenClaw
npm install -g openclaw

# 2. 复制配置文件
cp -r workspace ~/.openclaw/
cp .env ~/.openclaw/

# 3. 启动
openclaw gateway start
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

**高级自动化场景：**

### 场景 1：邮件发票自动抓取
```bash
# 配置邮箱后，AI 会自动：
# 1. 定时检查邮件
# 2. 识别含发票附件的邮件
# 3. 下载 → OCR → 提取数据 → 归档
```

### 场景 2：批量发票 OCR
```bash
# 把发票图片丢到 ~/发票/待处理/
# AI 自动批量识别并输出到 ~/发票/已处理/
```

### 场景 3：税局网站自动化
```bash
# AI 通过浏览器自动化：
# 1. 登录税局网站
# 2. 批量验证发票真伪
# 3. 下载验证结果报表
```

## 内含技能

| 技能 | 用途 |
|------|------|
| `web-content-fetcher` | 提取网页/文档内容 |
| `email-assistant` | 邮件发票抓取 |
| `agent-browser` | 浏览器自动化（税局网站） |
| `anspire-search` | 实时搜索税务信息 |
| `skill-hunter` | 发现更多技能 |
| `delegate-task` | 委派复杂任务 |
| `humanizer` | 文字润色 |
| `memory-setup` | 记忆管理 |
| `skill-vetter` | 技能安全检查 |

## 目录结构

```
openclaw-evolved-invoice/
├── install.sh           ← 一键安装脚本
├── .env.example         ← API Key 模板
├── .gitignore           ← 安全过滤
├── workspace/           ← 进化版人格/规则/配置
│   ├── SOUL.md          ← 你的灵魂（发票助手版）
│   ├── AGENTS.md        ← 行为规则
│   ├── IDENTITY.md      ← 你的名字
│   ├── USER.md          ← 用户信息（需填写）
│   ├── TOOLS.md         ← 工具笔记
│   ├── HEARTBEAT.md     ← 主动检查项
│   └── MEMORY.md        ← 长期记忆
├── skills/              ← 预装技能
│   ├── email-assistant/
│   ├── web-content-fetcher/
│   ├── agent-browser/
│   └── ...
└── README.md            ← 本文件
```

## 从零开始自定义

1. 编辑 `~/.openclaw/workspace/USER.md` — 告诉 AI 你是谁
2. 编辑 `~/.openclaw/workspace/SOUL.md` — 调整 AI 的性格
3. 在 WebChat 中直接说 "帮我安装 XX 技能" 扩展能力

## 需要更多？

- [OpenClaw 官方文档](https://docs.openclaw.ai)
- [技能市场 ClawHub](https://clawhub.ai)
- 有问题直接在 WebChat 里问 AI 就行 😄
