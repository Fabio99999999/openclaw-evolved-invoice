"""Load and manage trading strategies from YAML files."""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

STRATEGIES_DIR = Path(__file__).resolve().parent.parent.parent / "strategies"


@dataclass
class Strategy:
    """A trading strategy loaded from a YAML file.

    Each strategy is a detailed reasoning template written in natural language,
    describing a specific trading pattern or analysis framework.
    """

    name: str
    display_name: str
    description: str
    instructions: str
    category: str = "trend"
    core_rules: List[int] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    default_priority: int = 100
    default_active: bool = False
    default_router: bool = False
    market_regimes: List[str] = field(default_factory=list)


# ── Cache ──────────────────────────────────────────────────────────

_cache: Dict[str, Strategy] = {}
_loaded = False


def _parse_yaml_simple(text: str) -> dict:
    """Parse YAML key-value pairs + instructions block.

    Handles our specific format:
        # comments
        key: value
        key: [list, items]
        key: |
          multi-line string
    """
    result = {}
    lines = text.split("\n")
    i = 0
    instructions_start = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip comment lines
        if stripped.startswith("#"):
            i += 1
            continue

        # Empty line
        if not stripped:
            i += 1
            continue

        # Check for instructions: |  or instructions: >
        if stripped.startswith("instructions:"):
            instructions_start = i
            break

        # YAML dash-list: - item
        if stripped.startswith("- "):
            if current_list_key is not None:
                item = stripped[2:].strip().strip('"').strip("'")
                result.setdefault(current_list_key, []).append(item)
            i += 1
            continue

        # Parse key: value
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            # Handle list values like [a, b, c]
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                items = [
                    item.strip().strip('"').strip("'")
                    for item in inner.split(",")
                    if item.strip()
                ]
                result[key] = items
                current_list_key = None
            elif val == "":
                # Key followed by dash-list items on next lines
                current_list_key = key
                result[key] = []
            else:
                result[key] = val
                current_list_key = None
        else:
            current_list_key = None

        i += 1

    current_list_key = None

    # Extract instructions (multi-line block after "instructions: |")

    # Extract instructions (multi-line block after "instructions: |")
    if instructions_start is not None:
        instr_lines = []
        started = False
        for j in range(instructions_start, len(lines)):
            line_text = lines[j]
            if not started:
                # Skip the "instructions: |" line itself
                started = True
                continue
            if line_text.strip() == "" and instr_lines and instr_lines[-1].strip() == "":
                # Skip double empty lines
                pass
            else:
                instr_lines.append(line_text)

        # Strip leading/trailing empty lines
        while instr_lines and not instr_lines[0].strip():
            instr_lines.pop(0)
        while instr_lines and not instr_lines[-1].strip():
            instr_lines.pop()

        result["instructions"] = "\n".join(instr_lines)

    return result


def _parse_list_value(val: str) -> List[str]:
    """Parse a string that may be a YAML list: [item1, item2, item3]"""
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1]
        items = [item.strip().strip("'").strip('"') for item in inner.split(",") if item.strip()]
        return items
    return [val] if val else []


def _parse_list_int_value(val: str) -> List[int]:
    """Parse a string that may be a YAML list of ints: [1, 2, 3]"""
    items = _parse_list_value(val)
    nums = []
    for item in items:
        try:
            nums.append(int(item))
        except (ValueError, TypeError):
            pass
    return nums


def load_strategies(force_reload: bool = False) -> Dict[str, Strategy]:
    """Load all strategies from the strategies directory."""
    global _loaded, _cache
    if _loaded and not force_reload:
        return _cache

    _cache = {}
    if not STRATEGIES_DIR.exists():
        logger.warning(f"Strategies directory not found: {STRATEGIES_DIR}")
        return _cache

    for fpath in sorted(STRATEGIES_DIR.glob("*.yaml")):
        try:
            text = fpath.read_text("utf-8")
            data = _parse_yaml_simple(text)

            name = data.get("name", fpath.stem)
            display_name = data.get("display_name", name)
            description = data.get("description", "")
            instructions = data.get("instructions", description)
            category = data.get("category", "trend")

            core_rules = data.get("core_rules", [])
            if isinstance(core_rules, list):
                core_rules = [int(x) for x in core_rules if isinstance(x, int) or (isinstance(x, str) and x.strip().isdigit())]
            else:
                core_rules = _parse_list_int_value(str(core_rules))

            required_tools = data.get("required_tools", [])
            if isinstance(required_tools, str):
                required_tools = _parse_list_value(required_tools)

            aliases = data.get("aliases", [])
            if isinstance(aliases, str):
                aliases = _parse_list_value(aliases)

            try:
                default_priority = int(data.get("default_priority", 100))
            except (ValueError, TypeError):
                default_priority = 100

            default_active = str(data.get("default_active", "false")).lower() in ("true", "yes", "1")
            default_router = str(data.get("default_router", "false")).lower() in ("true", "yes", "1")

            market_regimes = data.get("market_regimes", [])
            if isinstance(market_regimes, str):
                market_regimes = _parse_list_value(market_regimes)

            strategy = Strategy(
                name=name,
                display_name=display_name,
                description=description,
                instructions=instructions,
                category=category,
                core_rules=core_rules,
                required_tools=[t.strip() for t in required_tools if t.strip()],
                aliases=[a.strip() for a in aliases if a.strip()],
                default_priority=default_priority,
                default_active=default_active,
                default_router=default_router,
                market_regimes=[r.strip() for r in market_regimes if r.strip()],
            )
            _cache[name] = strategy
            logger.debug(f"Loaded strategy: {name}")
        except Exception as e:
            logger.warning(f"Failed to load strategy {fpath.name}: {e}")

    _loaded = True
    if _cache:
        logger.info(f"Loaded {len(_cache)} strategies: {', '.join(_cache.keys())}")
    return _cache


def get_strategy(name: str) -> Optional[Strategy]:
    """Get a single strategy by name."""
    strategies = load_strategies()
    return strategies.get(name)


def list_strategies(category: Optional[str] = None, regime: Optional[str] = None) -> List[Strategy]:
    """List strategies, optionally filtered by category or market regime."""
    strategies = load_strategies()
    result = []
    for s in strategies.values():
        if category and s.category != category:
            continue
        if regime and regime not in s.market_regimes:
            continue
        result.append(s)
    return sorted(result, key=lambda x: x.default_priority)


def get_strategies_by_regime(regime: str, max_count: int = 3) -> List[Strategy]:
    """Get strategies matching a market regime, sorted by priority."""
    matched = []
    for s in load_strategies().values():
        if regime in s.market_regimes:
            matched.append(s)
    matched.sort(key=lambda x: x.default_priority)
    return matched[:max_count]
