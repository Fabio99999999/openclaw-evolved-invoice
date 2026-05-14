"""StrategyRouter — rule-based strategy selection based on market regime."""

import logging
from typing import Dict, List, Optional

from protocols import AgentContext
from .loader import load_strategies, get_strategies_by_regime

logger = logging.getLogger(__name__)


class StrategyRouter:
    """Select applicable trading strategies based on market conditions.

    Detects market regime from technical analysis output, then selects
    the most relevant strategies for that regime.
    """

    def detect_regime(self, ctx: AgentContext) -> Optional[str]:
        """Detect market regime from technical agent opinion."""
        for op in ctx.opinions:
            raw = op.raw_data or {}
            if op.agent_name not in ("technical", "strategy_consensus"):
                continue

            ma_alignment = str(raw.get("ma_alignment", "")).lower()
            try:
                trend_score = float(raw.get("trend_score", 50))
            except (TypeError, ValueError):
                trend_score = 50.0
            volume_status = str(raw.get("volume_status", "")).lower()

            if ma_alignment == "bullish" and trend_score >= 70:
                return "trending_up"
            if ma_alignment == "bearish" and trend_score <= 30:
                return "trending_down"
            if ma_alignment in ("neutral", "mixed") or 35 <= trend_score <= 65:
                return "sideways"
            if volume_status == "heavy" and 30 < trend_score < 70:
                return "volatile"

        # Check meta for sector_hot flag
        if ctx.meta.get("sector_hot"):
            return "sector_hot"

        return None

    def select_strategies(
        self,
        ctx: AgentContext,
        max_count: int = 3,
        override_regime: Optional[str] = None,
    ) -> List[str]:
        """Select strategy names for the given context.

        Args:
            ctx: Analysis context with opinions from previous agents.
            max_count: Maximum number of strategies to select.
            override_regime: Force a specific regime (e.g., user-requested).

        Returns:
            List of strategy names sorted by priority.
        """
        # User-requested strategies take priority
        requested = ctx.meta.get("strategies_requested", [])
        if requested:
            logger.info(f"Using user-requested strategies: {requested}")
            return requested[:max_count]

        # Detect regime
        regime = override_regime or self.detect_regime(ctx)

        if regime:
            strategies = get_strategies_by_regime(regime, max_count=max_count)
            if strategies:
                names = [s.name for s in strategies]
                logger.info(f"Regime '{regime}' -> strategies: {names}")
                return names

        # Default fallback: load all and pick by priority
        all_strategies = sorted(
            load_strategies().values(),
            key=lambda s: (s.default_priority, s.name),
        )
        names = [s.name for s in all_strategies if s.default_router or s.default_active][:max_count]
        if not names:
            names = [s.name for s in all_strategies[:max_count]]
        logger.info(f"No regime detected, using defaults: {names}")
        return names
