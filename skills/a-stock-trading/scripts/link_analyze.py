#!/usr/bin/env python3
"""
高胜算交易分析 — 马塞尔·林克方法 + 因子评分融合引擎

一个命令完成:
  1. 实时行情 (Sina)
  2. 多时间框架趋势分析 (日/周/月)
  3. 林克入场信号评分
  4. 止损建议
  5. 仓位建议
  6. 跟踪止损 (已有持仓)

使用:
    python3 link_analyze.py 603538                          # 单只股票
    python3 link_analyze.py 603538 000925 300342            # 多只股票
    python3 link_analyze.py 603538 --json                   # JSON输出
    python3 link_analyze.py 603538 --portfolio 100000       # 指定总资金算仓位
"""

import argparse
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional

# 导入本地模块
sys.path.insert(0, os.path.dirname(__file__))
from facecat_data import (
    fetch_kline, get_multiple_timeframes, judge_trend,
    fetch_realtime_sina
)
from entry_signals import check_entry_setup
from stop_loss_optimizer import (
    calc_technical_stop, calc_position_size, calc_trailing_stop
)


def analyze_stock(code: str, portfolio_value: float = 0,
                   entry_date: str = "") -> Dict:
    """全流程分析一只股票
    
    Args:
        code: 6位股票代码
        portfolio_value: 总资金 (0=不计算仓位)
        entry_date: 入场日期 (有持仓时)
    """
    code = code.zfill(6)

    # 1. 获取多时间框架数据
    tf_data = get_multiple_timeframes(code)
    if "error" in tf_data:
        return {"code": code, "error": tf_data["error"]}

    # 2. 趋势分析
    trend = judge_trend(tf_data.get("indicators", {}))

    # 3. 实时行情
    realtime = tf_data.get("realtime", {})

    # 4. 入场信号
    daily_data = tf_data.get("daily", [])
    indicators = tf_data.get("indicators", {})
    entry_signal = check_entry_setup(
        trend, indicators, daily_data,
        code=code, price=realtime.get("price", 0) if realtime else 0
    )

    # 5. 止损建议
    stop_info = calc_technical_stop(indicators, daily_data) if daily_data else {"error": "无K线"}

    # 6. 仓位建议
    position = {}
    if portfolio_value > 0 and "error" not in stop_info:
        position = calc_position_size(portfolio_value, stop_info,
                                       realtime.get("price") if realtime else None)

    # 7. 跟踪止损 (有入场日期)
    trail_stop = {}
    if entry_date and daily_data and realtime:
        trail_stop = calc_trailing_stop(daily_data, realtime.get("price", 0))

    # 8. 数据日期
    data_date = ""
    if realtime and realtime.get("trade_date"):
        data_date = realtime["trade_date"]

    return {
        "code": code,
        "name": realtime.get("name", ""),
        "price": realtime.get("price", 0),
        "change_pct": realtime.get("change_pct", 0),
        "data_date": data_date,
        "trend": trend,
        "entry_signal": entry_signal,
        "stop_loss": stop_info,
        "position": position,
        "trailing_stop": trail_stop,
        "updated_at": datetime.now().isoformat(),
    }


def format_analysis(result: Dict) -> str:
    """格式化输出分析结果 (人类可读)"""
    if "error" in result:
        return f"❌ {result['code']}: {result['error']}"

    lines = []
    lines.append("=" * 62)
    name = result.get("name", result["code"])
    r = result.get("realtime", {})
    price = result.get("price", 0)
    chg = result.get("change_pct", 0)
    chg_s = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
    data_date = result.get("data_date", "")
    date_info = f" (数据: {data_date})" if data_date else ""
    lines.append(f"{name} ({result['code']})  ¥{price:.2f}  {chg_s}{date_info}")
    lines.append("=" * 62)

    # 趋势
    trend = result.get("trend", {})
    t = trend.get("trend", "?")
    t_icon = "📈" if t == "up" else ("📉" if t == "down" else "➡️")
    lines.append(f"\n【趋势方向】{t_icon} {t.upper()}  (评分: {trend.get('score', 0)}/100)")
    for s in trend.get("signals", []):
        lines.append(f"  {s}")
    for tf, detail in trend.get("details", {}).items():
        lines.append(f"  {tf}: {detail['trend']} ({detail['score']}/100) | {detail.get('summary', '')}")

    # 入场信号
    signal = result.get("entry_signal", {})
    lines.append(f"\n【入场信号】{signal.get('summary', 'N/A')}")
    for rule_name, rule in signal.get("rules", {}).items():
        icon = "✅" if rule.get("pass") else "⬜"
        lines.append(f"  {icon} {rule_name}: {rule.get('detail', '')} ({rule.get('score', 0)}分)")

    # 入场区域
    zones = signal.get("entry_zones", {})
    if zones:
        lines.append(f"\n  入场参考: 现价¥{zones.get('current_price', 0):.2f}")
        if "primary" in zones:
            lines.append(f"    主要支撑: ¥{zones['primary']:.2f}")
        if "secondary" in zones:
            lines.append(f"    次级支撑: ¥{zones['secondary']:.2f}")

    # 止损
    stop = result.get("stop_loss", {})
    if "error" not in stop:
        lines.append(f"\n【止损建议】")
        lines.append(f"  核心止损: ¥{stop.get('core', 0):.2f} ({stop.get('risk_pct', 0):.1f}%)")
        lines.append(f"    方法: {stop.get('core_desc', '')}")
        lines.append(f"  ATR止损: ¥{stop.get('atr_stop', 0):.2f} (ATR={stop.get('atr_width', 0):.2f})")
        lines.append(f"  极值止损: ¥{stop.get('extreme', 0):.2f}")
        lines.append(f"  止损宽度: {stop.get('risk_pct', 0):.1f}%")

    # 仓位
    pos = result.get("position", {})
    if "error" not in pos and pos:
        lines.append(f"\n【仓位建议】")
        lines.append(f"  建议股数: {pos.get('recommended', 0)}")
        lines.append(f"  仓位占比: {pos.get('position_pct', 0):.1f}%")
        lines.append(f"  单笔风险: ¥{pos.get('risk_amount', 0):.0f} ({pos.get('risk_pct_text', '')})")
        lines.append(f"  止损价:   ¥{pos.get('stop_price', 0):.2f}")
        lines.append(f"  1%风险可买: {pos.get('risk_1pct', 0)}股")
        lines.append(f"  2%风险可买: {pos.get('risk_2pct', 0)}股")

    # 跟踪止损
    trail = result.get("trailing_stop", {})
    if trail and trail.get("trailing_active"):
        lines.append(f"\n【跟踪止损】✅ 已激活")
        lines.append(f"  跟踪止损价: ¥{trail.get('trail_stop', 0):.2f}")
        lines.append(f"  入场后最高: ¥{trail.get('highest_since_entry', 0):.2f}")
        lines.append(f"  当前盈利: {trail.get('profit_pct', 0):.1f}%")
        lines.append(f"  锁定盈利: {trail.get('locked_pct', 0):.1f}%")
    elif trail:
        lines.append(f"\n【跟踪止损】未激活 ({trail.get('status', '')})")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="高胜算交易分析 — 林克方法+因子融合")
    parser.add_argument("codes", nargs="+", help="股票代码")
    parser.add_argument("--json", "-j", action="store_true", help="JSON输出")
    parser.add_argument("--portfolio", "-p", type=float, default=0,
                        help="总资金(元), 用于计算仓位")
    parser.add_argument("--entry", "-e", type=str, default="",
                        help="入场日期 YYYY-MM-DD (有持仓时)")
    args = parser.parse_args()

    results = []
    for code in args.codes:
        result = analyze_stock(code, portfolio_value=args.portfolio,
                                entry_date=args.entry)
        results.append(result)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        for r in results:
            print(format_analysis(r))
            print()


if __name__ == "__main__":
    main()
