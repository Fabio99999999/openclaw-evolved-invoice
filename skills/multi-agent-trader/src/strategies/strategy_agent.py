"""StrategyAgent — evaluate a single strategy against a stock."""

import json
import logging
from typing import Optional

from agents.base_agent import BaseAgent
from protocols import AgentContext, AgentOpinion
from runner import try_parse_json
from .loader import get_strategy

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """Agent that evaluates a single trading strategy for a stock.

    Each strategy is a natural-language reasoning template (YAML file)
    describing entry/exit criteria, scoring adjustments, and risk rules.
    """

    max_steps = 6

    def __init__(self, strategy_id: str, **kwargs):
        super().__init__(**kwargs)
        self.strategy_id = strategy_id
        self._strategy = get_strategy(strategy_id)
        if self._strategy:
            # Only expose tools that the strategy needs
            self.tool_names = list(self._strategy.required_tools) or self.tool_names

    def system_prompt(self, ctx: AgentContext) -> str:
        s = self._strategy
        if s:
            display = s.display_name
            description = s.description
            instructions = s.instructions
        else:
            display = self.strategy_id
            description = f"Evaluate the {self.strategy_id} strategy."
            instructions = description

        return f"""\
You are applying the **{display}** strategy.

## Strategy Description
{description}

## Strategy Instructions
{instructions}

## Task
Evaluate whether **{ctx.stock_code} ({ctx.stock_name or 'Unknown'})** meets
this strategy's criteria. Use tools to fetch data and verify conditions.

## Output Format
Return **only** a valid JSON object with these fields:
{{
  "strategy_id": "{self.strategy_id}",
  "signal": "strong_buy|buy|hold|sell|strong_sell",
  "confidence": 0.0–1.0,
  "conditions_met": ["条件1", "条件2"],
  "conditions_missed": ["未满足条件1"],
  "score_adjustment": -20 to +20,
  "reasoning": "2–3 sentence explanation of strategy-based decision"
}}
"""

    def build_user_message(self, ctx: AgentContext) -> str:
        parts = [
            f"Strategy: **{self._strategy.display_name if self._strategy else self.strategy_id}**",
            f"Stock: **{ctx.stock_code} ({ctx.stock_name or 'Unknown'})**",
        ]

        # Include previous analysis context
        for op in ctx.opinions:
            if op.agent_name == "technical":
                parts.append(f"\nTechnical context: {op.reasoning}")
                if op.key_levels:
                    parts.append(f"Key levels: {json.dumps(op.key_levels, ensure_ascii=False)}")
            elif op.agent_name == "intel":
                parts.append(f"\nSentiment context: {op.reasoning}")

        return "\n".join(parts)

    def build_output(self, content: str, ctx: AgentContext) -> AgentOpinion:
        parsed = try_parse_json(content)
        if parsed and isinstance(parsed, dict):
            signal = str(parsed.get("signal", "hold"))
            try:
                confidence = float(parsed.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            try:
                score_adj = int(parsed.get("score_adjustment", 0))
            except (TypeError, ValueError):
                score_adj = 0

            conditions_met = parsed.get("conditions_met", [])
            conditions_missed = parsed.get("conditions_missed", [])

            return AgentOpinion(
                agent_name=f"strategy_{self.strategy_id}",
                signal=signal,
                confidence=confidence,
                reasoning=parsed.get("reasoning", content),
                raw_data={
                    "strategy_id": self.strategy_id,
                    "conditions_met": conditions_met,
                    "conditions_missed": conditions_missed,
                    "score_adjustment": score_adj,
                },
                key_levels={},
            )

        return AgentOpinion(
            agent_name=f"strategy_{self.strategy_id}",
            signal="hold",
            confidence=0.3,
            reasoning=f"Failed to parse strategy evaluation: {content[:200]}",
        )
