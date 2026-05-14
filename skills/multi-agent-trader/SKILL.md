# Multi-Agent Trader Skill

**AI多Agent协同分析系统** — 技术、情报、风险、决策四合一股票分析管线。

## 概述

将 upstream `ZhuLinsen/daily_stock_analysis` v3.16 的多Agent系统移植到 OpenClaw 环境。
使用 LLM + 工具调用 (Tool Calling) 实现 ReAct 循环，无需 Django/Celery/PostgreSQL。

### 架构

```
用户请求 → Orchestrator
              │
              ├─ TechnicalAgent  (技术分析：趋势/量能/形态)
              ├─ IntelAgent      (情报分析：新闻/公告/风险信号)
              ├─ RiskAgent       (风险评估：独立风险筛查)
              └─ DecisionAgent   (决策合成：输出操作面板)
              └─ PortfolioAgent  (组合分析：多股持仓评估)
```

### 模式

| 模式 | 管道 | 特点 | 推荐场景 |
|------|------|------|----------|
| `quick` | Technical → Decision | 最快，~2轮LLM调用 | 盘前快速扫描 |
| `standard` | Technical → Intel → Decision | 平衡速度与深度 | 日常分析，默认 |
| `full` | Technical → Intel → Risk → Decision | 最全面，含风险否决 | 重仓股、大额买入 |

## 文件结构

```
skills/multi-agent-trader/
├── SKILL.md                 # 本文件 — 使用方法
├── run_analysis.py          # CLI入口点
├── strategies/              # YAML 策略模板（P1）
│   ├── high_probability.yaml
│   ├── momentum_breakout.yaml
│   └── ... (共11个)
└── src/
    ├── __init__.py
    ├── protocols.py          # 数据类：AgentContext, AgentOpinion, StageResult
    ├── runner.py             # LLM调用 + ReAct执行循环
    ├── orchestrator.py       # 管线编排
    ├── agents/
    │   ├── base_agent.py     # BaseAgent 抽象类
    │   ├── technical_agent.py
    │   ├── intel_agent.py
    │   ├── risk_agent.py
    │   ├── decision_agent.py
    │   └── portfolio_agent.py
    └── tools/
        ├── registry.py       # ToolRegistry — 工具注册+执行
        ├── facecat_tools.py  # 数据工具（efinance/Sina/指标计算）
        └── search_tools.py   # 搜索工具（Anspire web search）
```

## 前提条件

- Provider Proxy (localhost:3457) — LiteLLM 协议转换
- efinance (`pip install efinance`)
- 可选：Anspire 搜索（`ANSPIRE_API_KEY` 环境变量）

## 快速开始

### 1. 验证安装
```bash
cd skills/multi-agent-trader
python run_analysis.py 600519 --mode quick
```

### 2. 标准分析
```bash
python run_analysis.py 600519
```

### 3. 全面分析（含风险筛查）
```bash
python run_analysis.py 600519 --mode full --name "贵州茅台"
```

### 4. 批量分析
```bash
python run_analysis.py batch --codes 600519,000001,002415 --names "贵州茅台,平安银行,腾讯控股"
```

### 5. JSON 输出
```bash
python run_analysis.py 600519 --json --output dashboard.json
```

## 输出示例（Decision Dashboard）

```json
{
  "decision_type": "buy",
  "sentiment_score": 72,
  "confidence_level": "较高",
  "analysis_summary": "技术面多头排列+量能配合，基本面估值合理",
  "operation_advice": "可建仓或加仓",
  "dashboard": {
    "core_conclusion": {
      "one_sentence": "趋势看涨，短期回调可建仓",
      "signal_type": "bullish",
      "position_advice": {
        "no_position": "逢回调买入，支撑位设止损",
        "has_position": "继续持有，跌破支撑减仓"
      }
    },
    "intelligence": {
      "sentiment_label": "positive",
      "risk_alerts": ["行业政策不确定性"],
      "positive_catalysts": ["业绩预增", "机构增持"]
    },
    "battle_plan": {
      "sniper_points": {
        "stop_loss": "14.50",
        "take_profit": "16.80"
      },
      "position_strategy": {
        "suggested_position": "10-20%",
        "entry_plan": "分批建仓"
      }
    }
  }
}
```

## YAML 策略模板（P1）

`strategies/` 目录包含 11 个策略文件，作为决策参考模板：

| 策略 | 文件 | 核心逻辑 |
|------|------|----------|
| 高胜算操盘 | `high_probability.yaml` | 林克方法：多时间框架+稳健形态 |
| 动量突破 | `momentum_breakout.yaml` | 放量突破关键阻力 |
| 回调入场 | `pullback_entry.yaml` | 趋势中回调均线买入 |
| 趋势跟踪 | `trend_following.yaml` | MACD金叉+MA多头 |
| 反转交易 | `reversal_trade.yaml` | 超卖+底背离 |
| 成交量分析 | `volume_analysis.yaml` | 量价背离检测 |
| 波动率突破 | `volatility_breakout.yaml` | Bollinger带宽+ATR |
| 估值修复 | `value_reversion.yaml` | PE/PB低水位+ROE |
| 事件驱动 | `event_driven.yaml` | 财报/公告/政策催化 |
| 组合对冲 | `portfolio_hedge.yaml` | 板块配比+相关性 |
| 风险管理 | `risk_management.yaml` | 止损+仓位优化 |

## 工具清单

### 数据工具 (facecat_tools.py)
| 工具 | 参数 | 用途 |
|------|------|------|
| `get_realtime_quote` | stock_code | 实时行情 |
| `get_daily_history` | stock_code, days | 日K线+指标 |
| `analyze_trend` | stock_code | 趋势分析 |
| `calculate_ma` | stock_code, period | 均线计算 |
| `get_volume_analysis` | stock_code | 量能分析 |
| `analyze_pattern` | stock_code | K线形态 |
| `get_market_indices` | (none) | 大盘指数 |
| `get_stock_info` | stock_code | 基本信息 |

### 搜索工具 (search_tools.py)
| 工具 | 参数 | 用途 |
|------|------|------|
| `search_stock_news` | stock_code, stock_name | 新闻搜索 |
| `search_comprehensive_intel` | stock_code, stock_name | 多维度情报 |

## 数据源

| 数据源 | 用途 | 可用性 |
|--------|------|--------|
| efinance | 日K线、实时行情、PE/PB/换手率 | ✅ 意大利直连 |
| Sina hq.sinajs.cn | 实时行情（fallback） | ✅ 意大利可用 |
| Anspire | Web搜索（需 ANSPIRE_API_KEY） | ✅ 已配置 |

## 局限

- 搜索工具依赖网络，可能超时。工具会自动降级返回搜索查询上下文。
- FaceCat 报价 API 无 PE/PB/换手率，使用 efinance 替代。
- LLM 调用通过 Provider Proxy (3457)，需确认代理运行中。

## 可视输出与图片分析

### 📊 K线图与组合图表
分析时可自动生成 K线图 和 投资组合饼图：

```bash
# 单股 + 图表
python run_analysis.py 600519 --chart

# Batch + 图表
python run_analysis.py batch --codes 600519,000001 --chart

# Full mode + 图表
python run_analysis.py 600519 --mode full --chart
```

图表保存在 `charts/` 目录下，包含：
- Candlestick K线（120天）+ MA5/10/20 均线
- 成交量柱状图
- 最新收盘价与涨跌幅标注
- 多股批量时自动生成组合饼图

### 📸 截图捕获
使用 Peekaboo 截取屏幕：
```bash
python run_analysis.py 600519 --screenshot
```

### 🖼️ 视觉模型切换
当需要识别/分析图片（如截图、K线图、报告）时，可临时切换至视觉模型：

**方法：通过 `session_status` 在会话内切换模型**
1. `session_status(model="uiuiapi/qwen-vl-max")` → 切换到视觉模型
2. 调用 `image(path="screenshot.png")` 分析图片
3. `session_status(model="default")` → 切回默认的 deepseek-v4-flash

**可用视觉模型：**
| 别名 | 模型 ID | 成本 | 用途 |
|------|---------|------|------|
| Qwen-VL-Max | `uiuiapi/qwen-vl-max` | 输入$0.003/输出$0.012 | 最高质量图片分析 |
| Qwen-VL-Plus | `uiuiapi/qwen-vl-plus` | 输入$0.0008/输出$0.0016 | 日常图片分析（性价比） |

**支持的分析类型：**
- 📋 截图 OCR 文字提取
- 📈 K线图/技术指标视觉解读
- 📰 新闻/公告图片内容识别
- 📱 App/网页界面分析
- 🔍 图表异常模式检测

> **默认使用 deepseek-v4-flash**（快速文本模型），仅在需要图片分析时切换到视觉模型，分析完成后切回，以控制成本。

## 与原生工具的集成

本系统可与 OpenClaw 的 `a-stock-trading` skill 配合使用：
- **a-stock-trading** 提供 `analyze.py` 和 `portfolio.py`，适合简单快速的单股分析。
- **multi-agent-trader** 提供多 Agent 协同、深度决策面板，适合需要综合研判的场景。

## YAML策略使用

策略文件定义在 `strategies/` 下，可在 DecisionAgent 的 system prompt 中引用：

```python
orchestrator = AgentOrchestrator(
    tool_registry=registry,
    skill_instructions="参考 high_probability 策略框架进行决策",
    mode="full",
)
```

或通过环境变量加载：
```bash
MULTI_AGENT_STRATEGY=high_probability python run_analysis.py 600519
```

## 开发

```bash
# 运行单测
python -m pytest tests/

# verbose调试
python run_analysis.py 600519 --verbose
```
