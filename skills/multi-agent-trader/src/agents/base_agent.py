# -*- coding: utf-8 -*-
"""BaseAgent — abstract base for all specialised agents."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from protocols import AgentContext, AgentOpinion, StageResult, StageStatus
from runner import run_agent_loop, RunLoopResult
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base for all specialised agents."""

    agent_name: str = "base"
    tool_names: Optional[List[str]] = None  # None = all tools
    max_steps: int = 6

    def __init__(
        self,
        tool_registry: ToolRegistry,
        skill_instructions: str = "",
        technical_skill_policy: str = "",
    ):
        self.tool_registry = tool_registry
        self.skill_instructions = skill_instructions
        self.technical_skill_policy = technical_skill_policy

    @abstractmethod
    def system_prompt(self, ctx: AgentContext) -> str:
        ...

    @abstractmethod
    def build_user_message(self, ctx: AgentContext) -> str:
        ...

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        return None

    def run(
        self,
        ctx: AgentContext,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> StageResult:
        t0 = time.time()
        result = StageResult(stage_name=self.agent_name, status=StageStatus.RUNNING)
        try:
            messages = self._build_messages(ctx)
            registry = self._filtered_registry()
            loop_result: RunLoopResult = run_agent_loop(
                messages=messages,
                tool_registry=registry,
                max_steps=self.max_steps,
                progress_callback=progress_callback,
                max_wall_clock_seconds=timeout_seconds,
            )
            result.duration_s = round(time.time() - t0, 2)
            result.tokens_used = loop_result.total_tokens
            result.tool_calls_count = len(loop_result.tool_calls_log)
            result.meta["tool_calls_log"] = loop_result.tool_calls_log
            result.meta["models_used"] = loop_result.models_used
            result.meta["raw_text"] = loop_result.content

            if loop_result.success or loop_result.content:
                opinion = self.post_process(ctx, loop_result.content)
                if opinion:
                    ctx.add_opinion(opinion)
                    result.opinion = opinion
                result.status = StageStatus.COMPLETED
            else:
                result.status = StageStatus.FAILED
                result.error = loop_result.error or "Agent returned empty response"
        except Exception as e:
            result.status = StageStatus.FAILED
            result.error = str(e)
            result.duration_s = round(time.time() - t0, 2)
            logger.exception(f"[{self.agent_name}] run failed: {e}")
        return result

    def _build_messages(self, ctx: AgentContext) -> List[Dict[str, Any]]:
        """Build the messages list: system prompt + user message with cached data."""
        sys_prompt = self.system_prompt(ctx)
        cached = self._inject_cached_data(ctx)
        user_msg = self.build_user_message(ctx)
        messages = [{"role": "system", "content": sys_prompt}]
        if cached:
            messages.append({"role": "system", "content": f"## Pre-fetched Data\n\n{cached}"})
        messages.append({"role": "user", "content": user_msg})
        return messages

    def _inject_cached_data(self, ctx: AgentContext) -> str:
        """Build context string from already-fetched data."""
        import json
        parts = []
        for key, value in ctx.data.items():
            if value is not None:
                try:
                    serialised = json.dumps(value, ensure_ascii=False, default=str)
                except (TypeError, ValueError):
                    serialised = str(value)
                if len(serialised) > 8000:
                    serialised = serialised[:8000] + "...(truncated)"
                parts.append(f"[Pre-fetched: {key}]\n{serialised}")
        return "\n\n".join(parts) if parts else ""

    def _filtered_registry(self) -> ToolRegistry:
        """Return ToolRegistry restricted to self.tool_names."""
        if self.tool_names is None:
            return self.tool_registry
        filtered = ToolRegistry()
        for name in self.tool_names:
            tool_def = self.tool_registry.get(name)
            if tool_def:
                filtered.register(tool_def)
            else:
                logger.warning(f"[{self.agent_name}] tool '{name}' not found")
        return filtered
