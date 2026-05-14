# MEMORY.md — 长期记忆（结构化版）

> 版本: 26 | 上次更新: 2026-05-14 06:02 (系统维护)

---

## ▎用户信息

- **姓名**: 老板 | **职业**: 交易员/独立创业者
- **所在地**: 意大利 (Europe/Rome GMT+2)
- **沟通**: 飞书 + webchat | **语言**: 中文为主

---

## ▎活跃项目

### 1. AI 量化交易系统 🏆（最高优先级）
**状态**: 战略转型期 — 成熟平台 + AI 注入
**成本**: ~$0.62/月

**已完成** ✅
- 基础技能+4交易Cron+FaceCat报价/Sina实时/efinance备选
- FaceCat Kronos桌面版(PySide6+UI定制) + Qlib 0.9.7 + LightGBM + RD-Agent macOS全循环
- 全流程6大方向代码落地（quant_optimizer: 缓存/因子引擎/回测/对抗/归因/VWAP）
- 林克方法5大模块落地（趋势分析/入场信号/止损优化/仓位管理/统一入口link_analyze）
- 盘中监控系统 (margin_monitor + market_monitor + MONITORING_DIMENSIONS.md)
- AGENTS.md 两轮升级+精简化+5级搜索规则
- **策略架构修复 (5/13)**: 3个相对引用→绝对引用，11个YAML策略全部加载成功 ✅
- **chart_gen.py (5/13)**: K线图+投资组合饼图生成器，matplotlib+PingFang HK中文显示 ✅
- **视觉模型配置 (5/13)**: uiuiapi/qwen-vl-max + qwen-vl-plus 双视觉模型，按需切换 ✅
- **Peekaboo 3.1.2** 已安装（缺Screen Recording权限，截图功能待授权）
- **策略架构决策 (5/13)**: multi-agent-trader 保持为单体 ClawHub skill，不拆分11策略，待推GitHub发布
- **备份 (5/13 00:24)**: multi-agent-trader 完整备份至 `backups/multi-agent-trader-20260513_0024/`
- **收盘综合报告修复 (5/15)**: portfolio.json更新为5/13调仓后7只新股 + 所有6个交易cron改用multi-agent-trader 4Agent+11策略管线 + 禁用5个冗余cron ✅

**⚠️ 事件回顾 (5/7-5/13)**:
- 5/7: 天银-10.49%巨阴 + 美诺华跌停，95%仓位未降
- 5/8: 反弹+¥771(+1.20%)，累计+26.11%，95%仓位持续→建议减仓未执行
- **5/11: 国晟(-10%)+美诺华(-10%)双跌停**，组合遭重大回撤
- **5/12(周二)**: 日亏¥1,440(-2.40%)→收盘反弹+¥1,985(+1.98%)，累计+¥13,356(+16.64%)；**华电辽能+10.01%涨停**；德龙汇能-7.45%破位；美诺华连续3日大跌，浮亏-18.5%
- **5/13(周三)**: 大幅调仓+大丰收。**早盘**: 华电辽能连续涨停(第二板一字板)+鸿博+7.01%反包，组合单日+¥4,634(+4.71%)，累计+¥17,990(+21.33%)，总资产¥105,470。**午后**: 大幅调仓——清仓美诺华/德龙汇能/天银/鸿博/晓程/龙星，新进中国能建/卓郎智能/锦龙股份/永鼎股份/圣阳股份共7只；调仓后今日盈利+¥2,244；累计+¥14,160.49；华电辽能利润扩至+22.85%

**技术约束**: FaceCat无PE/PB换手；efinance意大利部分地区超时；Qlib需Python3.12(不兼容3.14)；RD-Agent macOS无Docker可直接跑

**代码确认** ✅: 德龙汇能应为 **000593**(深市)，非600593(大连圣亚) — 已核实 2026-05-12

### 2. OpenClaw 系统维护（2026-05-11 晚）
**状态**: 5.2→5.7 升级完成 + 精简化 + 清理
- Extensions清理: openclaw-lark(84MB) + weixin(45MB) 已删除
- AGENTS.md 精简: 11,516→6,567 chars (-43%)，5级搜索规则移至 SEARCH_RULES.md
- Doctor修复: bundledDiscovery/101孤儿transcript/43不可用skill禁用 → 46技能在线
- Gateway 2026.5.7, 6 plugins: deepseek/intelligent-compression/tavily/openclaw-lark/feishu/memory-core

**⚠️ 待确认**: 5/11晚请求安装 clawhub/skill-finder-cn/tavily-search/peekaboo → skill-finder-cn✓已在workspace, tavily✓在plugins.allow; clawhub状态待确认; Peekaboo CLI 3.1.2已安装(缺Screen Recording权限)，skill文件待安装

### 3. 海外仓 & ACP协议 & Claude Code
- 海外仓: 调研阶段无新进展
- ACP: P0评估(~6-8h)，待交易系统稳定
- Claude Code: 已完成，不再推进

---

## ▎关键决策

| 日期 | 决策 | 原因 |
|------|------|------|
| 04-24 | 模型 GLM→deepseek-reasoner | 推理质量+成本大降 |
| 04-24 | 三层会话恢复系统 | 防丢失+crash恢复 |
| 04-28 | QVeris全部移除 | 稳定性 |
| 04-28 | Gmail cron禁用 | 缺credentials.json |
| 04-28/29 | 战略转型→成熟平台+AI注入 | Qlib首选, FaceCat Kronos wrapper |
| 04-29 | FaceCat报价API主数据源 | 意大利直连+完整CSV |
| 04-29 | QLib+RD-Agent macOS全循环跑通 | Baseline年化9.43% |
| 05-04 | 6大优化方向全部代码落地 | quant_optimizer全流程 |
| 05-06 | AGENTS.md第2轮搜索规则升级 | 5级搜索体系 |
| 05-13 | Strategy保持现状→推GitHub当skill发布 | multi-agent-trader是完整ClawHub skill |
| 05-13 | 图片识别+输出功能增强 | Peekaboo+chart_gen.py+Qwen-VL视觉模型 |
| 05-13 | 大幅调仓(清5旧进7新) | 清美诺华/德龙汇能/天银/鸿博/晓程/龙星，进中国能建/卓郎智能/锦龙股份/永鼎股份/圣阳股份 |

---

## ▎事实图谱

### 系统
- **模型**: deepseek/deepseek-v4-flash (主), uiuiapi/deepseek-reasoner (fallback) (1.0)
- **Provider Proxy**: 端口3457, Anthropic↔OpenAI协议互转 (1.0)
- **GitHub**: Fabio99999999/openclaw-evolved-invoice（不含secrets/交易组件）
- ✅ AGENTS精简(-43%), Gateway 5.7, 6 plugins active (1.0)
- ⚠️ Gmail cron待credentials激活 / memory FTS在线·向量降级 / QMD memory未运行 (1.0)
- ❌ Peekaboo缺Screen Recording权限 (1.0)

### 交易技术栈
- **数据源**: FaceCat报价API(意大利OHLC无PE/PB，持续空响应⚠️)、efinance单股可用、新浪hq实时 (1.0)
- **量化**: Qlib 0.9.7(Python3.12), RD-Agent macOS可直跑, 林克方法5模块 (1.0)
- **可视化**: PySide6 6.11.0(Python3.14.4), **matplotlib+chart_gen.py(PingFang HK中文)** (1.0)
- **截图分析**: Peekaboo 3.1.2 CLI已安装(Screen Recording未授权); Qwen-VL-Max/Plus 双视觉模型 (1.0)
- **图表生成**: chart_gen.py K线图+组合饼图+涨跌幅柱状图，PingFang HK中文字体 (1.0)
- **监控**: margin_monitor(融资)+market_monitor(7维情绪) (1.0)
- ❌ efinance get_realtime_quotes超时/pytdx全超时/东财API阻断/FaceCat空响应 (1.0)
- ❌ Ollama 0.20.4+Qwen 7B M5 16GB不足 (0.8)

### 爬取链
Anspire/Tavily搜 → Scrapling/Jina抓URL → agent-browser处理复杂 (1.0)

### 持仓概览（截至5/13收盘）
- **账户**: 国泰海通证券 (**9985) | 同花顺
- **股票市值** ¥66,994 | **基金市值** ¥3,910.70 | **累计盈利 +¥14,160.49** | **今日盈利 +¥2,244.00**

| 股票 | 盈亏 | 备注 |
|------|------|------|
| **华电辽能** 🟢 | **+22.85%** (+¥3,079.89) | 5/12涨停进，利润继续扩大，1000股 |
| **卓郎智能** 🟢 | **+8.31%** (+¥578) | 新进，1200股 |
| **中国能建** 🟢 | **+4.27%** (+¥433.92) | 新进基建票，3000股 |
| **永鼎股份** 🟢 | **+3.24%** (+¥325) | 新进，200股 |
| **圣阳股份** 🟢 | **+1.70%** (+¥174) | 新进，300股 |
| **国晟科技** ⚠️ | -¥76.00 | 保留(较跌停已大幅修复)，小仓位 |
| **锦龙股份** 🔴 | **-4.67%** (-¥444.85) | 新进券商，800股 |

| 基金 | 盈亏 | 备注 |
|------|------|------|
| **中韩芯片** 💀 | -¥1,879.39 | 总基金亏损¥3,689.04，规模小可考虑止损腾资金 |

> **5/13收盘旧组合参考**: 当天6涨2跌，华电辽能两连板(一字板)，鸿博+7.01%反包，日+¥4,634(+4.71%)，累计+¥17,990(+21.33%)，总资产¥105,470；午后大幅调仓换股

---

## ▎待办

### 🔴 高
- [ ] **复盘止损策略** — 5/11双跌停教训，执行纪律改进
- [ ] **Gmail credentials 配置**（需 Google Cloud Console 创建 OAuth 凭据）
- [ ] chart_gen.py集成入run_analysis.py（阻塞中）
- [ ] Peekaboo skill安装到workspace + 系统Screen Recording权限配置（需老板在系统设置→隐私→屏幕录制→添加peekaboo）
- [ ] multi-agent-trader 推GitHub当ClawHub skill发布
- [ ] 新组合监控（中国能建/卓郎智能/锦龙/永鼎/圣阳 进入观察期）
- [ ] FaceCat API空响应排查（持续数日）

### 🟡 中
- [ ] 批量持仓代码校验
- [ ] 北向资金API/量价背离检测接入
- [ ] FaceCat Kronos 搜索框bug
- [ ] Tushare Pro注册
- [ ] Qlib因子迭代(RD-Agent loop_n 1→3-5)
- [ ] FaceCat→Qlib 数据管道 bin 对齐修复
- [ ] 实盘模拟框架整合 / analyz.py 重构

### 🟢 低
- [ ] QMD memory backend / Local LLM(Ollama升级/llama.cpp)
- [ ] ACP协议/海外仓调研
- [ ] LoopDetector→交易cron集成
- [ ] 微信通信搭建
- [ ] AI图片分析用例探索（chart_gen + Qwen-VL 组合）

---

## ▎配置

```json
{
  "config_version": 25,
  "config_history": [
    {"v":26, "date":"2026-05-14", "what":"系统维护: memory重建·清理6旧cron·Gmail依赖安装+新建cron·MEMORY.md更新"},
    {"v":25, "date":"2026-05-15", "what":"修复: portfolio.json更新为5/13调仓后持仓 + 所有cron jobs改用multi-agent-trader策略引擎 + 清理5个冗余cron"},
    {"v":23, "date":"2026-05-14", "what":"autoDream: 增量维护，FaceCat API持续空响应，系统稳定运行中"},
    {"v":22, "date":"2026-05-13", "what":"5/13大幅调仓：清仓大亏票，新进中国能建/卓郎智能/锦龙股份，华电辽能利润扩至+22.85%"},
    {"v":19, "date":"2026-05-12", "what":"autoDream: 5/11晚升级维护(5.2→5.7)+AGENTS精简+extensions清理"},
    {"v":18, "date":"2026-05-12", "what":"autoDream: 5/11双跌停重大回撤"},
    {"v":15, "date":"2026-05-09", "what":"5/8收盘+26.11%+减仓待执行"}
  ],
  "cost_daily_max": 5,
  "cost_monthly_max": 200
}
```
