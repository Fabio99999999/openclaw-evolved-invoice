#!/usr/bin/env python3
"""
入场信号系统 — 基于《高胜算操盘》马塞尔·林克交易方法

信号规则 (林克体系):
  1. 大级别趋势向上 (多时间框架确认) ⭐⭐⭐
  2. 价格回调到EMA20/EMA60支撑 ⭐⭐⭐
  3. RSI回调到30-40区间 (超卖区)
  4. 成交量萎缩后重新放大 (洗盘结束)
  5. 支撑位出现价格验证 (K线反转/拒绝下跌)
  6. "该跌不跌" — 回调到支撑位但不跌破
  7. 摆动指标超卖背离 (价格新低但RSI不新低)

评分: 满足条件越多 → 信号越强 → 信心越高
"""

from typing import Dict, List, Optional, Tuple


# ─── 信号强度 ───
SIGNAL_STRONG = "strong"      # ⭐⭐⭐ 高胜算入场
SIGNAL_MEDIUM = "medium"      # ⭐⭐ 中等胜算
SIGNAL_WEAK = "weak"          # ⭐ 低胜算
SIGNAL_NONE = "none"          # 不入场

# ─── 林克入场信号检查 ───

def check_trend_alignment(trend: Dict) -> Tuple[bool, str, int]:
    """规则1: 大级别趋势确认
    
    林克核心: "The trend is your friend"
    只在主要趋势方向交易。日线趋势至少向上或向下。
    """
    score = 0
    details = []

    tf_details = trend.get("details", {})
    overall = trend.get("trend", "sideways")

    # 月线方向最重要(40%权重)
    monthly = tf_details.get("monthly", {})
    weekly = tf_details.get("weekly", {})
    daily = tf_details.get("daily", {})

    if overall == "up":
        score += 30
        details.append("主趋势向上")
    elif overall == "down":
        score -= 30  # 做空信号 (但A股基本只做多)
        details.append("主趋势向下(不宜做多)")
    else:
        details.append("震荡市(观望)")

    # 多周期共振加分
    aligned = sum(1 for tf in [monthly, weekly, daily] if tf.get("trend") == overall)
    if aligned >= 2 and overall == "up":
        score += 15
        details.append(f"多周期共振({aligned}/3)")
    elif aligned == 3 and overall == "up":
        score += 10
        details.append("全周期共振✅")

    # 周线EMA5 > EMA20确认趋势健康
    if weekly.get("ema5") and weekly.get("ema20"):
        if weekly["ema5"] > weekly["ema20"]:
            score += 5
            details.append("周线多头排列")

    ready = score >= 25
    return ready, "; ".join(details), score


def check_pullback_to_support(indicators: Dict, daily_data: List[Dict]) -> Tuple[bool, str, int]:
    """规则2+6: 回调到支撑 + 价格验证 (林克核心入场技术)
    
    林克: "Wait for retracements to key support or resistance levels 
           before entering trades in the direction of the trend."
    上涨趋势中 → 等回调到EMA20/EMA60/趋势线
    """
    score = 0
    details = []
    daily_ind = indicators.get("daily", {})

    if not daily_data or len(daily_data) < 10:
        return False, "K线数据不足", 0

    last = daily_data[-1]
    last_close = last["close"]
    last_low = last["low"]
    last_high = last["high"]

    ema20 = daily_ind.get("ema20")
    ema60 = daily_ind.get("ema60")

    if ema20 and ema20 > 0:
        # 价格在EMA20附近 (±2%)
        pct_from_ema20 = (last_close - ema20) / ema20 * 100
        if abs(pct_from_ema20) < 1.0:
            score += 25
            details.append(f"精准触及EMA20(+{pct_from_ema20:.1f}%)")
        elif -3.0 < pct_from_ema20 < 0:
            score += 20
            details.append(f"EMA20下方(-{abs(pct_from_ema20):.1f}%)支撑区")
        elif 0 < pct_from_ema20 < 2.0:
            score += 15
            details.append(f"EMA20上方(+{pct_from_ema20:.1f}%)近支撑")
        elif -5.0 < pct_from_ema20 < -3.0:
            score += 10
            details.append(f"跌破EMA20(-{abs(pct_from_ema20):.1f}%)关注EMA60")

    if ema60 and ema60 > 0:
        pct_from_ema60 = (last_close - ema60) / ema60 * 100
        if abs(pct_from_ema60) < 1.0:
            score += 20
            details.append(f"触及EMA60支撑(+{pct_from_ema60:.1f}%)")
        elif -2.0 < pct_from_ema60 < 0:
            score += 15
            details.append(f"EMA60下方支撑区")

    # 规则6: "该跌不跌" — 价格触及支撑后反弹
    if len(daily_data) >= 3:
        prev_2 = daily_data[-3]["low"]
        prev_1 = daily_data[-2]["low"]
        curr = daily_data[-1]["low"]
        # 连续三根K线低点不创新低
        if curr >= prev_1 >= prev_2:
            score += 15
            details.append("低点渐高(底部抬高)")
        # 下影线 (拒绝下跌)
        body = abs(last_close - last["open"])
        lower_shadow = last["open"] - last_low if last_close > last["open"] else last_close - last_low
        if body > 0 and lower_shadow > body * 1.5 and last_close >= last["open"]:
            score += 15
            details.append("长下影线(拒绝下跌)")

    valid = score >= 20
    return valid, "; ".join(details), score


def check_rsi_oversold(indicators: Dict) -> Tuple[bool, str, int]:
    """规则3: RSI回调信号
    
    林克: "Look for divergences between price action and oscillators"
    不在超买区追高，在回调后的支撑位入场。
    """
    score = 0
    details = []
    daily_ind = indicators.get("daily", {})
    weekly_ind = indicators.get("weekly", {})

    daily_rsi = daily_ind.get("rsi")
    weekly_rsi = weekly_ind.get("rsi")

    if daily_rsi is not None:
        if 30 <= daily_rsi <= 45:
            score += 20
            details.append(f"日RSI={daily_rsi:.0f}(超卖区)")
        elif 45 < daily_rsi <= 55:
            score += 10
            details.append(f"日RSI={daily_rsi:.0f}(中性偏低)")
        elif daily_rsi > 75:
            score -= 10
            details.append(f"日RSI={daily_rsi:.0f}(超买⚠️)")
        else:
            details.append(f"日RSI={daily_rsi:.0f}")

    if weekly_rsi is not None:
        if weekly_rsi > 80:
            score -= 5
            details.append(f"周RSI={weekly_rsi:.0f}(极强)")
        elif 40 <= weekly_rsi <= 60:
            score += 5
            details.append(f"周RSI={weekly_rsi:.0f}(健康)")

    valid = score >= 15
    return valid, "; ".join(details), score


def check_volume_confirmation(daily_data: List[Dict]) -> Tuple[bool, str, int]:
    """规则4+7: 成交量验证 + 量价配合
    
    林克: "Volume and open interest can confirm the trend."
    回调缩量 → 抛压减轻; 企稳放量 → 新资金入场
    """
    score = 0
    details = []

    if not daily_data or len(daily_data) < 10:
        return False, "数据不足", 0

    # 最近5根成交量对比前5根
    recent_vol = [d["volume"] for d in daily_data[-5:]]
    prev_vol = [d["volume"] for d in daily_data[-10:-5]]
    avg_recent = sum(recent_vol) / len(recent_vol)
    avg_prev = sum(prev_vol) / len(prev_vol)

    vol_ratio = avg_recent / avg_prev if avg_prev > 0 else 1

    if 0.6 <= vol_ratio <= 0.9:
        # 缩量回调
        score += 15
        details.append(f"缩量回调({vol_ratio:.2f}x)")
    elif 0.9 < vol_ratio <= 1.1:
        score += 5
        details.append("量能持平")
    elif vol_ratio < 0.6:
        score += 10
        details.append(f"极度缩量({vol_ratio:.2f}x)(惜售)")
    elif vol_ratio > 1.5:
        # 放量下跌不好，放量上涨好
        if daily_data[-1]["close"] > daily_data[-2]["close"]:
            score += 10
            details.append(f"放量上涨({vol_ratio:.2f}x)")
        else:
            details.append(f"放量下跌({vol_ratio:.2f}x)⚠️")

    # 规则7: 成交量背离 — 价格新低但成交量不放大
    if len(daily_data) >= 10:
        recent_lows = [d["low"] for d in daily_data[-10:]]
        recent_vols = [d["volume"] for d in daily_data[-10:]]
        if recent_lows[-1] == min(recent_lows):  # 今日是10日最低
            if recent_vols[-1] < sum(recent_vols[:-1]) / 9:  # 但量不大
                score += 10
                details.append("价创新低但量未放(背离)")

    valid = score >= 10
    return valid, "; ".join(details), score


def check_entry_setup(trend: Dict, indicators: Dict, daily_data: List[Dict],
                       code: str = "", price: float = 0) -> Dict:
    """完整入场信号评分 (林克体系综合)
    
    Returns:
        {
            "signal": "strong"|"medium"|"weak"|"none",
            "score": 0-100,
            "rules": {
                "trend_alignment": {"pass": bool, "detail": str, "score": int},
                "pullback_support": {...},
                "rsi_signal": {...},
                "volume_confirm": {...},
            },
            "summary": "入场建议文字",
        }
    """
    rules = {}

    # 规则1: 趋势确认
    trend_ok, trend_detail, trend_score = check_trend_alignment(trend)
    rules["trend_alignment"] = {"pass": trend_ok, "detail": trend_detail, "score": trend_score}

    # 规则2+6: 回调到支撑
    pullback_ok, pull_detail, pull_score = check_pullback_to_support(indicators, daily_data)
    rules["pullback_support"] = {"pass": pullback_ok, "detail": pull_detail, "score": pull_score}

    # 规则3: RSI信号
    rsi_ok, rsi_detail, rsi_score = check_rsi_oversold(indicators)
    rules["rsi_signal"] = {"pass": rsi_ok, "detail": rsi_detail, "score": rsi_score}

    # 规则4+7: 成交量验证
    vol_ok, vol_detail, vol_score = check_volume_confirmation(daily_data)
    rules["volume_confirm"] = {"pass": vol_ok, "detail": vol_detail, "score": vol_score}

    # 总分 (加权)
    weights = {
        "trend_alignment": 0.35,
        "pullback_support": 0.30,
        "rsi_signal": 0.20,
        "volume_confirm": 0.15,
    }
    total = sum(rules[k]["score"] * weights[k] for k in rules)
    total = max(0, min(100, int(total)))

    # 判定
    passes = sum(1 for k in rules if rules[k]["pass"])
    if total >= 60 and passes >= 3:
        signal = SIGNAL_STRONG
        summary = f"⭐⭐⭐ 高胜算入场机会 [ {total}/100 ]"
    elif total >= 40 and passes >= 2:
        signal = SIGNAL_MEDIUM
        summary = f"⭐⭐ 中等胜算入场 [ {total}/100 ]"
    elif total >= 20:
        signal = SIGNAL_WEAK
        summary = f"⭐ 低胜算 [ {total}/100 ] 等待更好时机"
    else:
        signal = SIGNAL_NONE
        summary = f"❌ 不建议入场 [ {total}/100 ] 条件不满足"

    # 入场关键位
    entry_zones = {}
    daily_ind = indicators.get("daily", {})
    if daily_ind.get("ema20"):
        entry_zones["primary"] = round(daily_ind["ema20"], 2)
    if daily_ind.get("ema60"):
        entry_zones["secondary"] = round(daily_ind["ema60"], 2)
    entry_zones["current_price"] = round(price, 2) if price else 0

    return {
        "signal": signal,
        "score": total,
        "rules": rules,
        "entry_zones": entry_zones,
        "pass_count": passes,
        "summary": summary,
    }
