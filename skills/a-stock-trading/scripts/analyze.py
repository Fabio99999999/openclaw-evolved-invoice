#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["efinance", "akshare", "baostock"]
# ///
"""
A股实时行情与分时量能分析工具 v2 — 多数据源融合

数据源优先级:
  1. efinance (东方财富) 🥇 — 主力实时+历史
  2. baostock 🥈 — 备用历史K线
  3. akshare (雪球) — 基本面查缺补漏
  4. 新浪财经 — 分时量能（保留）

Usage:
    python3 analyze.py 600789                    # 单只股票
    python3 analyze.py 600789 002446             # 多只股票
    python3 analyze.py 600789 --minute           # 分时量能分析
    python3 analyze.py 600789 --json             # JSON输出
    python3 analyze.py 600789 --fundamental      # 含基本面数据
    python3 analyze.py --history 603538 --days 20 # 历史K线
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# ─────────────── 代码格式转换 ───────────────

def normalize_code(code: str) -> str:
    """统一为6位纯数字"""
    c = code.upper().replace("SH", "").replace("SZ", "").replace("BJ", "").replace(".", "").strip()
    # 移除可能的前缀
    for prefix in ["SH", "SZ", "BJ"]:
        if c.startswith(prefix):
            c = c[len(prefix):]
    return c[:6]

def is_sh(code: str) -> bool:
    return code.startswith(("5", "6", "9"))

def is_sz(code: str) -> bool:
    return code.startswith(("0", "3"))

def is_bj(code: str) -> bool:
    return code.startswith(("4", "8"))

def to_baostock_symbol(code: str) -> str:
    cn = normalize_code(code)
    if is_sh(cn): return "sh." + cn
    elif is_sz(cn): return "sz." + cn
    else: return "sh." + cn  # fallback

def to_xq_symbol(code: str) -> str:
    """生成雪球代码"""
    cn = normalize_code(code)
    if is_sh(cn): return "SH" + cn
    elif is_sz(cn): return "SZ" + cn
    else: return "SH" + cn

# ─────────────── 数据源 1: efinance (主力) ───────────────

def fetch_realtime_efinance(codes: List[str]) -> Dict[str, Dict]:
    """efinance 批量实时行情"""
    result = {}
    try:
        import efinance as ef
        df = ef.stock.get_latest_quote(codes)
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            if not code:
                continue
            result[code] = {
                "code": code,
                "name": row.get("名称", ""),
                "price": float(row.get("最新价", 0) or 0),
                "open": float(row.get("今开", 0) or 0),
                "high": float(row.get("最高", 0) or 0),
                "low": float(row.get("最低", 0) or 0),
                "pre_close": float(row.get("昨日收盘", 0) or 0),
                "volume": int(float(row.get("成交量", 0) or 0)),  # 股
                "amount": float(row.get("成交额", 0) or 0),       # 元
                "change_pct": float(row.get("涨跌幅", 0) or 0),
                "change_amt": float(row.get("涨跌额", 0) or 0),
                "turnover": float(row.get("换手率", 0) or 0),
                "pe": float(row.get("动态市盈率", 0) or 0),
                "market_cap": float(row.get("总市值", 0) or 0),
                "circulating_cap": float(row.get("流通市值", 0) or 0),
                "volume_ratio": float(row.get("量比", 0) or 0),
                "source": "efinance",
            }
    except Exception as e:
        print(f"[efinance] 实时行情失败: {e}", file=sys.stderr)
    return result

def fetch_history_efinance(code: str, days: int = 20) -> Optional[List[Dict]]:
    """efinance 历史K线"""
    try:
        import efinance as ef
        end = datetime.now()
        start = end - timedelta(days=days * 2)  # 多取一些，去掉非交易日
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
                "volume": int(float(row.get("成交量", 0) or 0)),  # 股
                "amount": float(row.get("成交额", 0) or 0),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
            })
        return records[-days:]  # 只取需要的天数
    except Exception as e:
        print(f"[efinance] 历史K线失败: {e}", file=sys.stderr)
    return None

# ─────────────── 数据源 2: baostock (备用历史) ───────────────

def fetch_history_baostock(code: str, days: int = 20) -> Optional[List[Dict]]:
    """baostock 备用历史K线"""
    try:
        import baostock as bs
        import pandas as pd
        bs.login()
        symbol = to_baostock_symbol(code)
        end = datetime.now()
        start = end - timedelta(days=days * 2)
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,open,high,low,close,volume,amount,pctChg",
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="3"
        )
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        if not rows:
            return None
        records = []
        for row in rows:
            if not row[0]:
                continue
            records.append({
                "date": row[0],
                "open": float(row[1]) if row[1] else 0,
                "close": float(row[4]) if row[4] else 0,
                "high": float(row[2]) if row[2] else 0,
                "low": float(row[3]) if row[3] else 0,
                "volume": int(float(row[5])) if row[5] else 0,
                "amount": float(row[6]) if row[6] else 0,
                "change_pct": float(row[7]) if row[7] else 0,
            })
        return records[-days:]
    except Exception as e:
        print(f"[baostock] 历史K线失败: {e}", file=sys.stderr)
        try: bs.logout()
        except: pass
    return None

def fetch_history(code: str, days: int = 20) -> Optional[List[Dict]]:
    """历史K线：efinance 主 → baostock 备"""
    records = fetch_history_efinance(code, days)
    if records: return records
    records = fetch_history_baostock(code, days)
    if records: return records
    return None

# ─────────────── 数据源 3: akshare-雪球 (基本面) ───────────────

def fetch_fundamental_akshare(code: str) -> Optional[Dict]:
    """雪球个股行情（含基本面数据）"""
    try:
        import akshare as ak
        symbol = to_xq_symbol(code)
        df = ak.stock_individual_spot_xq(symbol=symbol)
        rows = dict(zip(df["item"], df["value"]))
        # 解析数值
        def sf(v):
            try: return float(v)
            except: return 0.0
        def si(v):
            try: return int(v)
            except: return 0
        return {
            "code": str(rows.get("代码", code)),
            "name": str(rows.get("名称", "")),
            "price": sf(rows.get("现价")),
            "change_pct": sf(rows.get("涨幅")),
            "change_amt": sf(rows.get("涨跌")),
            "open": sf(rows.get("今开")),
            "high": sf(rows.get("最高")),
            "low": sf(rows.get("最低")),
            "pre_close": sf(rows.get("昨收")),
            "volume": si(rows.get("成交量")) * 100,  # 雪球返回的是手，转股
            "amount": sf(rows.get("成交额")),
            "turnover": sf(rows.get("周转率")) / 100,  # 雪球的周转率是百分数
            "pe": sf(rows.get("市盈率(动)")),
            "pe_static": sf(rows.get("市盈率(静)")),
            "pb": sf(rows.get("市净率")),
            "dividend_yield": sf(rows.get("股息率(TTM)")),
            "market_cap": sf(rows.get("资产净值/总市值")),
            "circulating_value": sf(rows.get("流通值")),
            "amplitude": sf(rows.get("振幅")),
            "eps": sf(rows.get("每股收益")),
            "nav_per_share": sf(rows.get("每股净资产")),
            "high_52w": sf(rows.get("52周最高")),
            "low_52w": sf(rows.get("52周最低")),
            "yoy_return": sf(rows.get("今年以来涨幅")),
            "total_shares": si(rows.get("基金份额/总股本")),
            "circulating_shares": si(rows.get("流通股")),
            "halt_down": sf(rows.get("跌停")),
            "halt_up": sf(rows.get("涨停")),
            "source": "xueqiu",
        }
    except Exception as e:
        print(f"[xueqiu] 基本面查询失败: {e}", file=sys.stderr)
    return None

# ─────────────── 数据源 4: 新浪 (分时量能) ───────────────

def get_sina_symbol(code: str) -> str:
    cn = normalize_code(code)
    if is_sh(cn): return "sh" + cn
    elif is_sz(cn): return "sz" + cn
    elif is_bj(cn): return "bj" + cn
    return "sh" + cn

def fetch_minute_data_sina(symbol: str, count: int = 250) -> list[dict]:
    """新浪分时K线（保留原实现）"""
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{symbol}=/CN_MarketDataService.getKLineData?symbol={symbol}&scale=1&ma=no&datalen={count}"
    try:
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode("utf-8")
        match = re.search(r"\(\[(.*)\]\)", text, re.DOTALL)
        if not match:
            return []
        data = json.loads("[" + match.group(1) + "]")
        return [{
            "time": item["day"],
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "volume": int(item["volume"]),
            "amount": float(item["amount"]),
        } for item in data]
    except Exception as e:
        print(f"[sina] 分时接口错误: {e}", file=sys.stderr)
    return []

# ─────────────── 分时量能分析 ───────────────

def analyze_minute_volume(minute_data: list[dict]) -> dict:
    """分析分时量能（保留原算法）"""
    if not minute_data:
        return {"error": "无分时数据"}
    trading_data = [d for d in minute_data if d["volume"] > 0 and "09:25" <= d["time"][-8:-3] <= "15:00"]
    if not trading_data:
        return {"error": "无有效交易数据"}
    total_vol = sum(d["volume"] for d in trading_data)
    def period_vol(start, end):
        return sum(d["volume"] for d in trading_data if start <= d["time"][-8:-3] < end)
    open_30 = period_vol("09:30", "10:00")
    mid_am = period_vol("10:00", "11:30")
    mid_pm = period_vol("13:00", "14:30")
    close_30 = period_vol("14:30", "15:01")
    sorted_by_vol = sorted(trading_data, key=lambda x: x["volume"], reverse=True)[:10]
    top_volumes = [{"time": d["time"][-8:], "price": d["close"], "volume": d["volume"] // 100, "amount": d["amount"]} for d in sorted_by_vol]
    signals = []
    if total_vol > 0:
        if close_30 / total_vol > 0.25:
            signals.append("尾盘大幅放量，可能有主力抢筹或出货")
        elif close_30 / total_vol > 0.15:
            signals.append("尾盘有一定放量")
        if open_30 / total_vol > 0.30:
            signals.append("早盘主力抢筹明显")
        if open_30 / total_vol > 0.40:
            signals.append("早盘放量异常，主力强势介入")
    last_price = trading_data[-1]["close"] if trading_data else 0
    highest_vol_price = sorted_by_vol[0]["close"] if sorted_by_vol else 0
    if last_price > 0 and abs(last_price - highest_vol_price) < 0.01:
        signals.append("封板状态，关注封单量")
    return {
        "total_volume": total_vol // 100,
        "total_amount": sum(d["amount"] for d in trading_data),
        "distribution": {
            "open_30min": {"volume": open_30 // 100, "percent": round(open_30 / total_vol * 100, 1) if total_vol else 0},
            "mid_am": {"volume": mid_am // 100, "percent": round(mid_am / total_vol * 100, 1) if total_vol else 0},
            "mid_pm": {"volume": mid_pm // 100, "percent": round(mid_pm / total_vol * 100, 1) if total_vol else 0},
            "close_30min": {"volume": close_30 // 100, "percent": round(close_30 / total_vol * 100, 1) if total_vol else 0},
        },
        "top_volumes": top_volumes,
        "signals": signals,
    }

# ─────────────── 格式化输出 ───────────────

def format_realtime(data: dict) -> str:
    """格式化实时行情（efinance 格式）"""
    chg = data.get("change_pct", 0)
    cs = "+" if chg >= 0 else ""
    lines = [
        f"{'='*60}",
        f"股票: {data.get('name', '')} ({data.get('code', '')})",
        f"{'='*60}",
        f"",
        f"【实时行情】",
        f"  现价: {data.get('price', 0):.2f}  涨跌: {cs}{chg:.2f}%",
        f"  今开: {data.get('open', 0):.2f}  最高: {data.get('high', 0):.2f}  最低: {data.get('low', 0):.2f}",
        f"  昨收: {data.get('pre_close', 0):.2f}  换手: {data.get('turnover', 0):.2f}%",
        f"  成交量: {data.get('volume', 0)/10000:.1f}万手  成交额: {data.get('amount', 0)/100000000:.2f}亿",
    ]
    if data.get("pe"):
        lines.append(f"  市盈率: {data['pe']:.1f}  量比: {data.get('volume_ratio', 0):.2f}")
    if data.get("market_cap"):
        lines.append(f"  总市值: {data['market_cap']/100000000:.1f}亿  流通市值: {data.get('circulating_cap', 0)/100000000:.1f}亿")
    lines.append(f"  数据源: {data.get('source', 'unknown')}")
    return "\n".join(lines)

def format_fundamental(data: dict) -> str:
    """格式化基本面数据"""
    lines = [f"  【基本面数据】"]
    if data.get("pe") and data["pe"] != 0:
        lines.extend([
            f"    动态PE: {data['pe']:.2f}  静态PE: {data.get('pe_static', 0):.2f}",
            f"    市净率: {data.get('pb', 0):.2f}  TTM股息率: {data.get('dividend_yield', 0):.2f}%",
            f"    每股收益: {data.get('eps', 0):.4f}  每股净资产: {data.get('nav_per_share', 0):.2f}",
            f"    52周最高: {data.get('high_52w', 0):.2f}  52周最低: {data.get('low_52w', 0):.2f}",
            f"    振幅: {data.get('amplitude', 0):.2f}%  今年以来: {data.get('yoy_return', 0):.2f}%",
        ])
    lines.append(f"  数据源: xueqiu")
    return "\n".join(lines)

def format_minute_analysis(analysis: dict, name: str = "") -> str:
    """格式化分时分析输出"""
    if "error" in analysis:
        return f"分时分析错误: {analysis['error']}"
    lines = [
        f"",
        f"【分时量能分析】{name}",
        f"  全天成交: {analysis['total_volume']}手 ({analysis['total_amount']/10000:.1f}万元)",
        f"",
        f"  成交分布:",
        f"    早盘30分(9:30-10:00): {analysis['distribution']['open_30min']['volume']}手 ({analysis['distribution']['open_30min']['percent']}%)",
        f"    上午中段(10:00-11:30): {analysis['distribution']['mid_am']['volume']}手 ({analysis['distribution']['mid_am']['percent']}%)",
        f"    下午中段(13:00-14:30): {analysis['distribution']['mid_pm']['volume']}手 ({analysis['distribution']['mid_pm']['percent']}%)",
        f"    尾盘30分(14:30-15:00): {analysis['distribution']['close_30min']['volume']}手 ({analysis['distribution']['close_30min']['percent']}%)",
        f"",
        f"  放量时段 TOP 10:",
    ]
    for item in analysis["top_volumes"]:
        lines.append(f"    {item['time']} 价格:{item['price']:.2f} 成交:{item['volume']}手 金额:{item['amount']/10000:.1f}万")
    if analysis["signals"]:
        lines.extend(["", f"  【主力动向判断】"])
        for signal in analysis["signals"]:
            lines.append(f"    🔥 {signal}")
    return "\n".join(lines)

def format_history(records: List[Dict], name: str = "") -> str:
    """格式化历史K线"""
    if not records:
        return "无历史数据"
    lines = [f"", f"【历史K线】{name}", f"  最近{len(records)}个交易日:", f"  {'日期':<12} {'开盘':>8} {'收盘':>8} {'最高':>8} {'最低':>8} {'涨跌幅':>8} {'成交量':>10}"]
    for r in records:
        chg = r.get("change_pct", 0)
        cs = "+" if chg >= 0 else ""
        vol_str = f"{r.get('volume', 0)/10000:.0f}万" if r.get("volume", 0) > 10000 else f"{r.get('volume', 0)}股"
        lines.append(f"  {r['date']:<12} {r['open']:>8.2f} {r['close']:>8.2f} {r['high']:>8.2f} {r['low']:>8.2f} {cs}{chg:>7.2f}% {vol_str:>10}")
    return "\n".join(lines)

# ─────────────── 兼容接口 (portfolio.py) ───────────────

def analyze_stock(code: str, with_minute: bool = False) -> dict:
    """兼容 portfolio.py 的单只股票分析"""
    codes = [normalize_code(code)]
    efinance_data = fetch_realtime_efinance(codes)
    
    result = {"code": code}
    cn = normalize_code(code)
    if cn in efinance_data:
        realtime = efinance_data[cn]
        result["realtime"] = realtime
        result["name"] = realtime["name"]
    else:
        result["error"] = f"无法获取 {code} 的行情数据"
        return result
    
    if with_minute:
        minute_data = fetch_minute_data_sina(get_sina_symbol(cn))
        minute_analysis = analyze_minute_volume(minute_data)
        result["minute_analysis"] = minute_analysis
    
    result["updated_at"] = datetime.now().isoformat()
    
    # 因子引擎综合评分 (2026-05-04 文献优化) — 暂时禁用
    _factor_engine_enabled = False
    if _factor_engine_enabled:
        try:
            _engine = get_engine()
            factor_scores = {}
            if cn in efinance_data:
                rt = efinance_data[cn]
                price = float(rt.get("price", 0) or 0)
                change = float(rt.get("涨跌幅", 0) or 0)
                volume = float(rt.get("成交量", 0) or 0)
                turnover = float(rt.get("换手率", 0) or 0)
                pe = float(rt.get("市盈率", 0) or 0)
                
                # 技术因子
                factor_scores["均线趋势"] = min(100, max(0, 50 + change * 2))
                factor_scores["成交量异动"] = min(100, volume / 1e6 * 10)
                factor_scores["RSI超买超卖"] = max(0, 50 - change * 3)
                
                # 基本面
                factor_scores["PE分位数"] = max(0, 100 - pe * 2) if 0 < pe < 50 else 30
                factor_scores["换手率异常"] = min(100, turnover * 10)
                
                # 新增文献因子 (占位, 需真实数据源)
                factor_scores["机构调研密度"] = 65
                factor_scores["股东增减持链"] = 70
                factor_scores["业绩超预期概率"] = 55
                factor_scores["实控人变更影响"] = 80
                factor_scores["产业链位置变化"] = 60
            
            total, details = _engine.get_total_score(factor_scores)
            result["factor_score"] = round(total, 1)
            result["factor_count"] = len(factor_scores)
        except Exception:
            result["factor_score"] = 0
    
    return result


# ─────────────── 主逻辑 ───────────────

def main():
    parser = argparse.ArgumentParser(description="A股实时行情与分时量能分析 v2 (efinance主力)")
    parser.add_argument("codes", nargs="*", help="股票代码，如 600789 002446")
    parser.add_argument("--minute", "-m", action="store_true", help="包含分时量能分析")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--fundamental", "-f", action="store_true", help="含基本面数据")
    parser.add_argument("--history", "-H", type=str, help="查询历史K线（指定股票代码）")
    parser.add_argument("--days", "-d", type=int, default=20, help="历史K线天数（默认20）")
    
    args = parser.parse_args()
    
    # 纯历史K线模式
    if args.history:
        code = normalize_code(args.history)
        records = fetch_history(code, args.days)
        if args.json:
            print(json.dumps({"code": code, "history": records or []}, ensure_ascii=False, indent=2))
        else:
            print(format_history(records or [], code))
        return
    
    # 没有指定股票代码，显示帮助
    if not args.codes:
        parser.print_help()
        return
    
    # 归一化股票代码
    codes = [normalize_code(c) for c in args.codes]
    
    results = []
    
    # 1️⃣ 主力数据源: efinance
    efinance_data = fetch_realtime_efinance(codes)
    
    for code in codes:
        result = {"code": code}
        
        # 实时行情
        realtime = None
        if code in efinance_data:
            realtime = efinance_data[code]
            result["realtime"] = realtime
        else:
            result["error"] = f"无法获取 {code} 的行情数据"
        
        # 基本面（可选）
        if args.fundamental:
            fund = fetch_fundamental_akshare(code)
            if fund:
                result["fundamental"] = fund
        
        # 分时量能（可选）
        if args.minute and realtime:
            minute_data = fetch_minute_data_sina(get_sina_symbol(code))
            minute_analysis = analyze_minute_volume(minute_data)
            result["minute_analysis"] = minute_analysis
        
        results.append(result)
    
    # JSON输出
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        return
    
    # 文本输出
    for result in results:
        if "error" in result and "realtime" not in result:
            print(f"错误: {result['error']}")
            continue
        
        realtime = result.get("realtime", {})
        if realtime:
            print(format_realtime(realtime))
        
        if "fundamental" in result:
            print(format_fundamental(result["fundamental"]))
        
        if args.minute and "minute_analysis" in result:
            print(format_minute_analysis(result["minute_analysis"], realtime.get("name", "")))
        
        print()

if __name__ == "__main__":
    main()
