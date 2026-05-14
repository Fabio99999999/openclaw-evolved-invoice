# -*- coding: utf-8 -*-
"""Shared protocols — common data structures for multi-agent communication."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Signal(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


_CANONICAL_DECISION_SIGNAL_MAP: Dict[str, str] = {
    "strong_buy": "buy", "buy": "buy", "hold": "hold",
    "sell": "sell", "strong_sell": "sell",
}


def normalize_decision_signal(signal: Any, default: str = "hold") -> str:
    if not isinstance(signal, str):
        return default
    return _CANONICAL_DECISION_SIGNAL_MAP.get(signal.strip().lower(), default)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentContext:
    """Shared context carried across all agents in a single run."""
    query: str = ""
    stock_code: str = ""
    stock_name: str = ""
    session_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    opinions: List["AgentOpinion"] = field(default_factory=list)
    risk_flags: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def add_opinion(self, opinion: "AgentOpinion") -> None:
        if opinion.timestamp == 0:
            opinion.timestamp = time.time()
        self.opinions.append(opinion)

    def add_risk_flag(self, category: str, description: str, severity: str = "medium") -> None:
        self.risk_flags.append({
            "category": category, "description": description,
            "severity": severity, "timestamp": time.time(),
        })

    def get_data(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        self.data[key] = value

    @property
    def has_risk_flags(self) -> bool:
        return len(self.risk_flags) > 0


@dataclass
class AgentOpinion:
    """One agent's analysis opinion."""
    agent_name: str = ""
    signal: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    key_levels: Dict[str, float] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def signal_enum(self) -> Optional[Signal]:
        try:
            return Signal(self.signal)
        except ValueError:
            return None


@dataclass
class StageResult:
    """Outcome of one pipeline stage."""
    stage_name: str = ""
    status: StageStatus = StageStatus.PENDING
    opinion: Optional[AgentOpinion] = None
    error: Optional[str] = None
    duration_s: float = 0.0
    tokens_used: int = 0
    tool_calls_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == StageStatus.COMPLETED


@dataclass
class AgentRunStats:
    """Aggregate run statistics."""
    total_stages: int = 0
    completed_stages: int = 0
    failed_stages: int = 0
    skipped_stages: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_duration_s: float = 0.0
    models_used: List[str] = field(default_factory=list)
    stage_results: List[StageResult] = field(default_factory=list)

    def record_stage(self, result: StageResult) -> None:
        self.stage_results.append(result)
        self.total_stages += 1
        self.total_tokens += result.tokens_used
        self.total_tool_calls += result.tool_calls_count
        self.total_duration_s += result.duration_s
        if result.status == StageStatus.COMPLETED:
            self.completed_stages += 1
        elif result.status == StageStatus.FAILED:
            self.failed_stages += 1
        elif result.status == StageStatus.SKIPPED:
            self.skipped_stages += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "failed_stages": self.failed_stages,
            "skipped_stages": self.skipped_stages,
            "total_tokens": self.total_tokens,
            "total_tool_calls": self.total_tool_calls,
            "total_duration_s": round(self.total_duration_s, 2),
            "models_used": self.models_used,
        }


# ============== Helper functions ==============

_COERCED_LEVEL_VALUES = {"null", "none", "n/a", "na", "待补充", "undefined"}


def _coerce_level_value(value: Any) -> Optional[float]:
    """Convert a level value to float; return None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().lower().replace(",", "").replace("¥", "").replace("$", "")
        if stripped in _COERCED_LEVEL_VALUES or not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _level_values_equal(a: Any, b: Any) -> bool:
    """Check if two level values are equal (or None-equivalent)."""
    if a is b:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    return _coerce_level_value(a) == _coerce_level_value(b)


def _first_non_empty_text(*args: Any) -> str:
    for arg in args:
        if arg and isinstance(arg, str) and arg.strip():
            return arg.strip()
    return ""


def _signal_to_operation(signal: str) -> str:
    mapping = {"buy": "买入", "strong_buy": "买入", "hold": "持有",
               "sell": "卖出", "strong_sell": "卖出"}
    return mapping.get(signal.strip().lower(), "持有")


def _signal_to_signal_type(signal: str) -> str:
    mapping = {"buy": "bullish", "strong_buy": "strong_bullish",
               "hold": "neutral", "sell": "bearish", "strong_sell": "strong_bearish"}
    return mapping.get(signal.strip().lower(), "neutral")


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    return "low"


def _pick_first_level(*args: Any) -> Optional[float]:
    for arg in args:
        v = _coerce_level_value(arg)
        if v is not None:
            return v
    return None


def _truncate_text(text: str, max_len: int = 220) -> str:
    if not text:
        return ""
    return text[:max_len] + "…" if len(text) > max_len else text


def _estimate_sentiment_score(decision_type: str, confidence: float) -> int:
    base = {"buy": 75, "strong_buy": 85, "hold": 50, "sell": 35, "strong_sell": 20}
    return int(base.get(decision_type, 50) * confidence)


def _default_position_advice(decision_type: str) -> Dict[str, str]:
    if decision_type in ("buy", "strong_buy"):
        return {"no_position": "可考虑逢低建仓", "has_position": "现有仓位可继续持有"}
    elif decision_type in ("sell", "strong_sell"):
        return {"no_position": "建议观望", "has_position": "考虑减仓或止损"}
    return {"no_position": "观望为主", "has_position": "持有观察"}


def _default_position_size(decision_type: str) -> str:
    return {"buy": "20%", "strong_buy": "30%", "hold": "10%",
            "sell": "0%", "strong_sell": "0%"}.get(decision_type, "10%")


def _normalize_operation_advice_value(value: Any, decision_type: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("recommendation", "advice", "summary", "main"):
            if isinstance(value.get(k), str) and value[k].strip():
                return value[k].strip()
    return _signal_to_operation(decision_type)


def _extract_latest_news_title(intelligence: Dict[str, Any]) -> Optional[str]:
    for key in ("latest_news", "key_news", "news", "top_news"):
        news = intelligence.get(key, [])
        if isinstance(news, list) and news:
            item = news[0]
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                return str(item.get("title", "") or "")
    return None
