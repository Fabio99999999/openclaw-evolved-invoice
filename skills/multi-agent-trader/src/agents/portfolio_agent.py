# -*- coding: utf-8 -*-
"""PortfolioAgent — analyses a *set* of stocks as a portfolio."""

from __future__ import annotations

import logging
from typing import Optional

from .base_agent import BaseAgent
from protocols import AgentContext, AgentOpinion
from runner import try_parse_json

logger = logging.getLogger(__name__)


class PortfolioAgent(BaseAgent):
    agent_name = "portfolio"
    max_steps = 4
    tool_names = ["get_realtime_quote", "get_stock_info"]

    def system_prompt(self, ctx: AgentContext) -> str:
        return (
            "You are a professional **portfolio analyst** specialising in "
            "A-share equity portfolios.\n\n"
            "## Your task\n"
            "Given individual stock analysis opinions, produce a **Portfolio Assessment**:\n"
            "1. **Position Sizing** — suggested weight per stock.\n"
            "2. **Sector Concentration** — warn if > 40% in one sector.\n"
            "3. **Correlation Risk** — flag highly correlated pairs.\n"
            "4. **Portfolio Risk Score** — 1-10 scale.\n"
            "5. **Rebalance Suggestions** — trim/add recommendations.\n\n"
            "## Output format\n"
            "Return a single JSON object:\n"
            "```json\n"
            "{\n"
            '  "portfolio_risk_score": 6,\n'
            '  "total_stocks": 5,\n'
            '  "positions": [\n'
            '    {"code": "600519", "suggested_weight": 0.25, "note": "..."},\n'
            "    ...\n"
            "  ],\n"
            '  "sector_warnings": [...],\n'
            '  "correlation_warnings": [...],\n'
            '  "rebalance_suggestions": [...],\n'
            '  "summary": "Portfolio is moderately concentrated ..."\n'
            "}\n"
            "```\n"
        )

    def build_user_message(self, ctx: AgentContext) -> str:
        stock_opinions = ctx.data.get("stock_opinions", {})
        stock_list = ctx.data.get("stock_list", [])
        parts = [f"Analyze a portfolio of {len(stock_list) or len(stock_opinions)} stocks:\n"]
        if stock_opinions:
            for code, opinion in stock_opinions.items():
                if isinstance(opinion, AgentOpinion):
                    parts.append(
                        f"- **{code}**: signal={opinion.signal}, confidence={opinion.confidence:.0%}, "
                        f"summary={opinion.reasoning[:200]}"
                    )
                elif isinstance(opinion, dict):
                    parts.append(
                        f"- **{code}**: signal={opinion.get('signal', 'unknown')}, "
                        f"summary={str(opinion.get('summary', ''))[:200]}"
                    )
        elif stock_list:
            for code in stock_list:
                parts.append(f"- {code}")
        if ctx.risk_flags:
            parts.append("\n### Risk Flags:\n" + "\n".join(f"- {f}" for f in ctx.risk_flags))
        return "\n".join(parts)

    def post_process(self, ctx: AgentContext, raw_response: str) -> Optional[AgentOpinion]:
        data = try_parse_json(raw_response)
        if data is None:
            return AgentOpinion(
                agent_name="portfolio", signal="hold", confidence=0.3,
                reasoning=raw_response[:500], raw_data={"raw": raw_response[:1000]},
            )
        ctx.data["portfolio_assessment"] = data
        risk_score = data.get("portfolio_risk_score", 5)
        signal = "hold"
        if risk_score <= 3:
            signal = "buy"
        elif risk_score >= 7:
            signal = "sell"
        return AgentOpinion(
            agent_name="portfolio", signal=signal, confidence=0.6,
            reasoning=data.get("summary", raw_response[:300]), raw_data=data,
        )
