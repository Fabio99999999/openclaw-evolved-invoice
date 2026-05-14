# -*- coding: utf-8 -*-
"""FaceCat/efinance data tools — adapted for OpenClaw multi-agent system."""

import json
import sys
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)

# ==== Data fetching helpers (reuse existing facecat_data.py patterns) ====

def _fetch_kline_efinance(code: str, days: int = 120) -> Optional[List[Dict]]:
    try:
        import efinance as ef
        end = datetime.now()
        start = end - timedelta(days=days * 2)
        df = ef.stock.get_quote_history(code, beg=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
        if df is None or df.empty:
            return None
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row.get("日期", "")),
                "open": float(row.get("开盘", 0) or 0),
                "close": float(row.get("收盘", 0) or 0),
                "high": float(row.get("最高", 0) or 0),
                "low": float(row.get("最低", 0) or 0),
                "volume": int(float(row.get("成交量", 0) or 0)),
                "amount": float(row.get("成交额", 0) or 0),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
            })
        records.sort(key=lambda r: r["date"])
        return records[-days:]
    except Exception as e:
        logger.warning(f"efinance history failed {code}: {e}")
    return None


def _fetch_realtime_efinance(codes: List[str]) -> Dict[str, Dict]:
    """Fetch realtime quotes via efinance. Uses get_latest_quote (replaces broken get_realtime_quotes)."""
    result = {}
    try:
        import efinance as ef
        df = ef.stock.get_latest_quote(codes)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                result[code] = {
                    "code": code,
                    "name": str(row.get("名称", "")),
                    "price": float(row.get("最新价", 0) or 0),
                    "change": float(row.get("涨跌幅", 0) or 0),
                    "change_amount": float(row.get("涨跌额", 0) or 0),
                    "open": float(row.get("今开", 0) or 0),
                    "high": float(row.get("最高", 0) or 0),
                    "low": float(row.get("最低", 0) or 0),
                    "pre_close": float(row.get("昨日收盘", 0) or 0),
                    "volume": int(float(row.get("成交量", 0) or 0)),
                    "amount": float(row.get("成交额", 0) or 0),
                    "turnover_rate": float(row.get("换手率", 0) or 0),
                    "pe": float(row.get("动态市盈率", 0) or 0),
                    "pb": 0.0,
                    "market_cap": float(row.get("总市值", 0) or 0),
                    "circulating_cap": float(row.get("流通市值", 0) or 0),
                    "volume_ratio": float(row.get("量比", 0) or 0),
                }
    except Exception as e:
        logger.warning(f"efinance realtime failed: {e}")
    return result


def _fetch_realtime_sina(code: str) -> Optional[Dict]:
    """Fallback: fetch single stock from Sina."""
    try:
        import urllib.request
        # Determine Sina symbol
        code_str = str(code).strip()
        if code_str.startswith("6") or code_str.startswith("9"):
            symbol = f"sh{code_str}"
        else:
            symbol = f"sz{code_str}"
        url = f"http://hq.sinajs.cn/list={symbol}"
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode("gbk")
        if "=" not in text:
            return None
        data = text.split('"')[1].split(",")
        if len(data) < 30:
            return None
        return {
            "code": code_str,
            "name": data[0],
            "open": float(data[1]) if data[1] else 0,
            "pre_close": float(data[2]) if data[2] else 0,
            "price": float(data[3]) if data[3] else 0,
            "high": float(data[4]) if data[4] else 0,
            "low": float(data[5]) if data[5] else 0,
            "volume": int(float(data[8])) if data[8] else 0,
            "amount": float(data[9]) if data[9] else 0,
            "change": float(data[32]) if len(data) > 32 and data[32] else 0,
            "circulating_cap": float(data[44]) if len(data) > 44 and data[44] else 0,
        }
    except Exception as e:
        logger.warning(f"Sina realtime failed {code}: {e}")
    return None


def _calculate_indicators(klines: List[Dict]) -> Dict[str, Any]:
    """Calculate technical indicators from kline data."""
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]
    n = len(closes)
    if n < 5:
        return {}

    def ma(data, period):
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    def rsi(data, period=14):
        if len(data) < period + 1:
            return None
        gains, losses = 0, 0
        for i in range(-period, 0):
            diff = data[i] - data[i - 1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def macd(data):
        if len(data) < 26:
            return {}
        ema12, ema26 = [], []
        for i in range(12):
            ema12.append(sum(data[:i+1]) / (i+1))
        for i in range(26):
            ema26.append(sum(data[:i+1]) / (i+1))
        ema12_val = sum(data[-12:]) / 12
        ema26_val = sum(data[-26:]) / 26
        alpha12, alpha26 = 2/13, 2/27
        for p in data[-12:]:
            ema12_val = p * alpha12 + ema12_val * (1 - alpha12)
        for p in data[-26:]:
            ema26_val = p * alpha26 + ema26_val * (1 - alpha26)
        dif = ema12_val - ema26_val
        dea = dif * 2/9 + sum([0])  # simplified
        bar = 2 * (dif - 0)
        return {"dif": round(dif, 4), "dea": round(0, 4), "bar": round(bar, 4)}

    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20) if n >= 20 else None
    rsi_val = rsi(closes, 14)
    macd_val = macd(closes)
    current_price = closes[-1] if closes else 0
    avg_vol_5d = sum(volumes[-5:]) / min(5, len(volumes)) if volumes else 0
    avg_vol_20d = sum(volumes[-20:]) / min(20, len(volumes)) if len(volumes) >= 20 else avg_vol_5d
    vol_ratio_5d = round(volumes[-1] / avg_vol_5d, 2) if avg_vol_5d > 0 else 1.0

    return {
        "current_price": round(current_price, 2),
        "ma5": round(ma5, 2) if ma5 else None,
        "ma10": round(ma10, 2) if ma10 else None,
        "ma20": round(ma20, 2) if ma20 else None,
        "ma5_above_ma10": ma5 > ma10 if ma5 and ma10 else None,
        "ma10_above_ma20": ma10 > ma20 if ma10 and ma20 else None,
        "rsi_14": round(rsi_val, 2) if rsi_val else None,
        "macd_dif": macd_val.get("dif"),
        "macd_bar": macd_val.get("bar"),
        "volume_ratio_5d": vol_ratio_5d,
        "avg_volume_5d": round(avg_vol_5d, 0),
        "avg_volume_20d": round(avg_vol_20d, 0),
    }


def _calculate_support_resistance(klines: List[Dict]) -> Dict[str, float]:
    """Find support and resistance levels."""
    highs = [k["high"] for k in klines[-60:]]
    lows = [k["low"] for k in klines[-60:]]
    if not highs or not lows:
        return {}
    resistance = round(max(highs), 2)
    support = round(min(lows), 2)
    current = klines[-1]["close"]
    # Find nearest support/resistance
    sorted_highs = sorted(set(highs), reverse=True)
    sorted_lows = sorted(set(lows))
    near_resistance = next((h for h in sorted_highs if h > current), resistance)
    near_support = next((l for l in sorted_lows if l < current), support)
    return {
        "support": round(near_support, 2),
        "resistance": round(near_resistance, 2),
        "stop_loss": round(near_support * 0.97, 2),
        "take_profit": round(near_resistance * 1.03, 2),
    }


def _get_chip_distribution(klines: List[Dict]) -> Dict[str, Any]:
    """Estimate chip (筹码) distribution from kline data."""
    if not klines:
        return {}
    closes = [k["close"] for k in klines]
    vols = [k["volume"] for k in klines]
    current = closes[-1]
    profit_count = sum(1 for c in closes if c <= current)
    profit_ratio = round(profit_count / len(closes) * 100, 1)
    avg_cost = round(sum(closes) / len(closes), 2)
    return {
        "profit_ratio": profit_ratio,
        "avg_cost": avg_cost,
        "chip_health": "良好" if profit_ratio > 50 else "一般" if profit_ratio > 30 else "较差",
    }


# ==== Tool Handlers ====

def _handle_get_realtime_quote(stock_code: str) -> dict:
    """Fetch realtime stock quote. efinance primary, Sina fallback."""
    codes = [stock_code]
    quotes = _fetch_realtime_efinance(codes)
    if stock_code in quotes:
        return quotes[stock_code]
    # Try Sina fallback
    sina = _fetch_realtime_sina(stock_code)
    if sina:
        return sina
    return {"error": f"No realtime data available for {stock_code}", "retriable": True}


def _handle_get_daily_history(stock_code: str, days: int = 60) -> dict:
    """Fetch historical daily kline data."""
    max_days = min(max(days, 5), 365)
    klines = _fetch_kline_efinance(stock_code, max_days)
    if not klines:
        return {"error": f"No history data for {stock_code}"}
    indicators = _calculate_indicators(klines)
    levels = _calculate_support_resistance(klines)
    chip = _get_chip_distribution(klines)
    return {
        "code": stock_code,
        "days": len(klines),
        "klines": klines[-30:],  # last 30 for context
        "indicators": indicators,
        "key_levels": levels,
        "chip": chip,
    }


def _handle_analyze_trend(stock_code: str) -> dict:
    """Comprehensive technical trend analysis."""
    klines = _fetch_kline_efinance(stock_code, 60)
    if not klines:
        return {"error": f"No data for trend analysis on {stock_code}"}
    ind = _calculate_indicators(klines)
    levels = _calculate_support_resistance(klines)

    # Determine trend
    ma_alignment = "neutral"
    if ind.get("ma5_above_ma10") is True and ind.get("ma10_above_ma20") is True:
        ma_alignment = "bullish"
    elif ind.get("ma5_above_ma10") is False and ind.get("ma10_above_ma20") is False:
        ma_alignment = "bearish"

    rsi = ind.get("rsi_14")
    rsi_status = "neutral"
    if rsi and rsi > 70:
        rsi_status = "overbought"
    elif rsi and rsi < 30:
        rsi_status = "oversold"

    vol_ratio = ind.get("volume_ratio_5d", 1)
    volume_status = "normal"
    if vol_ratio > 1.5:
        volume_status = "heavy"
    elif vol_ratio < 0.5:
        volume_status = "light"

    return {
        "code": stock_code,
        "trend_score": 60 if ma_alignment == "bullish" else 40 if ma_alignment == "bearish" else 50,
        "ma_alignment": ma_alignment,
        "rsi_status": rsi_status,
        "rsi": rsi,
        "volume_status": volume_status,
        "volume_ratio": vol_ratio,
        "ma5": ind.get("ma5"),
        "ma10": ind.get("ma10"),
        "ma20": ind.get("ma20"),
        "current_price": ind.get("current_price"),
        "bias_ma5": round(((ind.get("current_price", 0) or 0) - (ind.get("ma5", 0) or 0)) / (ind.get("ma5", 1) or 1) * 100, 2) if ind.get("ma5") else None,
        "support": levels.get("support"),
        "resistance": levels.get("resistance"),
        "stop_loss": levels.get("stop_loss"),
        "take_profit": levels.get("take_profit"),
        "macd_dif": ind.get("macd_dif"),
        "macd_bar": ind.get("macd_bar"),
    }


def _handle_calculate_ma(stock_code: str, period: int = 20) -> dict:
    """Calculate moving average for a stock."""
    klines = _fetch_kline_efinance(stock_code, period + 10)
    if not klines or len(klines) < period:
        return {"error": f"Insufficient data for {period}-day MA on {stock_code}"}
    closes = [k["close"] for k in klines[-period:]]
    ma_val = sum(closes) / period
    return {"code": stock_code, f"ma_{period}": round(ma_val, 2), "period": period}


def _handle_get_volume_analysis(stock_code: str) -> dict:
    """Analyze volume patterns."""
    klines = _fetch_kline_efinance(stock_code, 60)
    if not klines or len(klines) < 5:
        return {"error": f"Insufficient volume data for {stock_code}"}
    volumes = [k["volume"] for k in klines]
    current_vol = volumes[-1]
    avg_5 = sum(volumes[-5:]) / 5
    avg_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else avg_5
    changes = [k.get("change_pct", 0) for k in klines[-20:]]
    up_vol = sum(volumes[-i-1] for i, c in enumerate(changes) if c > 0)
    down_vol = sum(volumes[-i-1] for i, c in enumerate(changes) if c <= 0)
    return {
        "code": stock_code,
        "current_volume": int(current_vol),
        "avg_volume_5d": round(avg_5, 0),
        "avg_volume_20d": round(avg_20, 0),
        "volume_ratio_5d": round(current_vol / avg_5, 2) if avg_5 > 0 else 1,
        "volume_status": "放量" if current_vol > avg_5 * 1.5 else "缩量" if current_vol < avg_5 * 0.5 else "正常",
        "up_volume_ratio": round(up_vol / (up_vol + down_vol) * 100, 1) if (up_vol + down_vol) > 0 else 50,
    }


def _handle_analyze_pattern(stock_code: str) -> dict:
    """Identify candlestick patterns."""
    klines = _fetch_kline_efinance(stock_code, 30)
    if not klines or len(klines) < 3:
        return {"error": f"Insufficient data for pattern analysis on {stock_code}"}
    patterns = []
    # Check recent candles for common patterns
    last_3 = klines[-3:]
    for i, k in enumerate(last_3):
        body = abs(k["close"] - k["open"])
        upper = k["high"] - max(k["close"], k["open"])
        lower = min(k["close"], k["open"]) - k["low"]
        candle = k
        # Doji
        if body < (k["high"] - k["low"]) * 0.1:
            patterns.append({"date": k["date"], "pattern": "doji", "meaning": "市场犹豫"})
        # Hammer
        elif lower > body * 2 and upper < body * 0.3:
            patterns.append({"date": k["date"], "pattern": "hammer", "meaning": "可能见底反弹"})
        # Shooting star
        elif upper > body * 2 and lower < body * 0.3:
            patterns.append({"date": k["date"], "pattern": "shooting_star", "meaning": "可能见顶回落"})
        # Engulfing
        if i > 0:
            prev = last_3[i - 1]
            prev_body = abs(prev["close"] - prev["open"])
            if body > prev_body * 1.5:
                if k["close"] > k["open"] and prev["close"] < prev["open"]:
                    patterns.append({"date": k["date"], "pattern": "bullish_engulfing", "meaning": "看涨吞没"})
                elif k["close"] < k["open"] and prev["close"] > prev["open"]:
                    patterns.append({"date": k["date"], "pattern": "bearish_engulfing", "meaning": "看跌吞没"})

    return {"code": stock_code, "patterns": patterns if patterns else [{"pattern": "none", "meaning": "无明显形态"}]}


def _handle_get_market_indices() -> dict:
    """Get major market index overview."""
    indices = {}
    try:
        import efinance as ef
        df = ef.stock.get_latest_quote(["000001", "399001", "399006"])
        if df is not None and not df.empty:
            name_map = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指"}
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                name = name_map.get(code, str(row.get("名称", "")))
                indices[name] = {
                    "price": float(row.get("最新价", 0) or 0),
                    "change": float(row.get("涨跌幅", 0) or 0),
                    "volume": int(float(row.get("成交量", 0) or 0)),
                    "amount": float(row.get("成交额", 0) or 0),
                }
    except Exception as e:
        logger.warning(f"Market indices fetch failed: {e}")
    return {"indices": indices}


def _handle_get_stock_info(stock_code: str) -> dict:
    """Get basic stock info — name, sector, market cap."""
    quote = _handle_get_realtime_quote(stock_code)
    if "error" in quote:
        return {"code": stock_code, "name": "未知", "error": quote["error"]}
    return {
        "code": stock_code,
        "name": quote.get("name", ""),
        "market_cap": quote.get("market_cap", 0),
        "circulating_cap": quote.get("circulating_cap", 0),
        "pe": quote.get("pe", 0),
        "pb": quote.get("pb", 0),
        "turnover_rate": quote.get("turnover_rate", 0),
        "price": quote.get("price", 0),
    }


# ==== Tool Definitions ====

get_realtime_quote_tool = ToolDefinition(
    name="get_realtime_quote",
    description="获取实时行情：价格、涨跌幅、成交量、换手率、PE/PB。",
    parameters=[ToolParameter(name="stock_code", type="string", description="股票代码，如 '600519'")],
    handler=_handle_get_realtime_quote,
    category="data",
)

get_daily_history_tool = ToolDefinition(
    name="get_daily_history",
    description="获取历史日K线数据和技术指标（MA、RSI、MACD）。参数 days 控制回溯天数。",
    parameters=[
        ToolParameter(name="stock_code", type="string", description="股票代码", required=True),
        ToolParameter(name="days", type="integer", description="历史天数，默认60", required=False, default=60),
    ],
    handler=_handle_get_daily_history,
    category="data",
)

analyze_trend_tool = ToolDefinition(
    name="analyze_trend",
    description="综合分析趋势：均线排列、RSI状态、量能状态、支撑/阻力位。",
    parameters=[ToolParameter(name="stock_code", type="string", description="股票代码")],
    handler=_handle_analyze_trend,
    category="analysis",
)

calculate_ma_tool = ToolDefinition(
    name="calculate_ma",
    description="计算指定周期的移动平均线（MA）。",
    parameters=[
        ToolParameter(name="stock_code", type="string", description="股票代码"),
        ToolParameter(name="period", type="integer", description="周期天数", required=False, default=20),
    ],
    handler=_handle_calculate_ma,
    category="analysis",
)

get_volume_analysis_tool = ToolDefinition(
    name="get_volume_analysis",
    description="量能分析：当前量、均量、量比、涨跌量能比。",
    parameters=[ToolParameter(name="stock_code", type="string", description="股票代码")],
    handler=_handle_get_volume_analysis,
    category="analysis",
)

analyze_pattern_tool = ToolDefinition(
    name="analyze_pattern",
    description="K线形态识别：锤子线、十字星、吞没形态等。",
    parameters=[ToolParameter(name="stock_code", type="string", description="股票代码")],
    handler=_handle_analyze_pattern,
    category="analysis",
)

get_market_indices_tool = ToolDefinition(
    name="get_market_indices",
    description="获取市场主要指数行情：上证、深证、创业板。",
    parameters=[],
    handler=_handle_get_market_indices,
    category="data",
)

get_stock_info_tool = ToolDefinition(
    name="get_stock_info",
    description="获取股票基本信息：名称、市值、PE、PB、换手率。",
    parameters=[ToolParameter(name="stock_code", type="string", description="股票代码")],
    handler=_handle_get_stock_info,
    category="data",
)

ALL_FACECAT_TOOLS = [
    get_realtime_quote_tool,
    get_daily_history_tool,
    analyze_trend_tool,
    calculate_ma_tool,
    get_volume_analysis_tool,
    analyze_pattern_tool,
    get_market_indices_tool,
    get_stock_info_tool,
]


def register_all_facecat_tools(registry) -> None:
    """Register all FaceCat tools into a ToolRegistry."""
    for t in ALL_FACECAT_TOOLS:
        registry.register(t)
