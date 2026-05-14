#!/usr/bin/env python3
"""
止损优化器 — 基于《高胜算操盘》马塞尔·林克 + ATR 动态止损

核心原则:
  1. 止损放技术位下方 (支撑下方), 不是随意数字
  2. ATR 决定合理止损宽度 
  3. 每笔交易风险 = 总资金 1-2%
  4. 盈利后用跟踪止损保护
  5. 时间止损 — 3天不涨就出

林克原话:
  "Place stops at logical technical levels, such as below support in an uptrend 
   or above resistance in a downtrend. Avoid placing stops at obvious round numbers."
  "Position sizing based on market volatility, using the Average True Range (ATR)."
"""

from typing import Dict, List, Optional, Tuple


def calc_technical_stop(indicators: Dict, daily_data: List[Dict]) -> Dict:
    """计算技术位止损 (林克核心方法)
    
    止损层:
      - Layer 1 (核心): 关键支撑下方 0.5-1%
      - Layer 2 (保守): EMA20 下方 0.5%
      - Layer 3 (极值): 前波低点
      - Layer 4 (ATR): 入场价 - 1.5×ATR
    
    Returns:
        {
            "core": 18.50,      # 核心止损价
            "conservative": 18.80,  # 保守止损
            "extreme": 18.00,   # 极端止损
            "atr_stop": 18.70,  # ATR 止损
            "atr_width": 0.80,  # ATR 数值
            "risk_pct": 3.2,    # 核心止损距离百分比
            "method": "支撑下方",
        }
    """
    result = {}
    daily_ind = indicators.get("daily", {})
    last_close = daily_ind.get("last_close", 0)
    atr = daily_ind.get("atr")
    ema20 = daily_ind.get("ema20")
    ema60 = daily_ind.get("ema60")

    if not daily_data or len(daily_data) < 5:
        return {"error": "数据不足"}

    # 寻找最近5根K线的最低点
    recent_lows = [d["low"] for d in daily_data[-5:]]
    recent_low = min(recent_lows)
    recent_10_low = min(d["low"] for d in daily_data[-10:]) if len(daily_data) >= 10 else recent_low
    # 前波低点 (20日内)
    wave_low = min(d["low"] for d in daily_data[-20:]) if len(daily_data) >= 20 else recent_low

    # 核心止损: 最近5日最低点下移 0.5%
    core_stop = round(recent_low * 0.995, 2)
    result["core"] = core_stop
    result["core_desc"] = f"近5日最低{recent_low:.2f}↓0.5%"

    # 保守止损: EMA20下方 0.5%
    if ema20 and ema20 > 0:
        conservative = round(ema20 * 0.995, 2)
        result["conservative"] = min(conservative, core_stop)  # 不高于核心止损
        result["conservative_desc"] = f"EMA20({ema20:.2f})↓0.5%"
    else:
        result["conservative"] = core_stop
        result["conservative_desc"] = "无EMA20, 同核心止损"

    # 极值止损: 20日最低
    result["extreme"] = round(wave_low * 0.99, 2)
    result["extreme_desc"] = f"20日最低({wave_low:.2f})↓1%"

    # ATR 止损
    if atr and atr > 0:
        atr_stop = round(last_close - 1.5 * atr, 2)
        atr_width = round(atr, 2)
    else:
        atr_stop = core_stop
        atr_width = round((last_close - core_stop) / 0.015, 2)  # 估算

    result["atr_stop"] = min(atr_stop, core_stop)  # ATR止损不宽于核心止损
    result["atr_width"] = atr_width

    # 止损占总资金百分比
    risk_pct = (last_close - core_stop) / last_close * 100
    result["risk_pct"] = round(risk_pct, 1)

    # 选择最佳止损方法
    methods = []
    if risk_pct <= 2: methods.append("窄止损")
    if 2 < risk_pct <= 5: methods.append("正常止损")
    if risk_pct > 5: methods.append("宽止损(波动大)")

    result["method"] = " + ".join(methods)
    result["last_price"] = last_close

    return result


def calc_position_size(portfolio_value: float, stop_loss: Dict,
                        entry_price: Optional[float] = None) -> Dict:
    """计算头寸规模 (林克资金管理)
    
    林克: "Risk no more than 1-2% of trading capital on any single trade."
    
    Args:
        portfolio_value: 总资金
        stop_loss: stop_loss output dict
        entry_price: 入场价 (None = 当前价)
    
    Returns:
        {
            "risk_1pct": 数量,        # 1%风险对应的股数
            "risk_2pct": 数量,        # 2%风险对应的股数
            "recommended": 数量,      # 建议股数(1.5%)
            "risk_amount": 金额,      # 单笔风险金额
            "position_pct": 占比,     # 仓位占总资产百分比
            "stop_price": 止损价,
            "entry_price": 入场价,
        }
    """
    if not stop_loss or "error" in stop_loss:
        return {"error": "止损数据无效"}

    price = entry_price or stop_loss.get("last_price", 0)
    core_stop = stop_loss.get("core", 0)
    if price <= 0 or core_stop <= 0:
        return {"error": "价格数据无效"}

    risk_per_share = price - core_stop  # 每股最大亏损
    if risk_per_share <= 0:
        return {"error": f"止损价{core_stop}高于现价{price}"}

    risk_1pct = int(portfolio_value * 0.01 / risk_per_share)
    risk_2pct = int(portfolio_value * 0.02 / risk_per_share)

    # 建议: 1.5% 风险, 取整到100股
    recommended = int(portfolio_value * 0.015 / risk_per_share / 100) * 100
    if recommended < 100:
        recommended = 100

    # 单票仓位上限 (林克: 专注少数市场, 单票≤20%)
    max_by_cost = int(portfolio_value * 0.20 / price / 100) * 100
    if max_by_cost > 0 and recommended > max_by_cost:
        recommended = max_by_cost

    risk_amount = round(recommended * risk_per_share, 2)
    position_pct = round(recommended * price / portfolio_value * 100, 1)

    return {
        "risk_1pct": risk_1pct,
        "risk_2pct": risk_2pct,
        "recommended": recommended,
        "risk_amount": risk_amount,
        "position_pct": position_pct,
        "stop_price": core_stop,
        "entry_price": round(price, 2),
        "risk_pct_text": f"¥{risk_per_share:.2f}/股 ({stop_loss.get('risk_pct', 0):.1f}%)",
    }


def calc_trailing_stop(daily_data: List[Dict], current_price: float) -> Dict:
    """跟踪止损 (让利润奔跑)
    
    林克: "Use trailing stops to lock in profits."
    
    方法:
      - 基于20日最高点下移 ATR
      - 盈利 >10% 后启动跟踪
    """
    if not daily_data or len(daily_data) < 10:
        return {"trailing_active": False}

    highest_20 = max(d["high"] for d in daily_data[-20:]) if len(daily_data) >= 20 else max(
        d["high"] for d in daily_data)

    # 假设入场价是20日内的某一点
    # 用近5日均线估算入场价
    recent_closes = [d["close"] for d in daily_data[-5:]]
    est_entry = sum(recent_closes) / len(recent_closes)

    profit_pct = (current_price - est_entry) / est_entry * 100

    # 从日线计算ATR
    from facecat_data import get_atr
    atr = get_atr(daily_data)

    trailing_active = profit_pct >= 8  # 盈利8%后启动跟踪

    if trailing_active and atr and atr > 0:
        # 跟踪止损 = 20日最高点 - 2×ATR
        trail_stop = round(highest_20 - 2 * atr, 2)
        locked_profit = round((current_price - trail_stop) / est_entry * 100, 1)
        return {
            "trailing_active": True,
            "trail_stop": trail_stop,
            "highest_since_entry": round(highest_20, 2),
            "estimated_entry": round(est_entry, 2),
            "profit_pct": round(profit_pct, 1),
            "locked_pct": max(0, locked_profit),
            "atr": round(atr, 2) if atr else 0,
        }
    else:
        return {
            "trailing_active": False,
            "estimated_entry": round(est_entry, 2),
            "profit_pct": round(profit_pct, 1),
            "status": "盈利未达8%, 暂不启动跟踪",
        }


def calc_time_stop(daily_data: List[Dict], entry_date_str: str = "") -> Dict:
    """时间止损 — 林克: "Time-based exits for trades not working as expected"
    
    入场后3个交易日不涨 → 出
    入场后5个交易日涨幅<3% → 减仓
    """
    if not daily_data or len(daily_data) < 2:
        return {"time_stop_signal": False}

    if entry_date_str:
        try:
            from datetime import datetime
            entry_dt = datetime.strptime(entry_date_str, "%Y-%m-%d")
            last_dt = datetime.strptime(daily_data[-1]["date"], "%Y-%m-%d")
            days_held = (last_dt - entry_dt).days
        except ValueError:
            days_held = 0
    else:
        days_held = 0

    entry_price = None
    if entry_date_str and days_held >= 0:
        entry_price = _find_price_on_date(daily_data, entry_date_str)

    if days_held >= 3 and entry_price and entry_price > 0:
        current = daily_data[-1]["close"]
        return_pct = (current - entry_price) / entry_price * 100
        if return_pct < 0.5:
            return {
                "time_stop_signal": True,
                "reason": f"入场{days_held}天仅涨{return_pct:+.1f}%",
                "days_held": days_held,
                "return_pct": round(return_pct, 1),
                "action": "出场 (时间止损)",
            }
        elif return_pct < 3:
            return {
                "time_stop_signal": True,
                "reason": f"入场{days_held}天涨{return_pct:+.1f}%",
                "days_held": days_held,
                "return_pct": round(return_pct, 1),
                "action": "减仓 (表现不及预期)",
            }

    return {"time_stop_signal": False, "days_held": days_held}


def _find_price_on_date(daily_data: List[Dict], date_str: str) -> Optional[float]:
    """在K线数据中找到指定日期的收盘价"""
    for d in daily_data:
        if d["date"] == date_str:
            return d["close"]
    return None
