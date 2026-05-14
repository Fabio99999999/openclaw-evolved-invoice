# MEMORY.md — 长期记忆（结构化版）

> 版本: 19 | autoDream 归纳 | 上次更新: 2026-05-12

---

## ▎用户信息

- **姓名**: 老板
- **职业**: 交易员，独立创业者
- **所在地**: 意大利
- **时区**: Europe/Rome (GMT+2)
- **沟通**: 飞书 + webchat
- **语言**: 中文为主，外文术语用外语

---

## ▎活跃项目

### 1. AI 量化交易系统 🏆（当前最高优先级）
**状态**: 战略转型中 — 从自研手搓转向「成熟平台 + AI 注入」
**成本**: ~$0.62/月
**⚠️ 5/11 重大回撤**: 国晟科技(-10%)、美诺华(-10%) 双双跌停，减仓未及时执行

**已完成** ✅
- 基础: a-stock-trading 技能 + analyze.py + portfolio.py，4个交易Cron
- 数据: FaceCat报价API（意大利直连）、efinance备选、Sina实时报价
- 面壁: FaceCat Kronos桌面版（PySide6+UI定制）、Qlib+LightGBM+RD-Agent macOS全循环
- 优化: 全流程6大方向代码落地（缓存/因子引擎/回测/对抗/归因/VWAP）
- 监控: margin_monitor + market_monitor + MONITORING_DIMENSIONS.md
- AGENTS.md: 5级主动回忆搜索规则升级
- ⚠️ 德龙汇能代码存疑: 600593 返回「大连圣亚」非德龙汇能，需核实

**技术约束**: FaceCat无PE/PB/换手率；efinance意大利部分超时；Qlib需Python3.12；RD-Agent macOS无Docker可直接跑

### 2. Claude Code 进化计划（已完成 ✅）
15 工具 + Provider Proxy + Coordinator Prompt，2026-04 完成，不再推进。

### 3. ACP 协议（待定）
P0 评估（~6-8h），待交易系统稳定后考虑。

### 4. 海外仓业务
调研阶段，无新进展。

### 5. OpenClaw 配置管理
deepseek 双模型 + 飞书渠道 + 三层恢复 + 智能压缩 v2.0。Provider Proxy (3457) 独立运行。GitHub: Fabio99999999/openclaw-evolved-invoice（公开）

### 6. OpenClaw 系统升级维护（2026-05-11 晚）🔥
**状态**: 5.2→5.7 升级完成，精简化+清理完成，4个skill安装待确认

**已完成** ✅
- OpenClaw 5.2 → 5.7 升级（Homebrew路径，无破坏性变更）
- 清理: 删除 extensions/openclaw-lark/(84MB) 和 extensions/openclaw-weixin/(45MB)
- AGENTS.md 精简化: 11,516→6,567 chars (-43%)
- 5级搜索规则移至 SEARCH_RULES.md（懒加载）
- Gateway 2026.5.7, 6 plugins running
- Doctor修复: bundledDiscovery, 101孤儿transcript, 43不可用skill禁用
- 46技能在线，用户0技能损失

**⚠️ 待确认**: 
- 23:37请求安装 clawhub/skill-finder-cn/tavily-search/peekaboo — 会话截断
- 已知: skill-finder-cn✓已在workspace, tavily✓已在plugins.allow
- 未确认: clawhub, peekaboo

---

## ▎关键决策（DeerFlow 结构化记忆）

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-04-24 | 模型从 GLM-5-Turbo → deepseek-reasoner | 推理质量 + 成本大幅降低 |
| 2026-04-24 | 三层会话恢复系统建立 | 防止消息丢失，crash 后快速恢复 |
| 2026-04-24 | cc-haha 进化停止 ~85% | 交易系统优先级更高 |
| 2026-04-25 | hermes-agent 进化延后 | 交易系统是唯一战场 |
| 2026-04-27 | DeerFlow 吸收 8 项全部执行 | 老板直接指定全吸收 |
| 2026-04-27 | efinance 首数据源定稿（后被 28/29 更新） | 意大利直连可用 |
| 2026-04-28 | AI Agent 全市场对比报告发布 | 覆盖 20+ 竞品，PDF 发飞书 |
| 2026-04-28 | **QVeris 全部移除** | 稳定性和可靠性考虑 |
| 2026-04-28 | **Gmail cron 禁用** | credentials.json 缺失，失败 20 次 |
| 2026-04-28 | **法尔胜清仓**，4 只新买入 | 实际调仓操作 |
| 2026-04-28/29 | **战略转型 → 成熟平台 + AI 注入** | Qlib 为首选，FaceCat-Kronos 为 wrapper |
| 2026-04-29 | **数据源切换 FaceCat 报价 API** | 意大利直连，完整 CSV 数据 |
| 2026-04-29 | FaceCat Kronos 桌面版搭建完成 | PySide6 + macOS 兼容，已部署 |
| 2026-04-29 | **Qlib 安装+LightGBM 训练完成** | pyqlib 0.9.7, CSI300, Alpha158, 13 rounds early stop |
| 2026-04-29 | **RD-Agent macOS 完整循环跑通** | 4 步循环，Baseline 年化 9.43%，超额 6.90% |
| 2026-04-29 | FaceCat→Qlib 数据管道搭建 | efinance→Qlib bin 格式，首批写入成功 |
| 2026-04-29 | **FaceCat Kronos UI 定制完成** | K 线颜色、涨停/跌停颜色、字体 16pt、分时按钮 |
| 2026-04-29 | **Local LLM (Ollama+Qwen 7B) 尝试失败** | M5 16GB 内存不足，Ollama 0.20.4 过旧 |
| 2026-05-04 | **6大优化方向全部代码落地** | quant_optimizer 全流程：缓存→因子→回测→对抗→归因→VWAP |
| 2026-05-04 | **AGENTS.md 主动回忆规则升级（第1轮）** | Session Recovery协议+永不反问 |
| 2026-05-04 | **五一后首日交易** | 全线回调（6/7跌），组合仍+18.07% |
| 2026-05-05 | **盘中监控全面升级** | margin_monitor+market_monitor+MONITORING_DIMENSIONS.md |
| 2026-05-06 | **AGENTS.md 搜索规则升级（第2轮）** | 5级搜索：运行时→memory→会话→文件系统→配置 |
| 2026-05-06 | **持仓轮换** — 圣龙/晓程入，众合/安诺其/华电辽能出 | 节后首日调仓，组合+14.1%
| 2026-05-07 | **天银机电-10.49%巨阴 + 美诺华跌停** | 持仓95%过高，建议减至70-80%
| 2026-05-08 | **组合+1.20%反弹(+¥771)，天银/美诺华/国晟集体修复** | 累计+26.11%，缩量新高，仓位95%仍过高
| 2026-05-11 | **国晟科技(-10%)、美诺华(-10%)双跌停，组合遭重大回撤** | 减仓建议(95%→70-80%)未及时执行；法尔胜-5.59%、天银-4.82%；发现600593代码对应大连圣亚非德龙汇能

---

## ▎事实图谱（Facts, confidence ≥ 0.6）


### 林克方法整合 (2026-05-05)
- ✅ 深度研究《高胜算操盘》马塞尔林克 (Marcel Link, High Probability Trading) ⭐⭐⭐
- ✅ 5大模块代码落地: facecat_data/entry_signals/stop_loss_optimizer/link_analyze
- ✅ 趋势分析器: 多时间框架 (日/周/月) 趋势评分 0-100
- ✅ 入场信号系统: 基于林克4大规则 (趋势50%/回调30%/RSI20%/量15%)
- ✅ 止损优化器: 4层止损 + ATR动态 + 跟踪止损 + 时间止损
- ✅ 仓位管理: 每笔风险1.5% + 单票上限20%
- ✅ 6份文件 + 1份研究报告
- ✅ link_analyze.py 统一入口, 全持仓测试通过

### 系统事实
- ✅ Agent 主模型: deepseek/deepseek-v4-flash (conf: 1.0)
- ✅ fallback: uiuiapi/deepseek-reasoner (conf: 1.0)
- ✅ Provider Proxy 服务运行中（端口 3457, Anthropic↔OpenAI 协议互转）(conf: 1.0)
- ✅ 飞书渠道配置完成，文件上传 & 发送 API 可用 (conf: 1.0)
- ✅ 智能压缩 v2.0: 含工具结果摘要化（Hermes 移植，已通过 6 项测试）(conf: 0.9)
- ✅ LoopDetector: 循环检测中间件已实现 (conf: 0.9)
- ✅ 6 个交易 cron 已更新（QVeris 移除）(conf: 1.0)
- ✅ OpenClaw-Evolved-Invoice GitHub 公开仓库 (conf: 1.0)
- ✅ **OpenClaw 已升级 5.2 → 5.7** (Homebrew路径, 2026-05-11) (conf: 1.0)
- ✅ **AGENTS.md 精简** 11,516→6,567 chars (-43%), 5级搜索规则移至 `SEARCH_RULES.md` (conf: 1.0)
- ✅ **46技能在线**, 用户技能0损失; 43个缺依赖内置skill被doctor自动禁用 (conf: 1.0)
- ✅ **Gateway 2026.5.7**, 6 plugins: deepseek, intelligent-compression, tavily, openclaw-lark, feishu, memory-core (conf: 1.0)
- ❌ Gmail cron 已禁用（缺 credentials.json）(conf: 1.0)
- ❌ QMD 内存后端未运行（待 embedding provider）(conf: 1.0)

### 数据源事实
- ✅ **FaceCat报价API** — 意大利直连，基础OHLC，无PE/PB/换手率 (conf: 1.0)
- ✅ **efinance** `get_quote_history()` 单股可用，日期YYYYMMDD，批量不稳定 (conf: 0.9)
- ✅ **新浪 hq.sinajs.cn** 实时报价意大利可用 (conf: 1.0)
- ❌ efinance `get_realtime_quotes()` 超时 / pytdx全超时 / akshare EastMoney API阻断 (conf: 1.0)
- ❌ 微信 ilink webchat无法往返确认 (conf: 1.0)

### 网页爬取工具链
- ✅ 完整链路: Anspire→web-content-fetcher(Scrapling/Jina)→agent-browser→Tavily (conf: 1.0)
- ✅ 策略: 搜→Anspire/Tavily；抓URL→Scrapling/Jina；复杂→agent-browser (conf: 1.0)

### 技术评估
- ✅ **量化全流程6大方向**代码已落地（quant_optimizer → 三级缓存→40因子→蒙特卡洛回测→FGSM对抗→Brinson归因→VWAP执行）(conf: 1.0)
- ✅ **AGENTS.md 两轮升级 + 1次精简化** — Session Recovery协议 + 5级主动回忆搜索规则 → SEARCH_RULES.md, 43%字数减少 (conf: 1.0)
- ✅ **Qlib** 0.9.7 (Python 3.12) 正常；**不兼容 Python 3.14**；macOS需 `mp.set_start_method("fork")`(conf: 1.0)
- ✅ **RD-Agent** macOS无Docker下可直接跑 — `.env` env_type=local (conf: 1.0)
- ✅ **盘中监控** — margin_monitor(融资融券) + market_monitor(7维情绪) (conf: 1.0)
- ✅ **PySide6** 6.11.0 在 Python 3.14.4 (macOS) 完美运行 (conf: 1.0)
- ❌ **Ollama 0.20.4 + Qwen 7B** M5 16GB不稳定 — 旧版+内存不足 (conf: 0.8)
- ✅ Provider Proxy Base URL不带`/v1`；飞书文件API直发无需确认 (conf: 1.0)

### 持仓（截至 05-11 盘中）
- **组合**: 国晟科技(-10%跌停)、美诺华(-10%跌停)、法尔胜(-5.59%)、天银机电(-4.82%)遭受重挫
- **历史最高点**: 5/8 累计+¥13,501 (+26.11%)
- **⚠️ 减仓未执行**: 5/8建议5/11开盘减仓95%→70-80%未及执行，国晟/美诺华随即跌停
- **⚠️ 代码问题**: 600593 回调结果为「大连圣亚」非「德龙汇能」，持仓配置需核实
- **当前状态**: 组合面临较大回撤，需重新评估止损策略和持仓结构

### GitHub 公开仓库
- Fabio99999999/openclaw-evolved-invoice（不含 secrets/交易组件）

---

## ▎待办（Todos）

### 🔴 高优先级
- [ ] **复盘5/11暴跌** — 国晟/美诺华双跌停原因，检视止损策略执行
- [ ] **核实600593代码** — 德龙汇能 vs 大连圣亚，修复持仓配置
- [ ] **飞书 cron 投递失败排查**
- [ ] Qlib 因子迭代（RD-Agent loop_n 1→3-5）
- [ ] FaceCat→Qlib 数据管道 bin 对齐修复
- [ ] 实盘模拟框架整合
- [ ] 因子评分网络验证（非交易时间）
- [ ] analyz.py 重构（FaceCat+缓存）

### 🟡 中优先级
- [ ] **确认5/11晚4个skill安装完毕** — clawhub, skill-finder-cn, tavily-search, peekaboo (会话截断)
- [ ] Gmail cron credentials（需Google Cloud凭据）
- [ ] **持仓代码批量校验** — 确保所有股票代码对应正确
- [ ] 北向资金API接入
- [ ] 量价背离检测→factor_engine.py
- [ ] FaceCat Kronos 搜索框bug修复
- [ ] Tushare Pro注册

### 🟢 低优先级
- [ ] QMD memory backend embedding
- [ ] Local LLM（Ollama升级/llama.cpp GGUF）
- [ ] ACP协议、海外仓调研
- [ ] loopDetector→交易cron集成
- [ ] 微信通信搭建（待确认扫码方案）

---

## ▎系统配置

```json
{
  "config_version": 19,
  "config_history": [
    {"v":19, "date":"2026-05-12", "what":"autoDream: 记录5/11晚升级维护(5.2→5.7)、AGENTS精简、extensions清理、todos更新"},
    {"v":18, "date":"2026-05-12", "what":"autoDream: 记录5/11双跌停重大回撤、代码问题、更新待办"},
    {"v":17, "date":"2026-05-11", "what":"autoDream 精简：3天无新交互"},
    {"v":16, "date":"2026-05-10", "what":"补充5/8细节+版本号header修复"},
    {"v":15, "date":"2026-05-09", "what":"5/8收盘+26.11%+减仓待执行"},
    {"v":14, "date":"2026-05-08", "what":"autoDream归纳+5/7市场"},
    {"v":13, "date":"2026-05-08", "what":"减仓防御+天银-10.49%"},
    {"v":11, "date":"2026-05-06", "what":"监控+AGENTS.md第2轮升级"}
  ],
  "cost_daily_max": 5,
  "cost_monthly_max": 200
}
```
