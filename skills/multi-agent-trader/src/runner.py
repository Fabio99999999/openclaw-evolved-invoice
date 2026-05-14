# -*- coding: utf-8 -*-
"""Shared LLM + tool execution loop for multi-agent system."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

import os
import json as _json

# Provider proxy (port 3457) + UIUIAPI direct fallback
_UIUI_KEY = ""
_provider_file = os.path.expanduser("~/.openclaw/provider-proxy/providers.json")
if not _UIUI_KEY and os.path.exists(_provider_file):
    try:
        with open(_provider_file) as _pf:
            _pd = _json.load(_pf)
        _active = _pd.get("activeId", "")
        for _p in _pd.get("providers", []):
            if _p["id"] == _active:
                _UIUI_KEY = _p.get("apiKey", "")
                break
        if not _UIUI_KEY and _pd.get("providers"):
            _UIUI_KEY = _pd["providers"][0].get("apiKey", "")
    except Exception:
        pass

LLM_API_URLS = [
    "http://localhost:3457/v1/chat/completions",  # Provider proxy (Anthropic-format, may not work)
    "https://sg.uiuiapi.com/v1/chat/completions",   # UIUIAPI direct (with API key)
]
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", _UIUI_KEY)
LLM_MODEL = "deepseek-chat"

_THINKING_TOOL_LABELS: Dict[str, str] = {
    "get_realtime_quote": "行情获取",
    "get_daily_history": "K线数据获取",
    "analyze_trend": "技术指标分析",
    "get_chip_distribution": "筹码分布分析",
    "search_stock_news": "新闻搜索",
    "search_comprehensive_intel": "综合情报搜索",
    "get_market_indices": "市场概览获取",
    "get_stock_info": "基本信息获取",
    "analyze_pattern": "K线形态识别",
    "get_volume_analysis": "量能分析",
    "calculate_ma": "均线计算",
}


@dataclass
class RunLoopResult:
    success: bool = False
    content: str = ""
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)
    total_steps: int = 0
    total_tokens: int = 0
    provider: str = ""
    models_used: List[str] = field(default_factory=list)
    error: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def model(self) -> str:
        return ", ".join(dict.fromkeys(m for m in self.models_used if m))


# ==== LLM API ====

class LLMResponse:
    def __init__(self, content: str = "", tool_calls: Optional[List] = None,
                 provider: str = "openai", usage: Optional[Dict] = None,
                 model: str = "", reasoning_content: Optional[str] = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.provider = provider
        self.usage = usage or {}
        self.model = model or provider
        self.reasoning_content = reasoning_content


def _call_llm(messages: List[Dict], tools: List[Dict] = None,
              timeout: Optional[float] = None) -> LLMResponse:
    """Call LLM via Provider Proxy (LiteLLM /v1/chat/completions compatible)."""
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools

    import urllib.request as _req
    last_error = ""
    result = None
    cc = 0
    for url in LLM_API_URLS:
        cc += 1
        try:
            headers = {"Content-Type": "application/json"}
            if "uiuiapi.com" in url and DEEPSEEK_API_KEY:
                headers["Authorization"] = f"Bearer {DEEPSEEK_API_KEY}"
            body = json.dumps(payload).encode("utf-8")
            req = _req.Request(url, data=body, headers=headers, method="POST")
            kw = {"timeout": timeout or 60}
            with _req.urlopen(req, **kw) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if cc > 1:
                    logger.info(f"LLM: using direct UIUIAPI endpoint")
                break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM call to {url} ({cc}) failed: {e}")
            result = None
            continue
    if result is None:
        logger.error(f"All LLM endpoints failed: {last_error}")
        return LLMResponse(content=last_error, provider="error", usage={})

    if "error" in result:
        return LLMResponse(content=result["error"], provider="error", usage={})

    choice = result.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content", "") or ""
    tool_calls_raw = message.get("tool_calls")

    class _ToolCall:
        """Simple named tuple-like tool call."""
        def __init__(self, tid: str, name: str, arguments: dict):
            self.id = tid
            self.name = name
            self.arguments = arguments

    tc_list = []
    if tool_calls_raw:
        for tc in tool_calls_raw:
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {"raw": args_str}
            tc_list.append(_ToolCall(
                tid=tc.get("id", f"call_{len(tc_list)}"),
                name=func.get("name", ""),
                arguments=args if isinstance(args, dict) else {},
            ))

    usage = result.get("usage", {})
    model = result.get("model", LLM_MODEL)
    reasoning = message.get("reasoning_content") or choice.get("reasoning_content")

    return LLMResponse(
        content=content,
        tool_calls=tc_list,
        provider="openai",
        usage={"total_tokens": usage.get("total_tokens", 0)},
        model=model,
        reasoning_content=reasoning,
    )


# ==== JSON Parse Utilities ====

def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    candidates = []
    cleaned = text.strip()
    if cleaned:
        candidates.append(cleaned)
    if cleaned.startswith("```"):
        unfenced = re.sub(r'^```(?:json)?\s*', '', cleaned)
        unfenced = re.sub(r'\s*```$', '', unfenced)
        if unfenced:
            candidates.append(unfenced.strip())
    fenced = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    for block in fenced:
        block = block.strip()
        if block:
            candidates.append(block)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start:end + 1].strip()
        if snippet:
            candidates.append(snippet)
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            continue
    try:
        from json_repair import repair_json
        for c in candidates:
            try:
                repaired = repair_json(c)
                obj = json.loads(repaired)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    except ImportError:
        pass
    return None


def parse_dashboard_json(content: str) -> Optional[Dict[str, Any]]:
    return try_parse_json(content)


def serialize_tool_result(result: Any, max_chars: int = 4000) -> str:
    """Serialize tool result, truncating to max_chars."""
    if result is None:
        return json.dumps({"result": None})
    if isinstance(result, str):
        return result[:max_chars]
    if isinstance(result, (dict, list)):
        try:
            s = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            s = str(result)
        if len(s) > max_chars:
            # Try to intelligently truncate dict/list
            if isinstance(result, dict):
                truncated = {k: v for k, v in result.items() 
                             if k not in ("klines", "messages", "results") 
                             or isinstance(v, (str, int, float, bool))}
                s = json.dumps(truncated, ensure_ascii=False, default=str)
            if len(s) > max_chars:
                s = s[:max_chars] + "... (truncated)"
        return s
    return str(result)


# ==== Core Loop ====

def run_agent_loop(
    *,
    messages: List[Dict[str, Any]],
    tool_registry: ToolRegistry,
    llm_adapter: Any = None,
    max_steps: int = 6,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    thinking_labels: Optional[Dict[str, str]] = None,
    max_wall_clock_seconds: Optional[float] = None,
    tool_call_timeout_seconds: Optional[float] = None,
) -> RunLoopResult:
    """Execute the ReAct LLM ↔ tool loop. OpenClaw adapted version."""
    labels = thinking_labels or _THINKING_TOOL_LABELS
    tool_decls = tool_registry.to_openai_tools()

    start_time = time.time()
    tool_calls_log: List[Dict[str, Any]] = []
    total_tokens = 0
    models_used: List[str] = []

    for step in range(max_steps):
        elapsed = time.time() - start_time
        if max_wall_clock_seconds and elapsed >= max_wall_clock_seconds:
            return RunLoopResult(
                success=False, error=f"Timed out after {elapsed:.1f}s",
                tool_calls_log=tool_calls_log, total_tokens=total_tokens,
                total_steps=step, models_used=models_used, messages=messages,
            )

        logger.info("Agent step %d/%d", step + 1, max_steps)

        if progress_callback:
            if not tool_calls_log:
                progress_callback({"type": "thinking", "step": step + 1, "message": "正在制定分析路径..."})
            else:
                last_tool = tool_calls_log[-1].get("tool", "")
                label = labels.get(last_tool, last_tool)
                progress_callback({"type": "thinking", "step": step + 1, "message": f"「{label}」已完成，继续分析..."})

        # LLM call
        remaining = max(0.0, (max_wall_clock_seconds or 60) - (time.time() - start_time)) if max_wall_clock_seconds else 60
        response = _call_llm(messages, tool_decls, timeout=min(remaining, 30))
        total_tokens += (response.usage or {}).get("total_tokens", 0)
        if response.model and response.model != "error":
            models_used.append(response.model)
        if response.provider == "error":
            return RunLoopResult(
                success=False, content=response.content, error=response.content,
                tool_calls_log=tool_calls_log, total_tokens=total_tokens,
                total_steps=step + 1, models_used=models_used, messages=messages,
            )

        if response.tool_calls:
            # Execute tools
            tc_list = []
            for tc in response.tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False) if hasattr(tc.arguments, 'keys') else str(tc.arguments),
                    }
                }
                tc_list.append(tc_dict)
            assistant_msg = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": tc_list,
            }
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                t0 = time.time()
                if progress_callback:
                    progress_callback({"type": "tool_start", "step": step + 1, "tool": tc.name})
                try:
                    res = tool_registry.execute(tc.name, **tc.arguments)
                    res_str = serialize_tool_result(res)
                    ok = True
                except Exception as e:
                    res_str = json.dumps({"error": str(e)})
                    ok = False
                    logger.warning(f"Tool '{tc.name}' failed: {e}")

                dur = round(time.time() - t0, 2)
                if progress_callback:
                    progress_callback({"type": "tool_done", "step": step + 1, "tool": tc.name, "success": ok, "duration": dur})
                tool_calls_log.append({
                    "step": step + 1, "tool": tc.name, "arguments": tc.arguments,
                    "success": ok, "duration": dur, "result_length": len(res_str),
                })
                # Truncate tool content to avoid API 500 errors
                if len(res_str) > 3000:
                    res_str = res_str[:3000] + "... (工具数据过长，已截断)"
                messages.append({
                    "role": "tool", "name": tc.name,
                    "tool_call_id": tc.id, "content": res_str,
                })
        else:
            # Final answer
            logger.info("Agent complete: %d steps, %d tokens", step + 1, total_tokens)
            if progress_callback:
                progress_callback({"type": "generating", "step": step + 1, "message": "分析完成"})
            return RunLoopResult(
                success=True,
                content=response.content or "",
                tool_calls_log=tool_calls_log,
                total_steps=step + 1,
                total_tokens=total_tokens,
                provider="openai",
                models_used=models_used,
                messages=messages,
            )

    return RunLoopResult(
        success=False, error=f"Exceeded max steps ({max_steps})",
        tool_calls_log=tool_calls_log, total_tokens=total_tokens,
        total_steps=max_steps, models_used=models_used, messages=messages,
    )
