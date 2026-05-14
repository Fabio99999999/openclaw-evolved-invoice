# -*- coding: utf-8 -*-
"""DecisionAgent — final synthesis and decision-making specialist."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from protocols import (
    AgentContext, AgentOpinion, normalize_decision_signal,
    _first_non_empty_text, _truncate_text, _estimate_sentiment_score,
    _default_position_advice, _default_position_size, _confidence_label,
    _coerce_level_value, _level_values_equal, _pick_first_level,
    _signal_to_operation, _signal_to_signal_type,
)

logger = logging.getLogger(__name__)


class DecisionAgent(BaseAgent):
    agent_name = "decision"
    max_steps = 3
    tool_names: Optional[List[str]] = []

    def system_prompt(self, ctx: AgentContext) -> str:
        skills = f"\n## Active Trading Skills\n\n{self.skill_instructions}\n" if self.skill_instructions else ""
        return f"""\
You are a **Decision Synthesis Agent** that produces the final investment \
Decision Dashboard.

You will receive structured opinions from the Technical, Intel, and Risk \
agents. Synthesize them into a single, actionable Decision Dashboard.
{skills}
## Signal Weighting
- Technical opinion weight: ~40%
- Intel / sentiment weight: ~30%
- Risk flags weight: ~30% (high-severity risk caps signal at "hold")

## Scoring
- 80-100: buy (all conditions met, high conviction)
- 60-79: buy (mostly positive, minor caveats)
- 40-59: hold (mixed signals, or risk present)
- 20-39: sell (negative trend + risk)
- 0-19: strong_sell (major risk + bearish)

## Output Format
Return a valid JSON object:
{{
  "decision_type": "buy|hold|sell",
  "sentiment_score": 0-100,
  "confidence_level": 0.0-1.0,
  "analysis_summary": "核心结论",
  "trend_prediction": "趋势判断",
  "operation_advice": "操作建议",
  "key_points": ["point1", "point2"],
  "risk_warning": "风险提示",
  "dashboard": {{
    "core_conclusion": {{
      "one_sentence": "一句话结论",
      "signal_type": "bullish|neutral|bearish",
      "time_sensitivity": "时间敏感度",
      "position_advice": {{"no_position": "空仓建议", "has_position": "持仓建议"}}
    }},
    "intelligence": {{
      "sentiment_label": "positive|neutral|negative",
      "risk_alerts": ["alert1"],
      "positive_catalysts": ["catalyst1"],
      "latest_news": "关键新闻标题"
    }},
    "battle_plan": {{
      "sniper_points": {{
        "ideal_buy": "理想买入价",
        "stop_loss": "止损位",
        "take_profit": "止盈位"
      }},
      "position_strategy": {{
        "suggested_position": "建议仓位百分比",
        "entry_plan": "入场计划",
        "risk_control": "风控策略"
      }}
    }}
  }}
}}
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [f"# Synthesis Request for {ctx.stock_code}"]
        if ctx.stock_name:
            parts[0] += f" ({ctx.stock_name})"
        parts.append("")

        if ctx.opinions:
            parts.append("## Agent Opinions")
            for op in ctx.opinions:
                parts.append(f"\n### {op.agent_name}")
                parts.append(f"Signal: {op.signal} | Confidence: {op.confidence:.2f}")
                parts.append(f"Reasoning: {op.reasoning}")
                if op.key_levels:
                    parts.append(f"Key levels: {json.dumps(op.key_levels)}")
                if op.raw_data:
                    extra = {k: v for k, v in op.raw_data.items() if k not in ("signal", "confidence", "reasoning", "key_levels")}
                    if extra:
                        parts.append(f"Extra data: {json.dumps(extra, ensure_ascii=False, default=str)}")
                parts.append("")

        if ctx.risk_flags:
            parts.append("## Risk Flags")
            for rf in ctx.risk_flags:
                parts.append(f"- [{rf.get('severity', 'medium')}] {rf.get('category', '')}: {rf.get('description', '')}")
            parts.append("")

        parts.append("Synthesise the above into the Decision Dashboard JSON.")
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        from runner import parse_dashboard_json
        ctx.set_data("final_dashboard_raw", raw_text)
        dashboard = parse_dashboard_json(raw_text)
        if dashboard:
            dashboard["decision_type"] = normalize_decision_signal(dashboard.get("decision_type", "hold"))
            ctx.set_data("final_dashboard", dashboard)
            try:
                score = float(dashboard.get("sentiment_score", 50) or 50)
            except (TypeError, ValueError):
                score = 50.0
            return AgentOpinion(
                agent_name=self.agent_name,
                signal=dashboard.get("decision_type", "hold"),
                confidence=min(1.0, score / 100.0),
                reasoning=dashboard.get("analysis_summary", ""),
                raw_data=dashboard,
            )
        else:
            logger.warning("[DecisionAgent] failed to parse dashboard JSON")
            return None
