#!/usr/bin/env python3
"""
融资融券监控模块 v1 — 基于 akshare + 东方财富

数据源策略 (意大利可用):
  1. ak.stock_margin_detail_sse() — 上交所个股融资融券 ✅
  2. ak.stock_margin_sse() — 上交所市场总计 ✅
  3. 东方财富网页 — 深交所个股 (备用)
  4. 个股不在此名单中 = 非融资融券标的

用法:
    python3 margin_monitor.py              # 持仓股融资融券监控
    python3 margin_monitor.py --market     # 市场融资融券总览
    python3 margin_monitor.py 603538       # 指定股票
    python3 margin_monitor.py --json       # JSON输出
"""
import argparse
import json
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

PORTFOLIO = {
    "603538": "美诺华",
    "603959": "国晟科技(百利)",
    "300342": "天银机电",
    "000925": "众合科技",
    "300067": "安诺其",
    "600396": "华电辽能(金山)",
    "600593": "德龙汇能",
}

# ─────────────── 数据获取 ───────────────


def _date() -> str:
    return "20260430"  # 最近可用交易日，盘中高频调用避免重试


def fetch_sse_market_summary() -> dict:
    """上交所融资融券市场汇总"""
    try:
        import akshare as ak
        d = _date()
        df = ak.stock_margin_sse(start_date=d, end_date=d)
        latest = df.iloc[-1]
        return {
            "日期": str(latest.get("信用交易日期", "")),
            "融资余额(亿)": round(float(latest.get("融资余额", 0)) / 1e8, 2),
            "融资买入额(亿)": round(float(latest.get("融资买入额", 0)) / 1e8, 2),
            "融券余量(万股)": round(float(latest.get("融券余量", 0)) / 10000, 2),
            "融券余额(亿)": round(float(latest.get("融券余量金额", 0)) / 1e8, 2),
            "融券卖出量(万股)": round(float(latest.get("融券卖出量", 0)) / 10000, 2),
            "融资融券余额(亿)": round(float(latest.get("融资融券余额", 0)) / 1e8, 2),
        }
    except Exception as e:
        return {"error": f"上交所融资融券汇总失败: {e}"}


_SSE_DETAIL_CACHE = None

def _get_sse_detail():
    """获取上交所个股融资融券明细（缓存，一次请求供所有股票复用）"""
    global _SSE_DETAIL_CACHE
    if _SSE_DETAIL_CACHE is not None:
        return _SSE_DETAIL_CACHE
    import akshare as ak
    d = _date()
    df = ak.stock_margin_detail_sse(date=d)
    if df is not None and not df.empty:
        df["标的证券代码"] = df["标的证券代码"].astype(str)
        _SSE_DETAIL_CACHE = df
    return _SSE_DETAIL_CACHE


def fetch_sse_stock_margin(code: str) -> dict:
    """获取上交所个股融资融券数据"""
    try:
        df = _get_sse_detail()

        df["标的证券代码"] = df["标的证券代码"].astype(str)
        match = df[df["标的证券代码"] == code]
        if match.empty:
            return {"状态": "非融资融券标的", "code": code}

        row = match.iloc[0]
        return {
            "股票代码": str(row.get("标的证券代码", "")),
            "股票名称": str(row.get("标的证券简称", "")),
            "日期": str(row.get("信用交易日期", "")),
            "融资余额(万)": round(float(row.get("融资余额", 0)) / 10000, 2),
            "融资买入额(万)": round(float(row.get("融资买入额", 0)) / 10000, 2),
            "融资偿还额(万)": round(float(row.get("融资偿还额", 0)) / 10000, 2),
            "融券余量(股)": int(float(row.get("融券余量", 0))),
            "融券卖出量(股)": int(float(row.get("融券卖出量", 0))),
            "融券偿还量(股)": int(float(row.get("融券偿还量", 0))),
            "交易所": "上交所",
        }
    except Exception as e:
        return {"error": f"上交所个股融资融券失败: {e}", "code": code}


def fetch_szse_stock_margin_em(code: str) -> dict:
    """深交所个股融资融券 — 东方财富备用"""
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        url = f"https://data.eastmoney.com/rzrq/detail/{code}.html"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return {"状态": "东方财富不可达", "code": code}

        import re
        patterns = {
            "融资余额": r"融资余额[：:]\s*([\d,.]+)",
            "融资买入额": r"融资买入[额：:]\s*([\d,.]+)",
            "融券余量": r"融券余量[：:]\s*([\d,.]+)",
            "融券卖出量": r"融券卖出[量：:]\s*([\d,.]+)",
        }
        result = {"股票代码": code, "交易所": "深交所(东方财富)"}
        for key, pattern in patterns.items():
            m = re.search(pattern, resp.text)
            if m:
                result[key] = m.group(1)

        if len(result) > 2:
            return result
        return {"状态": "未在融资融券标的名单中", "code": code}
    except Exception as e:
        return {"状态": f"东方财富抓取失败: {e}", "code": code}


def get_stock_margin(code: str) -> dict:
    """综合获取个股融资融券"""
    if code.startswith("6"):
        return fetch_sse_stock_margin(code)
    else:
        result = fetch_szse_stock_margin_em(code)
        if result and "状态" not in result:
            return result
        return {"code": code, "状态": "深交所融资融券不可用"}


def batch_margin(codes: Optional[List[str]] = None) -> Dict[str, dict]:
    if codes is None:
        codes = list(PORTFOLIO.keys())
    return {code: get_stock_margin(code) for code in codes}


# ─────────────── 分析 ───────────────


def analyze_margin_change(data: dict) -> dict:
    """分析融资融券异动信号"""
    signals = []
    score = 0

    fin_buy = data.get("融资买入额(万)")
    if fin_buy and isinstance(fin_buy, (int, float)):
        if fin_buy > 5000:
            signals.append("🔥 **融资买入激增** (>¥5000万)")
            score += 30
        elif fin_buy > 2000:
            signals.append("⚡ 融资买入活跃 (>¥2000万)")
            score += 15
        elif fin_buy > 500:
            score += 5

    fin_bal = data.get("融资余额(万)")
    if fin_bal and isinstance(fin_bal, (int, float)):
        if fin_bal > 50000:
            signals.append("🏦 **融资余额高** (>¥5亿)")
            score += 10

    short_sell = data.get("融券卖出量(股)")
    if short_sell and isinstance(short_sell, (int, float)):
        if short_sell > 100000:
            signals.append("🐻 **融券卖出激增** (>10万股)")
            score -= 20
        elif short_sell > 50000:
            signals.append("🐻 融券卖出较多 (>5万股)")
            score -= 10

    return {"signals": signals, "score": score, "level": "warning" if score > 20 else "info"}


def market_summary_analysis(summary: dict) -> str:
    if "error" in summary:
        return f"⚠️ {summary['error']}"

    total = summary.get("融资融券余额(亿)", 0)
    fin_buy = summary.get("融资买入额(亿)", 0)
    short_val = summary.get("融券余额(亿)", 0)
    margin_ratio = round(short_val / total * 100, 2) if total else 0

    lines = [f"\n📊 **上交所融资融券总览** ({summary.get('日期', '?')})"]
    lines.append(f"  融资融券余额: ¥{total}亿")
    lines.append(f"  融资买入: ¥{fin_buy}亿")
    lines.append(f"  融券余额: ¥{short_val}亿 | 占比: {margin_ratio}%")

    if margin_ratio > 5:
        lines.append("  🐻 **做空活跃**: 融券占比 >5%")
    elif margin_ratio < 1:
        lines.append("  🐂 **做空低迷**: 融券占比 <1%")

    return "\n".join(lines)


# ─────────────── 主入口 ───────────────


def main():
    parser = argparse.ArgumentParser(description="融资融券监控")
    parser.add_argument("codes", nargs="*", help="股票代码")
    parser.add_argument("--market", "-m", action="store_true", help="市场总览")
    parser.add_argument("--json", "-j", action="store_true", help="JSON输出")

    args = parser.parse_args()

    if args.market:
        summary = fetch_sse_market_summary()
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(market_summary_analysis(summary))
        return

    codes = args.codes or list(PORTFOLIO.keys())
    results = batch_margin(codes)
    summary = fetch_sse_market_summary()

    if args.json:
        output = {"stocks": results, "market": summary}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    print(f"\n📡 **融资融券监控** — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    margin_count = 0
    for code, data in results.items():
        name = PORTFOLIO.get(code, code)
        if "error" in data:
            continue
        if "状态" in data:
            print(f"  {name}({code}): {data['状态']}")
            continue

        margin_count += 1
        print(f"\n📊 **{name} ({code})** — {data.get('交易所', '上交所')}")
        print(f"  融资余额: ¥{data['融资余额(万)']}万 | 买入: ¥{data['融资买入额(万)']}万")
        print(f"  融券余量: {data['融券余量(股)']:,}股 | 卖出: {data['融券卖出量(股)']:,}股")

        analysis = analyze_margin_change(data)
        for sig in analysis["signals"]:
            print(f"  {sig}")

    print(f"\n{'='*60}")
    print(f"  有融资融券数据的: {margin_count}/{len(PORTFOLIO)} 只持仓")
    print(market_summary_analysis(summary))


if __name__ == "__main__":
    main()
