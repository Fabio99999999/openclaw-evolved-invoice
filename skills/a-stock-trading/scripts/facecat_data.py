#!/usr/bin/env python3
"""
K线数据获取 — 多数据源统一接口

数据源优先级:
  1. efinance get_quote_history() — 历史K线 (意大利可用 ✅)
  2. FaceCat API — 备选 (非交易时间可能为空)
  3. Sina API — 实时行情 (意大利可用 ✅)

技术指标:
  - EMA, SMA, ATR, RSI, MACD
  - 多时间框架: 日线/周线/月线
"""

import sys
import urllib.request
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

# ─── 数据源 1: efinance (历史K线) ───

def fetch_kline_efinance(code: str, days: int = 120) -> Optional[List[Dict]]:
    """efinance 历史K线 (单股查询, 日期 YYYYMMDD 格式)"""
    try:
        import efinance as ef
        end = datetime.now()
        start = end - timedelta(days=days * 2)
        beg = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")
        df = ef.stock.get_quote_history(code, beg=beg, end=end_str)
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
        # 按日期排序 (旧→新)
        records.sort(key=lambda r: r["date"])
        return records[-days:]
    except Exception as e:
        print(f"[efinance] 历史K线失败 {code}: {e}", file=sys.stderr)
    return None


# ─── 数据源 2: FaceCat (备选) ───

FACECAT_URL = "http://www.jjmfc.com:9968/quote"

def _fc_request(params: str) -> Optional[str]:
    try:
        req = urllib.request.Request(f"{FACECAT_URL}/{params}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return raw.strip() or None
    except Exception as e:
        return None

def fetch_kline_facecat(code: str, days: int = 60) -> Optional[List[Dict]]:
    """FaceCat 历史K线"""
    raw = _fc_request(f"getkline?code={code}&number={days * 2}")
    if not raw:
        return None
    import csv, io
    records = []
    try:
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            d = row.get("date", "").strip()
            if not d:
                continue
            try:
                records.append({
                    "date": d,
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": int(float(row.get("volume", 0) or 0)),
                    "amount": float(row.get("amount", 0) or 0),
                })
            except (ValueError, KeyError):
                continue
        if records:
            records.sort(key=lambda r: r["date"])
            return records[-days:]
    except Exception:
        pass
    return None


# ─── 统一K线获取入口 ───

def fetch_kline(code: str, days: int = 120) -> Optional[List[Dict]]:
    """统一获取日K线: efinance → FaceCat"""
    records = fetch_kline_efinance(code, days)
    if records:
        return records
    records = fetch_kline_facecat(code, days)
    if records:
        return records
    return None


# ─── 数据源 3: Sina (实时行情, 含交易日期) ───

def fetch_realtime_sina(codes: List[str]) -> Dict[str, Dict]:
    """Sina 实时行情 (意大利可用 ✅)"""
    result = {}
    try:
        sina_codes = []
        for c in codes:
            c = c.zfill(6)
            prefix = "sh" if c.startswith(("5", "6", "9")) else "sz"
            sina_codes.append(f"{prefix}{c}")
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk")

        for line in raw.strip().split(";"):
            if not line or "=" not in line:
                continue
            parts = line.split("=")[1].strip('"').split(",")
            if len(parts) < 30:
                continue
            code_key = line.split("=")[0].split("_")[-1]
            code = code_key[2:].zfill(6)
            name = parts[0]
            price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[2]) if parts[2] else price
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            high = float(parts[4]) if parts[4] else 0
            low = float(parts[5]) if parts[5] else 0
            open_p = float(parts[1]) if parts[1] else 0
            volume = int(float(parts[8])) if parts[8] else 0
            amount = float(parts[9]) if parts[9] else 0
            bid = float(parts[6]) if parts[6] else 0
            ask = float(parts[7]) if parts[7] else 0
            # 交易日期: parts[30] 或 parts[31]
            trade_date = ""
            if len(parts) >= 32:
                trade_date = parts[30].strip()
                if not trade_date or "-" not in trade_date:
                    trade_date = parts[31].strip() if len(parts) >= 32 else ""

            result[code] = {
                "code": code,
                "name": name,
                "price": price,
                "prev_close": prev_close,
                "change_pct": round(change_pct, 2),
                "open": open_p,
                "high": high,
                "low": low,
                "volume": volume,
                "amount": amount,
                "bid": bid,
                "ask": ask,
                "trade_date": trade_date,
                "source": "sina",
            }
    except Exception as e:
        print(f"[Sina] 实时行情失败: {e}", file=sys.stderr)
    return result


# ─── 技术指标计算 ───

def get_ema(values: List[float], period: int = 20) -> List[Optional[float]]:
    """EMA 指数移动平均 (返回长度=len(values), 不足period的位置为None)"""
    if not values:
        return []
    k = 2 / (period + 1)
    result: List[Optional[float]] = []
    prev = None
    for v in values:
        if prev is None:
            prev = v
            result.append(None)  # 第一根没有EMA
        else:
            prev = v * k + prev * (1 - k)
            result.append(prev)
    # 前 period-1 根不输出
    for i in range(min(period - 1, len(result))):
        result[i] = None
    return result


def get_sma(values: List[float], period: int = 20) -> List[Optional[float]]:
    """SMA 简单移动平均"""
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(values[i - period + 1:i + 1]) / period)
    return result


def get_atr(klines: List[Dict], period: int = 14) -> Optional[float]:
    """当前 ATR (Average True Range)"""
    if not klines or len(klines) < period + 1:
        return None
    trs = []
    for i in range(1, len(klines)):
        h, l, pc = klines[i]["high"], klines[i]["low"], klines[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def get_rsi(klines: List[Dict], period: int = 14) -> Optional[float]:
    """当前 RSI (Relative Strength Index)"""
    if not klines or len(klines) < period + 1:
        return None
    closes = [k["close"] for k in klines]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    if len(gains) < period:
        return None
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100.0
    return 100 - (100 / (1 + avg_g / avg_l))


def get_macd(closes: List[float]) -> Dict:
    """MACD 指标"""
    ema12 = get_ema(closes, 12)
    ema26 = get_ema(closes, 26)
    # 过滤None
    v12 = [v for v in ema12 if v is not None]
    v26 = [v for v in ema26 if v is not None]
    if not v12 or not v26:
        return {"dif": 0, "dea": 0, "macd": 0, "histogram": 0}
    dif = v12[-1] - v26[-1]
    # DIF 的 9EMA = DEA
    dif_list = [ema12[i] - ema26[i] for i in range(min(len(ema12), len(ema26))) if ema12[i] is not None and ema26[i] is not None]
    if len(dif_list) < 9:
        return {"dif": dif, "dea": dif, "macd": 0, "histogram": 0}
    dea_list = get_ema(dif_list, 9)
    dea = [d for d in dea_list if d is not None]
    dea_v = dea[-1] if dea else dif
    macd_v = 2 * (dif - dea_v)
    return {"dif": round(dif, 4), "dea": round(dea_v, 4), "macd": round(macd_v, 4), "histogram": round(macd_v, 4)}


# ─── 多时间框架 ───

def get_multiple_timeframes(code: str) -> Dict:
    """获取多时间框架数据
    
    Returns:
        {
            "code": "603538",
            "daily": [...60根...],
            "weekly": [...24根...],
            "monthly": [...12根...],
            "realtime": {...} 或 None,
            "indicators": {
                "daily": { "ema5": x, "ema20": x, "ema60": x, "rsi": x, "atr": x, "macd": {...} },
                "weekly": { "ema5": x, "ema20": x, "rsi": x },
                "monthly": { "ema5": x, "ema20": x, "rsi": x },
            }
        }
    """
    daily = fetch_kline(code, days=120)
    if not daily:
        return {"code": code, "error": "无法获取K线数据"}

    weekly = _aggregate_weekly(daily)
    monthly = _aggregate_monthly(daily)

    # 实时行情
    realtime = fetch_realtime_sina([code]).get(code)

    # 指标计算
    indicators = {}
    for name, data in [("daily", daily[-60:]), ("weekly", weekly[-24:] if weekly else []), ("monthly", monthly[-12:] if monthly else [])]:
        if not data:
            continue
        closes = [k["close"] for k in data]
        ema5 = get_ema(closes, 5)
        ema20 = get_ema(closes, 20)
        ema60 = get_ema(closes, 60)
        rsi = get_rsi(data)
        atr = get_atr(data)
        macd = get_macd(closes)
        ind = {
            "ema5": ema5[-1] if ema5 and ema5[-1] is not None else closes[-1],
            "ema20": ema20[-1] if ema20 and ema20[-1] is not None else None,
            "ema60": ema60[-1] if ema60 and ema60[-1] is not None else None,
            "rsi": round(rsi, 1) if rsi else None,
            "atr": round(atr, 2) if atr else None,
            "macd": macd,
            "last_close": closes[-1] if closes else 0,
            "highest_20": max(closes[-20:]) if len(closes) >= 20 else max(closes) if closes else 0,
            "lowest_20": min(closes[-20:]) if len(closes) >= 20 else min(closes) if closes else 0,
        }
        indicators[name] = ind

    return {
        "code": code,
        "daily": daily[-60:],
        "weekly": weekly[-24:] if weekly else [],
        "monthly": monthly[-12:] if monthly else [],
        "realtime": realtime,
        "indicators": indicators,
    }


def _aggregate_weekly(daily: List[Dict]) -> List[Dict]:
    from collections import OrderedDict
    weeks = OrderedDict()
    for d in daily:
        try:
            dt = datetime.strptime(d["date"], "%Y-%m-%d")
        except ValueError:
            continue
        wk = dt.strftime("%Y-W%W")
        if wk not in weeks:
            weeks[wk] = dict(d)
        else:
            w = weeks[wk]
            w["high"] = max(w["high"], d["high"])
            w["low"] = min(w["low"], d["low"])
            w["close"] = d["close"]
            w["volume"] += d["volume"]
            w["amount"] += d["amount"]
    return list(weeks.values())


def _aggregate_monthly(daily: List[Dict]) -> List[Dict]:
    from collections import OrderedDict
    months = OrderedDict()
    for d in daily:
        try:
            dt = datetime.strptime(d["date"], "%Y-%m-%d")
        except ValueError:
            continue
        mk = dt.strftime("%Y-%m")
        if mk not in months:
            months[mk] = dict(d)
        else:
            m = months[mk]
            m["high"] = max(m["high"], d["high"])
            m["low"] = min(m["low"], d["low"])
            m["close"] = d["close"]
            m["volume"] += d["volume"]
            m["amount"] += d["amount"]
    return list(months.values())


# ─── 趋势方向判断 ───

TREND_UP = "up"
TREND_DOWN = "down"
TREND_SIDEWAYS = "sideways"

def judge_trend(indicators: Dict) -> Dict:
    """多时间框架趋势判断
    
    Returns:
        {
            "trend": "up"|"down"|"sideways",
            "score": 0-100,
            "details": {
                "daily": {"trend": "...", "strength": ...},
                "weekly": {"trend": "...", "strength": ...},
                "monthly": {"trend": "...", "strength": ...},
            },
            "signals": [...]
        }
    """
    if not indicators:
        return {"trend": TREND_SIDEWAYS, "score": 50, "details": {}, "signals": ["数据不足"]}

    details = {}
    signals = []
    total_score = 0
    weights = {"monthly": 0.4, "weekly": 0.35, "daily": 0.25}
    count = 0

    for tf in ["monthly", "weekly", "daily"]:
        ind = indicators.get(tf)
        if not ind:
            continue
        count += 1

        last_close = ind["last_close"]
        ema5 = ind.get("ema5")
        ema20 = ind.get("ema20")
        rsi = ind.get("rsi")

        # 均线排列判断
        score = 50
        trend_msgs = []

        if ema5 is not None and ema20 is not None:
            if last_close > ema5 > ema20:
                # 多头排列: 价 > EMA5 > EMA20
                score += 20
                trend_msgs.append("多头排列")
            elif last_close < ema5 < ema20:
                # 空头排列: 价 < EMA5 < EMA20
                score -= 20
                trend_msgs.append("空头排列")
            elif last_close > ema5 and last_close > ema20:
                score += 10
                trend_msgs.append("均线上方")
            elif last_close < ema5 and last_close < ema20:
                score -= 10
                trend_msgs.append("均线下方")
            else:
                trend_msgs.append("均线缠绕")

        # RSI 确认
        if rsi is not None:
            if rsi > 60:
                score += 5
                trend_msgs.append(f"RSI={rsi:.0f}偏强")
            elif rsi < 40:
                score -= 5
                trend_msgs.append(f"RSI={rsi:.0f}偏弱")
            else:
                trend_msgs.append(f"RSI={rsi:.0f}中性")

        # 20日高低位置
        h20, l20 = ind.get("highest_20", last_close), ind.get("lowest_20", last_close)
        if h20 != l20:
            pos = (last_close - l20) / (h20 - l20) * 100
            if pos > 80:
                score += 5
                trend_msgs.append(f"近20日高位({pos:.0f}%)")
            elif pos < 20:
                score -= 5
                trend_msgs.append(f"近20日低位({pos:.0f}%)")

        score = max(0, min(100, score))
        _trend = TREND_UP if score > 60 else (TREND_DOWN if score < 40 else TREND_SIDEWAYS)
        details[tf] = {
            "trend": _trend,
            "score": score,
            "close": last_close,
            "ema5": ema5,
            "ema20": ema20,
            "rsi": rsi,
            "summary": ", ".join(trend_msgs),
        }
        total_score += score * weights.get(tf, 0.3)

    if count == 0:
        return {"trend": TREND_SIDEWAYS, "score": 50, "details": {}, "signals": ["数据不足"]}

    final_score = int(total_score / sum(weights[tf] for tf in weights if tf in details))
    final_trend = TREND_UP if final_score > 60 else (TREND_DOWN if final_score < 40 else TREND_SIDEWAYS)

    # 综合信号
    if final_trend == TREND_UP:
        signals.append("✅ 多周期共振看多")
    elif final_trend == TREND_DOWN:
        signals.append("⚠️ 多周期共振看空")
    else:
        signals.append("➡️ 方向不明确，建议观望")

    if details.get("daily", {}).get("trend") == TREND_UP and details.get("weekly", {}).get("trend") == TREND_SIDEWAYS:
        signals.append("💡 日线走强但周线未确认，需等待")
    if details.get("monthly", {}).get("trend") == TREND_UP:
        signals.append("📈 月线级别多头，大格局看多")
    if details.get("monthly", {}).get("trend") == TREND_DOWN:
        signals.append("📉 月线级别空头，谨慎抄底")

    return {"trend": final_trend, "score": final_score, "details": details, "signals": signals}


# ─── 测试 ───
if __name__ == "__main__":
    code = "603538"
    print(f"=== {code} 多时间框架分析 ===")
    data = get_multiple_timeframes(code)
    if "error" in data:
        print(f"错误: {data['error']}")
        sys.exit(1)

    trend = judge_trend(data.get("indicators", {}))
    print(f"\n趋势: {trend['trend']} (评分: {trend['score']}/100)")
    print(f"信号:")
    for s in trend.get("signals", []):
        print(f"  {s}")

    print(f"\n各周期:")
    for tf, detail in trend.get("details", {}).items():
        print(f"  {tf}: {detail['trend']} ({detail['score']}/100) | {detail['summary']}")

    if data.get("realtime"):
        r = data["realtime"]
        print(f"\n实时: {r['name']} ¥{r['price']:.2f} ({r['change_pct']:+.2f}%)")
