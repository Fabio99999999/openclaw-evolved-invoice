"""StrategyAggregator — weighted aggregation of strategy opinions."""

import json
import logging
from typing import Dict, List, Optional

from protocols import AgentContext, AgentOpinion

logger = logging.getLogger(__name__)

_SIGNAL_SCORES: Dict[str, float] = {
    "strong_buy": 5.0,
    "buy": 4.0,
    "hold": 3.0,
    "sell": 2.0,
    "strong_sell": 1.0,
}

_SCORE_TO_SIGNAL: List[tuple[float, str]] = [
    (4.5, "strong_buy"),
    (3.5, "buy"),
    (2.5, "hold"),
    (1.5, "sell"),
    (0.0, "strong_sell"),
]


class StrategyAggregator:
    """Combine multiple strategy evaluations into one consensus opinion."""

    def aggregate(self, ctx: AgentContext) -> Optional[AgentOpinion]:
        """Aggregate all strategy opinions in context into a consensus."""
        strategy_opinions = [
            op for op in ctx.opinions
            if op.agent_name.startswith("strategy_")
        ]
        if not strategy_opinions:
            return None

        total_score = 0.0
        total_weight = 0.0
        conditions_met_all = []
        conditions_missed_all = []
        reasons = []
        total_score_adj = 0
        strategy_details = []

        for op in strategy_opinions:
            score = _SIGNAL_SCORES.get(op.signal, 3.0)
            weight = op.confidence
            total_score += score * weight
            total_weight += weight

            raw = op.raw_data or {}
            conditions_met_all.extend(raw.get("conditions_met", []))
            conditions_missed_all.extend(raw.get("conditions_missed", []))
            total_score_adj += raw.get("score_adjustment", 0)
            reasons.append(f"[{op.agent_name}] {op.reasoning}")

            strategy_details.append({
                "strategy": op.agent_name,
                "signal": op.signal,
                "confidence": op.confidence,
                "score_adjustment": raw.get("score_adjustment", 0),
            })

        if total_weight == 0:
            avg_score = sum(_SIGNAL_SCORES.get(op.signal, 3.0) for op in strategy_opinions) / len(strategy_opinions)
        else:
            avg_score = total_score / total_weight

        # Convert score back to signal
        consensus_signal = "hold"
        for threshold, signal in _SCORE_TO_SIGNAL:
            if avg_score >= threshold:
                consensus_signal = signal
                break

        # Confidence: average of all confidences, modulated by agreement level
        avg_confidence = sum(op.confidence for op in strategy_opinions) / len(strategy_opinions)
        signals_set = set(op.signal for op in strategy_opinions)
        if len(signals_set) == 1:
            agreement_bonus = 0.15
        elif len(signals_set) <= 2:
            agreement_bonus = 0.05
        else:
            agreement_bonus = -0.10
        consensus_confidence = min(1.0, max(0.0, avg_confidence + agreement_bonus))

        # Build consensus reasoning
        consensus_reasoning = (
            f"Strategy consensus ({len(strategy_opinions)} strategies): "
            + "; ".join(reasons)
        )

        return AgentOpinion(
            agent_name="strategy_consensus",
            signal=consensus_signal,
            confidence=consensus_confidence,
            reasoning=consensus_reasoning,
            raw_data={
                "strategy_count": len(strategy_opinions),
                "total_score_adjustment": total_score_adj,
                "conditions_met": conditions_met_all,
                "conditions_missed": conditions_missed_all,
                "strategy_details": strategy_details,
            },
            key_levels={},
        )
