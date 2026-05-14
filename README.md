# 🦞 OpenClaw Evolved — 全量进化备份

> 仓库：`Fabio99999999/openclaw-evolved-invoice`
> 版本：v2.0 · 2026-05-14

## 📌 概述

OpenClaw 进化版备份。不同于默认 OpenClaw 发行版的所有定制化开发、技能增强和系统配置。

---

## 🏗️ 目录结构

```
openclaw-evolved-invoice/
├── workspace/                    # OpenClaw 工作区配置（进化版）
│   ├── AGENTS.md                 # 助手行为准则（5级搜索规则 v2）
│   ├── SOUL.md                   # AI人格定义
│   ├── USER.md                   # 用户画像
│   ├── IDENTITY.md               # 身份定义
│   ├── MEMORY.md                 # 长期记忆（结构化 v26）
│   ├── CHECKPOINT.md             # 当前工作检查点
│   ├── HEARTBEAT.md              # 心跳检查规则
│   ├── SEARCH_RULES.md           # 5级搜索优先级规则
│   └── TOOLS.md                  # 本地工具配置
│
├── skills/                       # 可复用技能包
│   ├── multi-agent-trader/       # ⭐ AI多Agent协同交易系统（核心进化）
│   ├── a-stock-trading/          # A股实时行情+分时量能分析
│   ├── email-assistant/          # 多邮箱管理助手（Gmail/163/QQ/Outlook）
│   ├── openclaw-dashboard/       # 可视化运营面板
│   ├── openclaw-control-center/  # 控制中心
│   ├── proactivity/              # 主动代理行为系统
│   ├── self-improving-agent/     # 自我进化代理
│   ├── xiucheng-self-improving-agent/ # 修正版自我进化
│   ├── skill-finder-cn/          # 中文Skill查找器
│   ├── skill-hunter/             # Skill搜索和评估
│   ├── skill-vetter/             # Skill安全审查
│   ├── skill-discovery/          # Skill发现
│   ├── agent-browser-clawdbot/   # 浏览器自动化
│   ├── anspire-search/           # 实时搜索
│   ├── delegate-task/            # 任务委派
│   ├── humanizer/                # 文本人性化
│   ├── memory-setup/             # 记忆系统配置
│   └── web-content-fetcher-hanya/ # 网页内容抓取
│
├── scripts/                      # 量化交易系统（全流程）
│   ├── market_monitor.py         # 市场情绪监控（7维）
│   ├── margin_monitor.py         # 融资融券监控
│   ├── factor_engine.py          # 因子引擎（文献因子）
│   ├── factor_mining.py          # 因子挖掘
│   ├── factor_validator.py       # 因子验证
│   ├── factor_auto_gen.py        # 因子自动生成
│   ├── quant_optimizer.py        # 量化优化器入口
│   ├── quant_models.py           # 量化模型
│   ├── backtest_engine.py        # 回测引擎
│   ├── data_cache.py             # 数据缓存
│   ├── simulation.py             # 模拟交易
│   ├── performance_attribution.py # 绩效归因
│   ├── adversarial_train.py      # 对抗训练
│   ├── vwap_executor.py          # VWAP执行
│   ├── trading_optimizer_integration.py # 优化器集成
│   ├── upgrade-repair.py         # 系统升级修复
│   ├── mlx-server-wrapper.py     # MLX服务封装
│   ├── snapshot_state.py         # 状态快照
│   └── MONITORING_DIMENSIONS.md  # 监控维度文档
│
├── backups/                      # 关键备份
│   ├── evolved-v0.2-20260512_1032.tar.gz  # v0.2完整备份
│   └── multi-agent-trader-20260513_0024/   # 交易系统专项备份
│
├── openclaw.json                 # OpenClaw 配置（已脱敏）
├── install.sh                    # 一键安装脚本
└── README.md                     # 本文件
```

---

## ⭐ 核心进化亮点

### 1. Multi-Agent Trader（AI交易系统）
4 Agent（技术/情报/风险/决策）+ 11 YAML策略管线，全自动盘中监控+收盘报告。

### 2. A股量化交易系统
FaceCat + efinance 多数据源融合，文献因子（量价背离/VWAP/布林带/ATR）实时计算。

### 3. 7维市场情绪监控
大盘情绪、融资融券、涨跌家数、板块异动、文献因子、量能信号、策略引擎匹配。

### 4. 自我进化框架
Self-Improving Agent + Proactivity 系统，从错误中学习，主动维护。

### 5. 可视化运营
OpenClaw Dashboard + Control Center 双面板监控系统状态。

---

## 🚀 部署

```bash
# 1. 克隆
git clone https://github.com/Fabio99999999/openclaw-evolved-invoice.git
cd openclaw-evolved-invoice

# 2. 安装依赖
chmod +x install.sh && ./install.sh

# 3. 配置凭据（参考 .env.example）
```

---

## 🔒 安全

- 所有 API Key / 令牌已在配置文件中脱敏
- 凭据文件不纳入版本控制
- 参见 [SECURITY.md](skills/openclaw-dashboard/SECURITY.md)

---

## 📜 历史

| 版本 | 日期 | 内容 |
|------|------|------|
| v1.0 | 04-28 | 初版：发票自动化一键安装包 |
| v2.0 | 05-14 | 全量进化备份：交易系统+AI Agent+监控系统 |
| ~ | ~ | 持续进化中... |
