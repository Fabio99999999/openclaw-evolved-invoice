#!/usr/bin/env python3
"""
市场综合情绪监控 v2 — 7+4 监控维度

文献参考:
  - 《因子投资：方法与实践》石川(2020) — 因子体系
  - WorldQuant Alpha101 — Alpha#3(量价背离), Alpha#41(涨停板), Alpha#50(板块联动)
  - 《算法交易》Kissell(2021) — VWAP偏离度, 执行分析
  - BigQuant多因子系统 — 市场温度/情绪指标
  - 平头哥短线量化系统 — 市场强度、情绪周期
  - 《金融计量学》Tsay(2010) — 波动率/布林带
  - 《打开量化投资的黑箱》Narang(2013) — 量化全框架
  - Qlib Alpha158(Microsoft) — 158个量价因子
  - Marcel Link《高胜算操盘》— 趋势/量能/止损

数据源:
  1. 东方财富实时API — 板块行情、涨跌停(意大利部分超时⚠️)
  2. akshare — 融资融券、北向资金(意大利直连✅)
  3. FaceCat API — 全市场OHLC(意大利直连✅)
  4. 新浪 hq.sinajs.cn — 实时报价(意大利直连✅)

用法:
    python3 market_monitor.py                            # 综合市场监控(完整报告)
    python3 market_monitor.py --brief                    # 精简版(嵌入盘中cron)
    python3 market_monitor.py --portfolio                # 持仓股量价背离+VWAP+布林带
    python3 market_monitor.py --sector 新能源            # 指定板块查询
    python3 market_monitor.py --json                     # 结构化输出
"""
import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request

# ─────────────── 量化核心模型 ───────────────
try:
    # 同时支持 scripts/ 和 . 两种运行路径
    from quant_models import (
        kelly_criterion, half_kelly, kelly_with_stop,
        garch_predict_volatility, garch_vol_signal,
        markowitz_optimize, markowitz_compare,
        pca_factor_orthogonalize, pca_factor_report
    )
    QUANT_MODELS_AVAILABLE = True
except ImportError:
    try:
        from scripts.quant_models import (
            kelly_criterion, half_kelly, kelly_with_stop,
            garch_predict_volatility, garch_vol_signal,
            markowitz_optimize, markowitz_compare,
            pca_factor_orthogonalize, pca_factor_report
        )
        QUANT_MODELS_AVAILABLE = True
    except ImportError:
        QUANT_MODELS_AVAILABLE = False
        import sys
        print(f"[warn] quant_models not loaded (sys.path: {sys.path[:3]})")

# ─────────────── 配置 ───────────────

PORTFOLIO = {
    "603778": "国晟科技",
    "000890": "法尔胜",
    "300139": "晓程科技",
    "600593": "德龙汇能",
    "603538": "美诺华",
    "300342": "天银机电",
    "603178": "圣龙股份",
    "002442": "龙星科技",
}

PORTFOLIO_SECTORS = {
    "603778": ["光伏", "建筑"],
    "000890": ["金属制品", "特钢"],
    "300139": ["黄金", "金属"],
    "600593": ["燃气", "能源"],
    "603538": ["化学制药", "医药"],
    "300342": ["军工", "传感器"],
    "603178": ["汽车零部件", "新能源车"],
    "002442": ["化工", "橡胶"],
}

EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

# ─────────────── 文献因子: VWAP偏离度 ───────────────
# 来源: 《算法交易》Kissell Ch.7, WorldQuant Alpha#3


def check_price_volume_divergence(price_chg: float, vol_chg: float) -> dict:
    """量价背离检测 — WorldQuant Alpha#3 简化版
    Alpha#3 原式: rank(return_5d) * rank(volume_5d) → 量价相关系数
    
    返回: {"score": int (-30~30), "signal": str, "level": str}
    """
    signals = []
    score = 0

    if price_chg > 2 and vol_chg < -10:
        signals.append("⚠️ 量价背离 — 价涨量缩，上行乏力")
        score = -20
    elif price_chg < -2 and vol_chg > 20:
        signals.append("⚠️ 放量下跌 — 恐慌抛售")
        score = -30
    elif price_chg > 2 and vol_chg > 20:
        signals.append("✅ 价量齐升 — 健康上涨")
        score = 30
    elif price_chg < -2 and vol_chg < -10:
        signals.append("⚖️ 缩量调整 — 洗盘可能")
        score = 10
    elif abs(price_chg) < 2 and vol_chg > 30:
        signals.append("⚠️ 放量滞涨/跌 — 多空分歧加大")
        score = -10

    if not signals:
        signals.append("🔹 量价正常")
        score = 0

    level = {30: "strong_buy", 10: "weak_buy", 0: "neutral",
             -10: "weak_sell", -20: "sell", -30: "strong_sell"}.get(score, "neutral")

    return {"score": score, "signals": signals, "level": level}


def check_vwap_deviation(price: float, vwap: float) -> dict:
    """VWAP偏离度检测 — Kissell《算法交易》
    用法: 当前价偏离VWAP的程度
    - >+3%: 高位，回调风险
    - <-3%: 低位，反弹可能
    """
    if vwap is None or vwap == 0:
        return {"score": 0, "signal": "无VWAP数据", "level": "unknown"}
    dev = (price - vwap) / vwap * 100

    score = 0
    signal = ""
    level = "neutral"

    if dev > 3:
        score = -15
        signal = f"⚠️ VWAP偏离 +{dev:.1f}% — 高于VWAP>3%，回调风险"
        level = "sell"
    elif dev > 1.5:
        score = -5
        signal = f"📈 VWAP偏离 +{dev:.1f}% — 偏高"
        level = "weak_sell"
    elif dev < -3:
        score = -15
        signal = f"⚠️ VWAP偏离 {dev:.1f}% — 低于VWAP>3%，弱势"
        level = "sell"
    elif dev < -1.5:
        score = -5
        signal = f"📉 VWAP偏离 {dev:.1f}% — 偏低"
        level = "weak_buy"
    else:
        score = 5
        signal = f"⚖️ VWAP偏离 {dev:+.1f}% — 正常"
        level = "buy"

    return {"score": score, "signal": signal, "level": level, "deviation_pct": round(dev, 2)}


# ─────────────── 文献因子: 布林带/ATR波动率 ───────────────
# 来源: 《金融计量学》Tsay Ch.4, Marc Link Ch.6


def calc_bollinger(close_prices: List[float], period: int = 20, std_mult: float = 2.0) -> dict:
    """布林带计算
    返回: {"ma": float, "upper": float, "lower": float, 
           "band_width": float, "band_position": float,
           "signal": str, "score": int}
    """
    if len(close_prices) < period:
        return {"ma": None, "upper": None, "lower": None,
                "signal": f"数据不足(需{period}天, 有{len(close_prices)}天)", "score": 0}

    recent = close_prices[-period:]
    ma = sum(recent) / period
    variance = sum((x - ma) ** 2 for x in recent) / period
    std = math.sqrt(variance)

    upper = ma + std_mult * std
    lower = ma - std_mult * std
    band_width = (upper - lower) / ma * 100
    current = close_prices[-1]

    # 布林带位置 (0=下轨, 1=上轨)
    if upper != lower:
        band_pos = (current - lower) / (upper - lower)
    else:
        band_pos = 0.5

    # 信号判断
    score = 0
    signal = ""
    if current >= upper:
        score = -20
        signal = f"⚠️ 突破布林上轨 ¥{upper:.2f} — 超买，回调概率大"
    elif current <= lower:
        score = 20
        signal = f"🎯 跌破布林下轨 ¥{lower:.2f} — 超卖，反弹机会"
    elif current >= ma:
        score = 5
        signal = f"📈 布林中轨上方 ¥{ma:.2f} — 偏多"
    else:
        score = -5
        signal = f"📉 布林中轨下方 ¥{ma:.2f} — 偏空"

    # 布林带收缩 → 变盘预警
    if band_width < 5:
        signal += " | 🔔 布林带收窄<5%，变盘预警"

    return {
        "ma": round(ma, 2), "upper": round(upper, 2), "lower": round(lower, 2),
        "band_width": round(band_width, 2), "band_position": round(band_pos, 2),
        "signal": signal, "score": score, "current": current
    }


def calc_atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> dict:
    """ATR波动率计算 — Tsay《金融计量学》
    ATR = 过去N日真实波幅的移动平均
    返回: {"atr": float, "atr_pct": float, "signal": str}
    """
    if len(high) < period + 1 or len(low) < period + 1 or len(close) < period + 1:
        return {"atr": None, "atr_pct": None, "signal": f"数据不足(需{period+1}天)"}

    tr_values = []
    for i in range(-period, 0):
        h = high[i]
        l = low[i]
        pc = close[i - 1] if (i - 1) >= -len(close) else close[i]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_values.append(tr)

    atr = sum(tr_values) / period
    current_close = close[-1]
    atr_pct = (atr / current_close) * 100 if current_close else 0

    # 波动率信号
    signal = ""
    if atr_pct > 5:
        signal = f"⚠️ ATR波动率 {atr_pct:.1f}% — 高波动，止损应放宽"
    elif atr_pct > 3:
        signal = f"📊 ATR波动率 {atr_pct:.1f}% — 中等波动"
    else:
        signal = f"✅ ATR波动率 {atr_pct:.1f}% — 低波动，止损应收紧"

    return {"atr": round(atr, 3), "atr_pct": round(atr_pct, 2), "signal": signal}


# ─────────────── FaceCat API 数据获取 (意大利主力) ───────────────
# 主力数据源，支付宝接口直连


import urllib.parse


def fetch_efinance_kline(code: str, days: int = 25) -> List[dict]:
    """从efinance获取历史K线 (备用, 带超时)
    日期格式: YYYYMMDD (无横杠)
    """
    import threading
    result = []
    exception = []
    
    def _fetch():
        nonlocal result, exception
        try:
            import efinance as ef
            df = ef.stock.get_quote_history(code, klt=101, fqt=1)
            if df is None or df.empty:
                exception.append(ValueError("空响应"))
                return
            bars = []
            for _, row in df.iterrows():
                bar = {
                    "date": str(row.get("日期", "")),
                    "open": float(row.get("开盘", 0)),
                    "close": float(row.get("收盘", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "volume": float(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                }
                bars.append(bar)
            bars.sort(key=lambda x: x["date"])
            result.extend(bars[-days:] if days > 0 else bars)
        except Exception as e:
            exception.append(e)
    
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=12)  # 12秒超时
    if t.is_alive():
        print(f"[efinance] {code} 超时", file=sys.stderr)
        return []
    if exception:
        print(f"[efinance] {code} 获取失败: {exception[0]}", file=sys.stderr)
        return []
    return result


def fetch_kline(code: str, days: int = 25) -> List[dict]:
    """K线数据获取: FaceCat(首选) → efinance(备用)"""
    # 标准化工股票代码
    sc = code.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    url = f"http://www.jjmfc.com:9968/quote?type=getkline&code={sc}&period=%C8%D5%CF%DF&start=&count={days}"
    try:
        req = urlopen(url, timeout=5)
        raw = req.read()
        data = raw.decode("gbk", errors="replace").strip()
        if not data:
            raise ValueError("空响应")
        lines = data.split("\n")
        bars = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            bar = {
                "date": parts[0].strip(),
                "open": float(parts[1]) if parts[1] else 0,
                "high": float(parts[2]) if parts[2] else 0,
                "low": float(parts[3]) if parts[3] else 0,
                "close": float(parts[4]) if parts[4] else 0,
                "volume": float(parts[5]) if len(parts) > 5 and parts[5] else 0,
            }
            bars.append(bar)
        if bars:
            print(f"[FaceCat] {code} K线 {len(bars)}条", file=sys.stderr)
            return bars
    except Exception as e:
        print(f"[FaceCat] {code} 跳过: {e}", file=sys.stderr)
    
    # 备用: efinance
    print(f"[efinance] {code} 备用获取...", file=sys.stderr)
    return fetch_efinance_kline(code, days)


def fetch_facecat_quote(code: str) -> dict:
    """从FaceCat获取实时报价"""
    sc = code.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    url = f"http://www.jjmfc.com:9968/quote?type=price&code={sc}"
    try:
        req = urlopen(url, timeout=5)
        data = req.read().decode("utf-8").strip()
        return {"raw": data, "code": code}
    except Exception as e:
        return {"error": str(e), "code": code}


def fetch_sina_quote(code: str) -> dict:
    """新浪实时报价 — hq.sinajs.cn (意大利可用)
    返回: {"price": float, "change": float, "open": float, ...}
    """
    # 代码转新浪格式
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"https://hq.sinajs.cn/list={prefix}{code}"
    try:
        req = Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        resp = urlopen(req, timeout=5)
        raw = resp.read().decode("gbk").strip()
        # 解析: var hq_str_sh603538="美诺华,62.46,-2.84,59.62,61.43,62.50,...
        parts = raw.split('"')
        if len(parts) >= 2:
            fields = parts[1].split(",")
            if len(fields) >= 32:
                name = fields[0]
                open_p = float(fields[1]) if fields[1] else 0
                prev_close = float(fields[2]) if fields[2] else 0
                price = float(fields[3]) if fields[3] else 0
                high = float(fields[4]) if fields[4] else 0
                low = float(fields[5]) if fields[5] else 0
                vol = float(fields[8]) if fields[8] else 0  # 手
                amount = float(fields[9]) if fields[9] else 0  # 元
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
                return {
                    "code": code, "name": name,
                    "price": price, "prev_close": prev_close,
                    "open": open_p, "high": high, "low": low,
                    "volume": vol, "amount": amount,
                    "change_pct": round(change_pct, 2),
                    "price_change": round(price - prev_close, 2),
                }
    except Exception as e:
        return {"error": str(e), "code": code}
    return {"error": "parse_failed", "code": code}


# ─────────────── 持仓股文献因子分析 ───────────────
# Alpha#3 + Kissell + Tsay + Marc Link


def analyze_portfolio_alpha_factors() -> str:
    """分析持仓股的4大文献因子:
    1. 量价背离 (Alpha#3)
    2. VWAP偏离度 (Kissell)
    3. 布林带位置 (Tsay)
    4. ATR波动率 (Link Ch.6)
    """
    lines = []
    lines.append("\n" + "═" * 50)
    lines.append("🧬 **文献因子: 持仓个股4维分析**")
    lines.append("量价背离(Alpha#3) | VWAP(Kissell) | 布林带(Tsay) | ATR(Link)")
    lines.append("═" * 50)

    for code, name in PORTFOLIO.items():
        # 1. 获取K线数据
        bars = fetch_kline(code, 25)

        # 2. 获取新浪实时报价
        quote = fetch_sina_quote(code)

        if not bars or "error" in quote:
            lines.append(f"\n📌 **{name}({code})** — 数据暂不可用")
            continue

        # 提取数据
        close_prices = [b["close"] for b in bars if b["close"] > 0]
        highs = [b["high"] for b in bars if b["high"] > 0]
        lows = [b["low"] for b in bars if b["low"] > 0]
        volumes = [b["volume"] for b in bars if b["volume"] > 0]

        if len(close_prices) < 3:
            lines.append(f"\n📌 **{name}({code})** — K线数据不足")
            continue

        # 今日数据
        today_bar = bars[-1] if bars else None
        yesterday_bar = bars[-2] if len(bars) >= 2 else None

        price = quote.get("price", close_prices[-1])
        prev_close = quote.get("prev_close", close_prices[-2] if len(close_prices) >= 2 else close_prices[-1])
        today_chg = ((price - prev_close) / prev_close * 100) if prev_close else 0

        # --- 因子1: 量价背离 (Alpha#3) ---
        if today_bar and yesterday_bar:
            today_vol = today_bar["volume"]
            yesterday_vol = yesterday_bar["volume"]
            vol_chg = ((today_vol - yesterday_vol) / yesterday_vol * 100) if yesterday_vol else 0
        else:
            vol_chg = 0

        pv = check_price_volume_divergence(today_chg, vol_chg)

        # --- 因子2: VWAP偏离度 (Kissell) ---
        # 估算VWAP: 当日成交额/成交量
        vwap = 0
        if today_bar and today_bar["volume"] > 0 and quote.get("amount", 0) > 0:
            vwap = quote["amount"] / (today_bar["volume"] * 100)  # 元/股
        else:
            # 用(high+low+close)/3 近似
            vwap = (quote.get("high", price) + quote.get("low", price) + price) / 3

        vwap_result = check_vwap_deviation(price, vwap)

        # --- 因子3: 布林带 (Tsay) ---
        boll = calc_bollinger(close_prices)

        # --- 因子4: ATR波动率 (Link Ch.6) ---
        atr_result = calc_atr(highs, lows, close_prices)

        # --- 因子5(补充): 持仓盈亏 ---
        cost_prices = {"603778": 8.79, "000890": 24.735, "300139": 54.125,
                       "600593": 25.887, "603538": 66.257, "300342": 70.826,
                       "603178": 18.802, "002442": 6.311}
        cost = cost_prices.get(code, 0)
        profit_pct = ((price - cost) / cost * 100) if cost else 0

        # --- 汇总评分 ---
        total_score = (pv["score"] or 0) + (vwap_result["score"] or 0) + \
                      (boll.get("score", 0) or 0)

        # --- 输出 ---
        emoji = "🟢" if total_score >= 10 else ("🔴" if total_score <= -10 else "🟡")

        lines.append(f"\n{emoji} **{name}({code})** 综合因子分: {total_score:+d}")
        lines.append(f"  当前 ¥{price:.2f} | 今日 {today_chg:+.2f}% | 浮盈 {profit_pct:+.1f}%")

        # 因子1
        s = pv["signals"][0] if pv["signals"] else "🔹 量价正常"
        lines.append(f"  📊 量价背离: {s}")

        # 因子2
        lines.append(f"  📈 VWAP偏离: {vwap_result.get('signal', 'N/A')}")

        # 因子3
        lines.append(f"  📐 布林带: {boll.get('signal', 'N/A')}")
        if boll.get("band_width"):
            bw = boll["band_width"]
            bw_signal = "🔔 变盘预警" if bw < 5 else "正常"
            lines.append(f"     带宽 {bw:.1f}%({bw_signal}) | 位置 {boll.get('band_position', 0):.0%} | MA{boll.get('ma', 0):.2f}")

        # 因子4
        lines.append(f"  📊 ATR波动: {atr_result.get('signal', 'N/A')}")

        # 综合判断
        if total_score >= 20:
            lines.append(f"  ✅ **评判**: 多因子共振偏多")
        elif total_score <= -20:
            lines.append(f"  ❌ **评判**: 多因子共振偏空")
        else:
            lines.append(f"  ➖ **评判**: 信号中性，需结合大盘和新闻")

    lines.append("\n" + "═" * 50)
    return "\n".join(lines)


# ─────────────── 原有监控功能 ───────────────


def fetch_sector_performance(top_n: int = 10) -> List[dict]:
    """东方财富板块涨跌幅排行"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz={}&po=1&np=1"
        "&fields=f2,f3,f4,f12,f14&fid=f3"
        "&fs=m:90+t:2"
    ).format(top_n)
    try:
        req = Request(url, headers=EM_HEADERS)
        resp = urlopen(req, timeout=8)
        raw = resp.read().decode("utf-8")
        # 提取JSON
        m = re.search(r'"diff":(\[.*?\])', raw)
        if not m:
            return [{"error": "parse_failed"}]
        data = json.loads(m.group(1))
        return [{"name": it["f14"], "change_pct": it.get("f3", 0)} for it in data]
    except Exception as e:
        return [{"error": str(e)}]


def fetch_concept_sector_performance(top_n: int = 10) -> List[dict]:
    """概念板块涨跌幅排行"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz={}&po=1&np=1"
        "&fields=f2,f3,f4,f12,f14&fid=f3"
        "&fs=m:90+t:3"
    ).format(top_n)
    try:
        req = Request(url, headers=EM_HEADERS)
        resp = urlopen(req, timeout=8)
        raw = resp.read().decode("utf-8")
        m = re.search(r'"diff":(\[.*?\])', raw)
        if not m:
            return [{"error": "parse_failed"}]
        data = json.loads(m.group(1))
        return [{"name": it["f14"], "change_pct": it.get("f3", 0)} for it in data]
    except Exception as e:
        return [{"error": str(e)}]


def check_portfolio_sector_sentiment() -> Dict[str, List[dict]]:
    """检查持仓股所属板块的今日表现"""
    result = {}
    try:
        sectors = fetch_sector_performance(50)
        concepts = fetch_concept_sector_performance(50)
        all_items = sectors + concepts
        for code, secs in PORTFOLIO_SECTORS.items():
            matches = []
            for s in all_items:
                if "error" in s:
                    continue
                for ps in secs:
                    if ps in s["name"]:
                        matches.append({"板块": s["name"], "涨跌幅": f"{s['change_pct']:+.2f}%"})
                        break
            result[code] = matches[:3]
    except Exception as e:
        for code in PORTFOLIO:
            result[code] = [{"板块": "获取失败", "涨跌幅": str(e)}]
    return result


def fetch_limit_up_down() -> dict:
    """涨跌停统计"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz=200&po=1&np=1"
        "&fields=f2,f3,f12,f14&fid=f3"
        "&fs=m:0+t:6+f:!50,m:0+t:80+f:!50"
        "&ut=bd1d9ddb04089700cf9c27f6f7426281"
    )
    try:
        req = Request(url, headers=EM_HEADERS)
        resp = urlopen(req, timeout=8)
        raw = resp.read().decode("utf-8")
        m = re.search(r'"diff":(\[.*?\])', raw)
        if not m:
            return {"error": "parse_failed"}
        data = json.loads(m.group(1))
        limit_up = [it for it in data if it.get("f3", 0) >= 9.9]
        limit_down = [it for it in data if it.get("f3", 0) <= -9.9]
        return {
            "涨停数": len(limit_up),
            "跌停数": len(limit_down),
            "涨停股票": [it.get("f14", "") for it in limit_up[:10]],
            "跌停股票": [it.get("f14", "") for it in limit_down[:10]],
        }
    except Exception as e:
        return {"error": str(e)}


def get_limit_up_down_summary() -> str:
    """涨跌停汇总"""
    data = fetch_limit_up_down()
    if "error" in data:
        return "🚀 涨跌停: 数据暂不可用"
    s = f"🚀 涨停:{data['涨停数']} | 🐻 跌停:{data['跌停数']}"
    if data["涨停数"] > 0:
        tops = ", ".join(data["涨停股票"][:5])
        s += f"\n  涨停: {tops}"
    if data["跌停数"] > 0:
        downs = ", ".join(data["跌停股票"][:3])
        s += f"\n  跌停: {downs}"
    return s


def get_margin_summary() -> str:
    """融资融券汇总 — 导入margin_monitor"""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from margin_monitor import fetch_sse_market_summary
        mkt = fetch_sse_market_summary()
        lines = ["💰 **融资融券**"]
        if "error" in mkt:
            lines.append(f"  {mkt['error']}")
        else:
            lines.append(f"  融资余额: ¥{mkt.get('融资余额(亿)', '?')}亿")
            lines.append(f"  融券余额: ¥{mkt.get('融券余额(亿)', '?')}亿")
            lines.append(f"  融券占比: {mkt.get('融券占比(%)', '?')}%")
    except Exception as e:
        return f"💰 融资融券: 暂不可用 ({e})"
    return "\n".join(lines)


def fetch_north_bound_flow() -> dict:
    """北向资金净流入 — akshare"""
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪股通")
        if df.empty:
            return {"沪股通": {"净买额(亿)": 0, "净流入(亿)": 0},
                    "深股通": {"净买额(亿)": 0, "净流入(亿)": 0}}
        latest = df.iloc[-1]
        return {
            "沪股通": {
                "净买额(亿)": round(float(latest.get("value", 0)), 2),
                "净流入(亿)": round(float(latest.get("value", 0)), 2),
            },
            "深股通": {"净买额(亿)": 0, "净流入(亿)": 0}  # 简化处理
        }
    except Exception as e:
        return {"error": f"北向资金获取失败: {e}"}


def get_north_bound_summary() -> str:
    """北向资金汇总文本"""
    data = fetch_north_bound_flow()
    if "error" in data:
        return f"🇨🇳 北向资金: {data['error']}"
    if not data or data.get("沪股通", {}).get("净买额(亿)", 0) == 0:
        return "🇨🇳 北向资金: 暂无数据 (非交易时间)"
    sh = data.get("沪股通", {})
    sz = data.get("深股通", {})
    total = sh.get("净买额(亿)", 0) + sz.get("净买额(亿)", 0)
    arrow = "🟢" if total > 0 else ("🔴" if total < 0 else "⚪")
    return f"🇨🇳 北向资金: {arrow} 净买额 ¥{abs(total):.2f}亿 ({'流入' if total>0 else '流出' if total<0 else '持平'})"


def fetch_market_breadth() -> dict:
    """市场宽度: 涨跌家数、成交额"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz=5000&po=1&np=1"
        "&fields=f2,f3,f12,f14&fid=f3"
        "&fs=m:0+t:6+f:!50,m:0+t:80+f:!50"
        "&ut=bd1d9ddb04089700cf9c27f6f7426281"
    )
    try:
        req = Request(url, headers=EM_HEADERS)
        resp = urlopen(req, timeout=8)
        raw = resp.read().decode("utf-8")
        m = re.search(r'"diff":(\[.*?\])', raw)
        if not m:
            return {"error": "parse_failed"}
        data = json.loads(m.group(1))
        up = len([it for it in data if it.get("f3", 0) > 0])
        down = len([it for it in data if it.get("f3", 0) < 0])
        flat = len(data) - up - down
        return {"上涨": up, "下跌": down, "平盘": flat, "总数": len(data)}
    except Exception as e:
        return {"error": str(e)}


def get_market_sentiment_summary() -> str:
    """市场温度"""
    breadth = fetch_market_breadth()
    if "error" in breadth:
        return f"🌡️ 市场温度: 暂不可用"
    up = breadth.get("上涨", 0)
    down = breadth.get("下跌", 0)
    total = breadth.get("总数", 1)
    up_ratio = up / total if total else 0
    # 温度计
    if up_ratio > 0.6:
        temp = "🔥 亢奋"
    elif up_ratio > 0.5:
        temp = "🟢 偏暖"
    elif up_ratio > 0.3:
        temp = "⚪ 中性"
    else:
        temp = "🔵 偏冷"

    return f"🌡️ 市场温度: {temp}\n  涨 {up} | 跌 {down} | 平 {breadth.get('平盘', 0)} | 涨跌比 {up/(down+1):.2f}"


# ─────────────── 主报告生成 ───────────────


def generate_full_report() -> str:
    """生成综合市场监控报告"""
    lines = [
        f"📡 **A股市场综合监控看板** — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 50,
    ]

    # 1. 市场温度
    lines.append("\n" + get_market_sentiment_summary())

    # 2. 涨跌停
    lines.append("\n" + get_limit_up_down_summary())

    # 3. 板块异动
    print("正在获取板块异动...", file=sys.stderr)
    sectors = fetch_sector_performance(8)
    if sectors and "error" not in sectors[0]:
        lines.append(f"\n📊 **板块异动TOP8**")
        for s in sectors:
            arrow = "🟢" if s["change_pct"] > 0 else ("🔴" if s["change_pct"] < 0 else "⚪")
            lines.append(f"  {arrow} {s['name']}: {s['change_pct']:+.2f}%")
    else:
        print(f"  板块数据: {sectors}", file=sys.stderr)
        lines.append(f"\n⚠️ 板块数据暂不可用(意大利连接超时)")

    # 4. 持仓股板块情绪
    print("正在检查持仓板块情绪...", file=sys.stderr)
    sector_sentiment = check_portfolio_sector_sentiment()
    lines.append("\n📌 **持仓股板块情绪**")
    for code, sectors in sector_sentiment.items():
        name = PORTFOLIO.get(code, code)
        if sectors and "板块" in sectors[0]:
            sector_strs = [f"{s['板块']}({s['涨跌幅']})" for s in sectors[:2]]
            lines.append(f"  {name}({code}): {' | '.join(sector_strs)}")
        else:
            lines.append(f"  {name}({code}): 暂不可用")

    # 5. 融资融券
    print("正在获取融资融券...", file=sys.stderr)
    lines.append("\n" + get_margin_summary())

    # 6. 概念板块TOP5
    print("正在获取概念板块...", file=sys.stderr)
    concepts = fetch_concept_sector_performance(5)
    if concepts and "error" not in concepts[0]:
        lines.append(f"\n💡 **概念热点TOP5**")
        for c in concepts:
            arrow = "🟢" if c["change_pct"] > 0 else "🔴"
            lines.append(f"  {arrow} {c['name']}: {c['change_pct']:+.2f}%")
    else:
        lines.append(f"\n⚠️ 概念板块数据暂不可用")

    # 7. 北向资金
    print("正在获取北向资金...", file=sys.stderr)
    lines.append("\n" + get_north_bound_summary())

    # ===== 新增: 8. 持仓4大文献因子分析 =====
    print("正在分析持仓文献因子(量价背离/VWAP/布林带/ATR)...", file=sys.stderr)
    lines.append(analyze_portfolio_alpha_factors())

    return "\n".join(lines)


def generate_brief() -> str:
    """精简版 — 嵌入盘中监控cron"""
    lines = [f"📡 **盘中监控补充** — {datetime.now().strftime('%H:%M')}"]

    # 市场宽度
    breadth = fetch_market_breadth()
    if "error" not in breadth:
        up = breadth.get("上涨", 0)
        down = breadth.get("下跌", 0)
        total = breadth.get("总数", 0)
        up_ratio = up / total if total else 0
        temp = "🔥亢奋" if up_ratio > 0.6 else ("🟢偏暖" if up_ratio > 0.5 else ("⚪中性" if up_ratio > 0.3 else "🔵偏冷"))
        lines.append(f"  🌡️ 涨跌: {up}/{down} | 温度: {temp}")
    else:
        lines.append(f"  🌡️ 市场宽度: 暂不可用")

    # 涨跌停
    limit = fetch_limit_up_down()
    if "error" not in limit:
        lines.append(f"  🚀 涨停: {limit['涨停数']} | 🐻 跌停: {limit['跌停数']}")
    else:
        lines.append(f"  🚀 涨跌停: 暂不可用")

    # 板块TOP3
    sectors = fetch_sector_performance(3)
    if sectors and "error" not in sectors[0]:
        sector_str = " | ".join([f"{s['name']}{s['change_pct']:+.1f}%" for s in sectors])
        lines.append(f"  📊 板块: {sector_str}")

    # 北向资金
    lines.append(f"  " + get_north_bound_summary())

    return "\n".join(lines)


# ─────────────── CLI入口 ───────────────


def main():
    parser = argparse.ArgumentParser(description="市场综合监控 v2 — 7+4 文献因子监控")
    parser.add_argument("--brief", "-b", action="store_true", help="精简版(嵌入cron)")
    parser.add_argument("--portfolio", "-p", action="store_true", help="持仓4大文献因子分析")
    parser.add_argument("--models", "-m", action="store_true", help="量化核心模型: 凯利+GARCH+马科维茨+PCA")
    parser.add_argument("--json", "-j", action="store_true", help="JSON输出")
    parser.add_argument("--sector", help="查询指定板块")
    args = parser.parse_args()

    if args.brief:
        print(generate_brief())
        return

    if args.portfolio:
        print(analyze_portfolio_alpha_factors())
        return

    if args.models:
        print(generate_models_report())
        return

    if args.sector:
        sectors = fetch_sector_performance(50)
        concepts = fetch_concept_sector_performance(50)
        all_items = [
            *[{"name": s["name"], "change_pct": s["change_pct"], "type": "行业"}
              for s in sectors if "error" not in s],
            *[{"name": c["name"], "change_pct": c["change_pct"], "type": "概念"}
              for c in concepts if "error" not in c],
        ]
        matches = [x for x in all_items if args.sector in x["name"]]
        if matches:
            print(f"📊 **{args.sector} 相关板块**")
            for m in matches[:10]:
                print(f"  {'🟢' if m['change_pct'] > 0 else '🔴'} [{m['type']}] {m['name']}: {m['change_pct']:+.2f}%")
        else:
            print(f"未找到包含「{args.sector}」的板块")
        return

    if args.json:
        result = {
            "market_breadth": fetch_market_breadth(),
            "limit_up_down": fetch_limit_up_down(),
            "sectors_top": [s for s in fetch_sector_performance(10) if "error" not in s],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(generate_full_report())


def generate_models_report():
    """量化核心模型报告: 凯利 + GARCH + 马科维茨 + PCA (缓存一次数据)"""
    if not QUANT_MODELS_AVAILABLE:
        return "❌ quant_models.py 未加载"
    
    import pandas as pd
    import numpy as np
    
    lines = []
    today = datetime.now()
    lines.append(f"═══ 量化核心模型报告 {today.strftime('%Y-%m-%d %H:%M')} ═══")
    lines.append("凯利(Kelly) | GARCH(1,1) | 马科维茨(Markowitz) | PCA\n")
    
    # ── 一次性获取所有K线 ──
    all_klines = {}
    print(f"[models] 获取{len(PORTFOLIO)}只股票K线...", file=sys.stderr)
    for code, name in PORTFOLIO.items():
        klines = fetch_kline(code)
        if klines and len(klines) > 10:
            all_klines[code] = klines
    print(f"[models] 获取完成: {len(all_klines)}只", file=sys.stderr)
    
    # ── 凯利公式 ──
    lines.append("━" * 50)
    lines.append("1️⃣ 凯利公式仓位管理")
    lines.append("━" * 50)
    
    scenarios = [
        ("稳健策略", 0.55, 0.03, 0.02),
        ("激进策略", 0.50, 0.05, 0.02),
        ("保守策略", 0.60, 0.02, 0.01),
    ]
    lines.append(f"{'策略':<10} {'胜率':<8} {'均盈':<8} {'均亏':<8} {'全凯利':<10} {'半凯利':<10}")
    lines.append("-" * 54)
    for name, wr, aw, al in scenarios:
        k = kelly_criterion(wr, aw, al)
        h = half_kelly(wr, aw, al)
        lines.append(f"{name:<10} {wr:<7.0%} {aw:<7.1%} {al:<7.1%} {k:<9.1%} {h:<9.1%}")
    lines.append(f"")
    lines.append(f"  {'当前组合':<10} {'-':<8} {'-':<8} {'-':<8} {'使用半凯利推荐':<20}")
    
    # ── GARCH ──(用缓存数据)
    lines.append("")
    lines.append("━" * 50)
    lines.append("2️⃣ GARCH(1,1) 波动率预测 (持有个股)")
    lines.append("━" * 50)
    
    for code, klines in all_klines.items():
        name = PORTFOLIO[code]
        prices = np.array([k['close'] for k in klines])
        if len(prices) >= 20:
            vol = garch_predict_volatility(prices)
            sig, mult = garch_vol_signal(vol)
            lines.append(f"  {name}({code}): 年化波动 {vol:.1%} → {sig}")
        else:
            lines.append(f"  {name}({code}): 数据不足")
    
    # ── 马科维茨 ──(用缓存数据)
    lines.append("")
    lines.append("━" * 50)
    lines.append("3️⃣ 马科维茨组合优化")
    lines.append("━" * 50)
    
    prices_dict = {code: [k['close'] for k in kls] for code, kls in all_klines.items()}
    if len(prices_dict) >= 2:
        min_len = min(len(v) for v in prices_dict.values())
        if min_len >= 15:
            aligned = {k: v[-min_len:] for k, v in prices_dict.items()}
            prices_df = pd.DataFrame(aligned)
            shares = {code: 1000 for code in PORTFOLIO}
            lines.append(markowitz_compare(shares, prices_df))
        else:
            lines.append("  数据不足15天")
    else:
        lines.append("  数据不足2只")
    
    # ── PCA ──(用缓存数据)
    lines.append("")
    lines.append("━" * 50)
    lines.append("4️⃣ PCA因子正交化")
    lines.append("━" * 50)
    
    try:
        factor_data = {}
        for code, klines in all_klines.items():
            prices = np.array([k['close'] for k in klines])
            volumes = np.array([k['volume'] for k in klines])
            ret = np.diff(prices) / (prices[:-1] + 1e-8)
            vol_chg = np.diff(volumes) / (volumes[:-1] + 1e-8)
            min_l = min(len(ret), len(vol_chg))
            if min_l > 5:
                factor_data[f'{code}_动量'] = ret[:min_l]
                factor_data[f'{code}_量变'] = vol_chg[:min_l]
        
        if len(factor_data) >= 2:
            min_len = min(len(v) for v in factor_data.values())
            if min_len >= 10:
                aligned = {k: v[-min_len:] for k, v in factor_data.items()}
                factor_df = pd.DataFrame(aligned)
                lines.append(pca_factor_report(factor_df))
            else:
                lines.append("  因子数据不足")
        else:
            lines.append("  因子数据不足")
    except Exception as e:
        lines.append(f"  PCA错误: {e}")
    
    lines.append("\n" + "═" * 50)
    lines.append("💡 建议: 凯利仓位每月校准一次")
    lines.append("       GARCH波动率每日自动分析")
    lines.append("       马科维茨每季度再平衡")
    lines.append("       PCA因子正交化每周/月更新")
    
    return "\n".join(lines)


if __name__ == "__main__":
    main()
