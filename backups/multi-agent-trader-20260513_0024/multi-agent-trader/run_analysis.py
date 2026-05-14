#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Agent Trader — CLI entry point for stock analysis.

Usage:
    # Quick technical analysis (2 agents)
    python run_analysis.py 600519 --mode quick

    # Standard analysis with news (3 agents, default)
    python run_analysis.py 002415

    # Full analysis with risk (4 agents)
    python run_analysis.py 000001 --mode full --name "平安银行"

    # Batch analysis
    python run_analysis.py batch --codes 600519,000001,002415 --mode standard
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from orchestrator import AgentOrchestrator
from tools.registry import ToolRegistry
from tools.facecat_tools import register_all_facecat_tools
from tools.search_tools import register_all_search_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_analysis")


def build_registry() -> ToolRegistry:
    """Create and populate the ToolRegistry."""
    reg = ToolRegistry()
    register_all_facecat_tools(reg)
    register_all_search_tools(reg)
    return reg


def single_stock_analysis(
    code: str,
    name: str = "",
    mode: str = "standard",
    output_json: bool = False,
    output_file: Optional[str] = None,
) -> str:
    """Analyze a single stock and return the report."""
    registry = build_registry()
    orchestrator = AgentOrchestrator(
        tool_registry=registry,
        mode=mode,
        max_steps=12,
    )

    print(f"\n{'='*60}")
    print(f"  多 Agent 分析: {code} {f'({name})' if name else ''}")
    print(f"  模式: {mode.upper()}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    result = orchestrator.run_analysis(code, name, mode=mode)

    if output_json and result.dashboard:
        output = json.dumps(result.dashboard, ensure_ascii=False, indent=2)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"\nDashboard saved to: {output_file}")
        return output
    elif result.content:
        return result.content
    else:
        return f"分析失败: {result.error or '未知错误'}"


def batch_analysis(
    codes: List[str],
    names: Dict[str, str],
    mode: str = "standard",
    output_json: bool = False,
) -> str:
    """Run multi-stock analysis with portfolio agent."""
    registry = build_registry()
    orchestrator = AgentOrchestrator(
        tool_registry=registry,
        mode="standard",  # portfolio always uses standard
        max_steps=12,
    )

    reports = []
    stock_opinions = {}

    for idx, code in enumerate(codes):
        name = names.get(code, "")
        print(f"\n[{idx+1}/{len(codes)}] Analyzing {code} ({name})...")
        result = orchestrator.run_analysis(code, name)
        if result.dashboard:
            stock_opinions[code] = result.dashboard
            reports.append(result.content)
        else:
            reports.append(f"{code}: {result.error or 'failed'}")

    # Portfolio analysis (if > 1 stock)
    if len(codes) > 1:
        print(f"\n{'='*60}")
        print("  Portfolio Analysis")
        print(f"{'='*60}\n")
        ctx = orchestrator._build_context("Portfolio analysis", {})
        ctx.data["stock_list"] = codes
        ctx.data["stock_opinions"] = stock_opinions
        from agents.portfolio_agent import PortfolioAgent
        pa = PortfolioAgent(tool_registry=registry)
        pa_result = pa.run(ctx)
        if pa_result.success and pa_result.opinion:
            reports.append(f"\n## Portfolio Assessment\n{pa_result.opinion.reasoning}")

    summary = "\n\n".join(reports)

    if output_json:
        output = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "stocks": codes,
            "mode": mode,
            "reports": stock_opinions,
        }, ensure_ascii=False, indent=2)
        print(output)
        return output

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Stock Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_analysis.py 600519                    # Standard analysis
  python run_analysis.py 600519 --mode full        # Full 4-agent pipeline
  python run_analysis.py 600519 --mode quick --json  # Quick + JSON output
  python run_analysis.py batch --codes 600519,000001 --names "贵州茅台,平安银行"
        """,
    )
    parser.add_argument("command", nargs="?", default="600519",
                        help="Stock code or 'batch'")
    parser.add_argument("--code", "-c", help="Stock code (alternative)")
    parser.add_argument("--name", "-n", default="", help="Stock name")
    parser.add_argument("--mode", "-m", default="standard",
                        choices=["quick", "standard", "full", "strategy", "strategy_full"],
                        help="Analysis mode (default: standard)")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output JSON dashboard")
    parser.add_argument("--output", "-o", help="Save output to file")
    parser.add_argument("--codes", help="Comma-separated codes for batch")
    parser.add_argument("--names", help="Comma-separated names for batch")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.command == "batch" or args.command.startswith("batch"):
        if not args.codes:
            parser.error("Batch mode requires --codes")
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        names = {}
        if args.names:
            name_parts = [n.strip() for n in args.names.split(",")]
            for code, n in zip(codes, name_parts):
                names[code] = n
        result = batch_analysis(codes, names, args.mode, args.json)
        if result:
            print(result)
        return

    # Single stock analysis
    code = args.code or args.command
    result = single_stock_analysis(
        code=code,
        name=args.name,
        mode=args.mode,
        output_json=args.json,
        output_file=args.output,
    )
    if result:
        print(result)


if __name__ == "__main__":
    main()
