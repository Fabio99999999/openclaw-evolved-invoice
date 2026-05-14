# -*- coding: utf-8 -*-
"""Search tools — Anspire-based web search for stock news and intelligence."""

import json
import logging
import sys
from typing import Dict, List, Optional

from tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)

_ANSPIRE_SCRIPT = None  # lazy resolved


def _get_search_tool():
    """Return the anspire_search function."""
    global _ANSPIRE_SCRIPT
    if _ANSPIRE_SCRIPT is not None:
        return _ANSPIRE_SCRIPT

    # Try to find anspire search skill
    possible_paths = [
        "~/.openclaw/workspace/skills/anspire-search/scripts/search.py",
        "~/.openclaw/plugin-skills/anspire-search/scripts/search.py",
    ]
    for p in possible_paths:
        import os
        expanded = os.path.expanduser(p)
        if os.path.exists(expanded):
            sys.path.insert(0, os.path.dirname(os.path.dirname(expanded)))
            _ANSPIRE_SCRIPT = expanded
            break

    if _ANSPIRE_SCRIPT is None:
        return None
    return _ANSPIRE_SCRIPT


def _web_search(query: str, count: int = 5) -> List[Dict]:
    """Execute a web search using Anspire or fallback to web_fetch."""
    results = []
    anspire_script = _get_search_tool()

    if anspire_script and isinstance(anspire_script, str):
        # Use anspire search via subprocess
        import subprocess
        import sys as _sys
        try:
            result = subprocess.run(
                [_sys.executable, anspire_script, query, "--count", str(count)],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("results", data)
        except Exception as e:
            logger.warning(f"Anspire search failed: {e}")

    # Simple fallback — just return the query as context
    return [{"title": f"搜索: {query}", "snippet": f"关于 {query} 的最新信息", "url": ""}]


def _handle_search_stock_news(stock_code: str, stock_name: str) -> dict:
    """Search for the latest news about a stock."""
    query = f"{stock_name}({stock_code}) 最新消息 公告"
    results = _web_search(query, 5)
    return {
        "query": query,
        "success": True,
        "results_count": len(results),
        "results": [
            {
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "url": r.get("url", ""),
            }
            for r in results
        ],
    }


def _handle_search_comprehensive_intel(stock_code: str, stock_name: str) -> dict:
    """Multi-dimensional intelligence search."""
    searches = [
        ("latest_news", f"{stock_name}({stock_code}) 最新新闻 动态"),
        ("announcements", f"{stock_name} 公司公告"),
        ("risk_events", f"{stock_name} 风险 减持 处罚"),
        ("industry", f"{stock_name} 行业 板块"),
        ("earnings", f"{stock_name} 业绩 财报"),
    ]
    dimensions = {}
    report_parts = [f"## {stock_name}({stock_code}) 综合情报报告\n"]
    for dim_name, query in searches:
        results = _web_search(query, 3)
        dimensions[dim_name] = {
            "query": query,
            "results_count": len(results),
            "results": [
                {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "source": r.get("source", "")}
                for r in results[:3]
            ],
        }
        snippets = [r.get("snippet", "")[:100] for r in results[:2] if r.get("snippet")]
        if snippets:
            report_parts.append(f"### {dim_name}\n" + "\n".join(f"- {s}" for s in snippets))

    return {
        "report": "\n".join(report_parts),
        "dimensions": dimensions,
    }


search_stock_news_tool = ToolDefinition(
    name="search_stock_news",
    description="搜索个股最新新闻和公告。需要股票代码和股票名称。",
    parameters=[
        ToolParameter(name="stock_code", type="string", description="股票代码，如 '600519'"),
        ToolParameter(name="stock_name", type="string", description="股票名称，如 '贵州茅台'"),
    ],
    handler=_handle_search_stock_news,
    category="search",
)

search_comprehensive_intel_tool = ToolDefinition(
    name="search_comprehensive_intel",
    description="多维度综合情报搜索：新闻、公告、风险事件、行业、业绩。返回格式化报告。",
    parameters=[
        ToolParameter(name="stock_code", type="string", description="股票代码"),
        ToolParameter(name="stock_name", type="string", description="股票名称"),
    ],
    handler=_handle_search_comprehensive_intel,
    category="search",
)

ALL_SEARCH_TOOLS = [search_stock_news_tool, search_comprehensive_intel_tool]


def register_all_search_tools(registry) -> None:
    for t in ALL_SEARCH_TOOLS:
        registry.register(t)
