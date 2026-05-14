# -*- coding: utf-8 -*-
"""AgentOrchestrator — multi-agent pipeline coordinator.

Modes:
- ``quick``   : Technical only → Decision (fastest, ~2 LLM calls)
- ``standard``: Technical → Intel → Decision (default)
- ``full``    : Technical → Intel → Risk → Decision
- ``strategy``: Technical → Intel → [StrategyAgent×N] → Aggregator → Decision
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from protocols import (
    AgentContext, AgentOpinion, AgentRunStats, StageResult, StageStatus,
    normalize_decision_signal, _first_non_empty_text, _truncate_text,
    _estimate_sentiment_score, _default_position_advice, _default_position_size,
    _confidence_label, _coerce_level_value, _level_values_equal, _pick_first_level,
    _signal_to_operation, _signal_to_signal_type, _extract_latest_news_title,
)
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

VALID_MODES = ("quick", "standard", "full", "strategy", "strategy_full")


@dataclass
class OrchestratorResult:
    success: bool = False
    content: str = ""
    dashboard: Optional[Dict[str, Any]] = None
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)
    total_steps: int = 0
    total_tokens: int = 0
    model: str = ""
    error: Optional[str] = None
    stats: Optional[AgentRunStats] = None


class AgentOrchestrator:
    """Multi-agent pipeline coordinator."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        skill_instructions: str = "",
        technical_skill_policy: str = "",
        max_steps: int = 10,
        mode: str = "standard",
    ):
        self.tool_registry = tool_registry
        self.skill_instructions = skill_instructions
        self.technical_skill_policy = technical_skill_policy
        self.max_steps = max_steps
        self.mode = mode if mode in VALID_MODES else "standard"

    # ================================================================
    # Public interface
    # ================================================================

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> OrchestratorResult:
        """Run the multi-agent pipeline for a dashboard analysis."""
        ctx = self._build_context(task, context)
        return self._execute_pipeline(ctx)

    def run_analysis(
        self,
        stock_code: str,
        stock_name: str = "",
        query: str = "",
        mode: str = "standard",
    ) -> OrchestratorResult:
        """Convenience: run full analysis on a stock."""
        ctx = AgentContext(
            query=query or f"分析 {stock_name or stock_code}",
            stock_code=stock_code,
            stock_name=stock_name,
        )
        prev_mode = self.mode
        if mode in VALID_MODES:
            self.mode = mode
        result = self._execute_pipeline(ctx)
        self.mode = prev_mode
        return result

    # ================================================================
    # Pipeline execution
    # ================================================================

    def _execute_pipeline(self, ctx: AgentContext) -> OrchestratorResult:
        stats = AgentRunStats()
        all_tool_calls: List[Dict[str, Any]] = []
        models_used: List[str] = []
        t0 = time.time()

        agents = self._build_agent_chain(ctx)

        for idx, agent in enumerate(agents):
            logger.info(f"[Orchestrator] Running stage: {agent.agent_name}")

            result: StageResult = agent.run(ctx)
            stats.record_stage(result)
            all_tool_calls.extend(result.meta.get("tool_calls_log", []))
            models_used.extend(result.meta.get("models_used", []))

            # Propagate cached data to next agents
            if result.success and result.opinion:
                self._propagate_data(ctx, result)

            if result.success and agent.agent_name == "decision":
                self._apply_risk_override(ctx)

            if result.status == StageStatus.FAILED:
                non_critical = agent.agent_name in ("intel", "risk")
                if not non_critical:
                    logger.error(f"[Orchestrator] Critical stage '{agent.agent_name}' failed: {result.error}")
                    return OrchestratorResult(
                        success=False, error=f"Stage '{agent.agent_name}' failed: {result.error}",
                        stats=stats, total_tokens=stats.total_tokens,
                        tool_calls_log=all_tool_calls,
                    )
                logger.warning(f"[Orchestrator] Non-critical '{agent.agent_name}' failed, degrading: {result.error}")

        # Final output assembly
        total_duration = round(time.time() - t0, 2)
        stats.total_duration_s = total_duration
        stats.models_used = list(dict.fromkeys(models_used))

        dashboard, content = self._resolve_final_output(ctx)
        model_str = ", ".join(dict.fromkeys(m for m in models_used if m))

        if dashboard is None and not content:
            return OrchestratorResult(
                success=False, error="No dashboard produced",
                stats=stats, total_tokens=stats.total_tokens,
                tool_calls_log=all_tool_calls,
            )

        return OrchestratorResult(
            success=bool(content), content=content, dashboard=dashboard,
            tool_calls_log=all_tool_calls, total_steps=stats.total_stages,
            total_tokens=stats.total_tokens, model=model_str, stats=stats,
        )

    def _propagate_data(self, ctx: AgentContext, result: StageResult) -> None:
        """Propagate agent data so downstream agents can skip redundant fetches."""
        opinion = result.opinion
        if opinion and opinion.raw_data:
            ctx.set_data(f"{opinion.agent_name}_opinion", opinion.raw_data)

        # After technical, save kline data
        if result.stage_name == "technical":
            kline_data = ctx.get_data("daily_history")
            if kline_data:
                ctx.set_data("trend_result", kline_data.get("indicators", {}))

        # After intel, save news context
        if result.stage_name == "intel":
            ctx.set_data("news_context", ctx.get_data("intel_opinion"))

    # ================================================================
    # Agent chain
    # ================================================================

    def _build_agent_chain(self, ctx: AgentContext) -> list:
        from agents.technical_agent import TechnicalAgent
        from agents.intel_agent import IntelAgent
        from agents.decision_agent import DecisionAgent
        from agents.risk_agent import RiskAgent

        kwargs = dict(
            tool_registry=self.tool_registry,
            skill_instructions=self.skill_instructions,
            technical_skill_policy=self.technical_skill_policy,
        )
        tech = TechnicalAgent(**kwargs)
        intel = IntelAgent(**kwargs)
        risk = RiskAgent(**kwargs)
        dec = DecisionAgent(**kwargs)

        strategy_enabled = self.mode in ("strategy", "strategy_full")

        if self.mode == "quick":
            return [tech, dec]
        elif self.mode == "full":
            return [tech, intel, risk, dec]
        elif strategy_enabled:
            try:
                import importlib
                router_mod = importlib.import_module("strategies.router")
                agent_mod = importlib.import_module("strategies.strategy_agent")
                agg_mod = importlib.import_module("strategies.aggregator")

                router = router_mod.StrategyRouter()
                strategy_ids = router.select_strategies(ctx)

                chain = [tech, intel]
                if self.mode == "strategy_full":
                    chain.append(risk)

                # Add strategy agents
                strat_agents = []
                for sid in strategy_ids:
                    try:
                        sa = agent_mod.StrategyAgent(
                            strategy_id=sid,
                            tool_registry=self.tool_registry,
                        )
                        strat_agents.append(sa)
                    except Exception as e:
                        logger.warning(f"Failed to create strategy agent '{sid}': {e}")

                chain.extend(strat_agents)
                chain.append(dec)
                logger.info(f"Strategy mode: selected {strategy_ids}")
                return chain
            except ImportError as e:
                logger.warning(f"Strategy system unavailable: {e}, falling back to standard")
                return [tech, intel, dec]

        return [tech, intel, dec]  # standard

    # ================================================================
    # Context builder
    # ================================================================

    def _build_context(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentContext:
        ctx = AgentContext(query=task)
        if context:
            ctx.stock_code = context.get("stock_code", "")
            ctx.stock_name = context.get("stock_name", "")
            for key in ("realtime_quote", "daily_history"):
                if context.get(key):
                    ctx.set_data(key, context[key])
        if not ctx.stock_code:
            ctx.stock_code = self._extract_stock_code(task)
        return ctx

    @staticmethod
    def _extract_stock_code(text: str) -> str:
        """Extract 6-digit stock code from text."""
        import re
        codes = re.findall(r'\b\d{6}\b', text)
        return codes[0] if codes else ""

    # ================================================================
    # Risk override
    # ================================================================

    def _apply_risk_override(self, ctx: AgentContext) -> None:
        if ctx.get_data("risk_override_applied"):
            return
        dashboard = ctx.get_data("final_dashboard")
        if not isinstance(dashboard, dict):
            return

        risk_opinion = next((op for op in reversed(ctx.opinions) if op.agent_name == "risk"), None)
        risk_raw = risk_opinion.raw_data if risk_opinion and isinstance(risk_opinion.raw_data, dict) else {}

        adjustment = str(risk_raw.get("signal_adjustment", "")).lower()
        has_high_flag = any(str(f.get("severity", "")).lower() == "high" for f in ctx.risk_flags)
        veto_buy = bool(risk_raw.get("veto_buy")) or adjustment == "veto" or has_high_flag

        current_signal = normalize_decision_signal(dashboard.get("decision_type", "hold"))
        if current_signal == "buy" and (veto_buy or adjustment in ("downgrade_two", "veto")):
            dashboard["decision_type"] = "hold"
            dashboard["risk_warning"] = "[风险否决] 高风险信号覆盖，买入建议已被否决。"
        elif current_signal == "hold" and adjustment == "veto":
            dashboard["decision_type"] = "sell"
            dashboard["risk_warning"] = "[风险否决] 高风险触发强行卖出。"
        elif current_signal == "buy" and adjustment == "downgrade_one":
            dashboard["decision_type"] = "hold"
            dashboard["risk_warning"] = "[风险降级] 因高风险将买入降级为持有。"

        ctx.set_data("risk_override_applied", True)

    # ================================================================
    # Dashboard normalization (simplified)
    # ================================================================

    def _resolve_final_output(self, ctx: AgentContext) -> tuple:
        """Return (dashboard_dict, content_str)."""
        dashboard = ctx.get_data("final_dashboard")
        if isinstance(dashboard, dict):
            normalized = self._normalize_dashboard(dashboard, ctx)
            if normalized:
                ctx.set_data("final_dashboard", normalized)
                self._apply_risk_override(ctx)
                overridden = ctx.get_data("final_dashboard")
                return overridden, json.dumps(overridden, ensure_ascii=False, indent=2)
        return None, self._fallback_summary(ctx)

    def _normalize_dashboard(self, payload: Dict[str, Any], ctx: AgentContext) -> Optional[Dict[str, Any]]:
        """Normalize and fill in missing fields."""
        payload = dict(payload)
        # Ensure minimum dashboard shape
        base_opinion = self._select_base_opinion(ctx)
        decision_type = normalize_decision_signal(payload.get("decision_type") or (base_opinion.signal if base_opinion else "hold"))
        confidence = float(base_opinion.confidence if base_opinion else 0.5)

        sentiment_score = payload.get("sentiment_score")
        try:
            sentiment_score = int(sentiment_score)
        except (TypeError, ValueError):
            sentiment_score = _estimate_sentiment_score(decision_type, confidence)

        db = payload.get("dashboard", {})
        if not isinstance(db, dict):
            db = {}
        core = db.get("core_conclusion", {})
        if not isinstance(core, dict):
            core = {}
        intelligence = db.get("intelligence", {})
        if not isinstance(intelligence, dict):
            intelligence = {}
        battle = db.get("battle_plan", {})
        if not isinstance(battle, dict):
            battle = {}
        sniper = battle.get("sniper_points", {})
        if not isinstance(sniper, dict):
            sniper = {}

        # Fill required fields
        analysis_summary = _first_non_empty_text(
            payload.get("analysis_summary"), core.get("one_sentence"),
            getattr(base_opinion, "reasoning", ""),
        ) or f"多 Agent 分析完成，当前按{_signal_to_operation(decision_type)}处理。"

        position_advice = _default_position_advice(decision_type)
        core.setdefault("one_sentence", _truncate_text(analysis_summary, 60))
        core.setdefault("signal_type", _signal_to_signal_type(decision_type))
        core.setdefault("time_sensitivity", "本周内")
        core["position_advice"] = position_advice

        sniper.setdefault("stop_loss", "待补充")
        sniper.setdefault("take_profit", "N/A")
        battle["sniper_points"] = sniper
        battle.setdefault("position_strategy", {
            "suggested_position": _default_position_size(decision_type),
            "entry_plan": position_advice["no_position"],
            "risk_control": f"止损参考 {sniper.get('stop_loss', '待补充')}",
        })

        risk_alerts = self._collect_risk_alerts(ctx, intelligence)
        if risk_alerts and not intelligence.get("risk_alerts"):
            intelligence["risk_alerts"] = risk_alerts
        if not intelligence.get("latest_news"):
            news = _extract_latest_news_title(intelligence)
            if news:
                intelligence["latest_news"] = news

        db["core_conclusion"] = core
        db["intelligence"] = intelligence
        db["battle_plan"] = battle

        payload["stock_name"] = _first_non_empty_text(payload.get("stock_name"), ctx.stock_name, ctx.stock_code)
        payload["sentiment_score"] = sentiment_score
        payload["decision_type"] = decision_type
        payload["confidence_level"] = _confidence_label(confidence)
        payload["analysis_summary"] = _truncate_text(analysis_summary, 220)
        payload["trend_prediction"] = payload.get("trend_prediction", "待确认")
        payload["operation_advice"] = _signal_to_operation(decision_type)
        payload["key_points"] = payload.get("key_points", [])
        payload["risk_warning"] = _first_non_empty_text(
            payload.get("risk_warning"), "；".join(risk_alerts[:3]),
        ) or "暂无额外风险提示"
        payload["dashboard"] = db
        return payload

    def _collect_risk_alerts(self, ctx: AgentContext, intelligence: Dict[str, Any]) -> List[str]:
        alerts = []
        for item in intelligence.get("risk_alerts", []):
            text = str(item).strip() if isinstance(item, str) else str(item.get("description", "")).strip() if isinstance(item, dict) else ""
            if text and text not in alerts:
                alerts.append(text)
        intel = next((op for op in reversed(ctx.opinions) if op.agent_name == "intel"), None)
        if intel and isinstance(intel.raw_data, dict):
            for item in intel.raw_data.get("risk_alerts", []):
                text = str(item).strip() if isinstance(item, str) else ""
                if text and text not in alerts:
                    alerts.append(text)
        for flag in ctx.risk_flags:
            desc = str(flag.get("description", "")).strip()
            if desc and desc not in alerts:
                alerts.append(desc)
        return alerts[:8]

    def _fallback_summary(self, ctx: AgentContext) -> str:
        lines = [f"# Analysis Summary: {ctx.stock_code} ({ctx.stock_name})", ""]
        for op in ctx.opinions:
            lines.append(f"## {op.agent_name}")
            lines.append(f"Signal: {op.signal} (confidence: {op.confidence:.0%})")
            lines.append(op.reasoning)
            lines.append("")
        if ctx.risk_flags:
            lines.append("## Risk Flags")
            for rf in ctx.risk_flags:
                lines.append(f"- [{rf['severity']}] {rf['description']}")
        return "\n".join(lines)

    @staticmethod
    def _select_base_opinion(ctx: AgentContext) -> Optional[AgentOpinion]:
        preferred = ({"decision"}, {"technical"}, {"intel"}, {"risk"})
        for names in preferred:
            for op in reversed(ctx.opinions):
                if op.agent_name in names:
                    return op
        return ctx.opinions[-1] if ctx.opinions else None
