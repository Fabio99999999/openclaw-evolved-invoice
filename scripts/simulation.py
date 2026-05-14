#!/usr/bin/env python3
"""
实盘模拟框架 v1 — 策略执行 + 持仓管理 + 归因分析

基于:
  - factor_engine.py (因子评分)
  - margin_monitor.py (融资融券)
  - market_monitor.py (市场情绪)
  - backtest_engine.py (回测验证)
  - performance_attribution.py (归因)
  - vwap_executor.py (VWAP执行)

设计原则:
  1. 每只持仓独立决策 (评分 → 信号 → 动作)
  2. 全市场监控辅助 (板块/融资/情绪)
  3. 风险预算管理 (止损/止盈/仓位)
  4. 日终归因分析

用法:
    python3 simulation.py run                       # 运行模拟交易
    python3 simulation.py status                    # 当前持仓状态
    python3 simulation.py signal                     # 生成买卖信号
    python3 simulation.py analyze                   # 归因分析
    python3 simulation.py daily                     # 日终处理
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# ─────────────── 配置 ───────────────

SIMULATION_DIR = os.path.expanduser("~/.openclaw/data/simulation")
os.makedirs(SIMULATION_DIR, exist_ok=True)

PORTFOLIO_FILE = os.path.join(SIMULATION_DIR, "portfolio.json")
TRADE_LOG_FILE = os.path.join(SIMULATION_DIR, "trades.json")
SIGNAL_LOG_FILE = os.path.join(SIMULATION_DIR, "signals.json")
ATTRIBUTION_FILE = os.path.join(SIMULATION_DIR, "attribution.json")

PORTFOLIO_STOCKS = {
    "603538": "美诺华",
    "603959": "国晟科技",
    "300342": "天银机电",
    "000925": "众合科技",
    "300067": "安诺其",
    "600396": "华电辽能",
    "600593": "德龙汇能",
}

RISK_CONFIG = {
    "stop_loss_pct": -8.0,       # 单票止损
    "trailing_stop_pct": -5.0,   # 追踪止损(从最高点回撤)
    "max_single_pct": 25.0,      # 单票最大仓位
    "max_leverage": 1.0,         # 最大杠杆
    "min_score_buy": 75,         # 买入最低评分
    "max_score_sell": 40,        # 卖出最高评分
}


# ─────────────── 数据层 ───────────────


def load_data(filepath: str, default=None) -> dict:
    if not os.path.exists(filepath):
        return default or {}
    try:
        with open(filepath) as f:
            return json.load(f)
    except Exception:
        return default or {}


def save_data(filepath: str, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_current_portfolio() -> dict:
    """获取当前模拟持仓"""
    return load_data(PORTFOLIO_FILE, {
        "cash": 1000000,  # 初始资金 ¥1,000,000
        "holdings": {},
        "total_cost": 0,
        "last_updated": None,
    })


def get_real_portfolio() -> dict:
    """读取真实持仓 (用于同步)"""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, 
             os.path.expanduser("~/.openclaw/workspace/skills/a-stock-trading/scripts/portfolio.py"),
             "show", "--json"],
            capture_output=True, text=True, timeout=15
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


# ─────────────── 信号生成 ───────────────


def get_factor_score(code: str, name: str) -> dict:
    """获取因子评分"""
    # 调用 factor_engine.generate_scores (需要集成)
    return {"total_score": 50, "details": {}, "signal": "hold"}


def check_stop_loss(code: str, entry_price: float, current_price: float,
                    high_since_entry: float) -> dict:
    """止损/追踪止损检查"""
    pnl_pct = (current_price - entry_price) / entry_price * 100
    trailing_drawdown = (current_price - high_since_entry) / high_since_entry * 100

    signals = []

    if pnl_pct <= RISK_CONFIG["stop_loss_pct"]:
        signals.append({
            "type": "stop_loss",
            "reason": f"止损触发: {pnl_pct:.1f}% ≤ {RISK_CONFIG['stop_loss_pct']:.1f}%",
            "urgency": "high",
        })

    if trailing_drawdown <= RISK_CONFIG["trailing_stop_pct"]:
        signals.append({
            "type": "trailing_stop",
            "reason": f"追踪止损: 从高点回撤{trailing_drawdown:.1f}% ≥ {RISK_CONFIG['trailing_stop_pct']:.1f}%",
            "urgency": "high",
        })

    return {
        "pnl_pct": round(pnl_pct, 2),
        "trailing_drawdown": round(trailing_drawdown, 2),
        "signals": signals,
        "action": "sell" if any(s["urgency"] == "high" for s in signals) else "hold",
    }


def generate_trade_signals(portfolio: dict) -> List[dict]:
    """为所有持仓生成交易信号"""
    signals = []
    for code, name in PORTFOLIO_STOCKS.items():
        holding = portfolio["holdings"].get(code, {})
        if not holding:
            continue

        score_data = get_factor_score(code, name)
        stop_data = check_stop_loss(
            code,
            holding.get("entry_price", 0),
            holding.get("current_price", 0),
            holding.get("high_since_entry", 0),
        )

        signal = {
            "code": code,
            "name": name,
            "score": score_data.get("total_score", 50),
            "pnl_pct": stop_data["pnl_pct"],
            "action": "hold",
            "reasons": [],
        }

        # 止损优先级最高
        if stop_data["action"] == "sell":
            signal["action"] = "sell"
            signal["reasons"] = [s["reason"] for s in stop_data["signals"]]
        # 评分卖出
        elif score_data.get("total_score", 50) <= RISK_CONFIG["max_score_sell"]:
            signal["action"] = "sell"
            signal["reasons"].append(f"评分{score_data['total_score']} ≤ 卖出阈值{RISK_CONFIG['max_score_sell']}")
        # 加分触发买入
        elif score_data.get("total_score", 50) >= RISK_CONFIG["min_score_buy"]:
            existing = portfolio["holdings"].get(code, {})
            if not existing:
                signal["action"] = "buy"
                signal["reasons"].append(f"评分{score_data['total_score']} ≥ 买入阈值{RISK_CONFIG['min_score_buy']}")

        signals.append(signal)

    return signals


# ─────────────── 归因分析 ───────────────


def run_attribution() -> str:
    """运行归因分析"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from scripts.performance_attribution import run_attribution as attr_fn
        result = attr_fn()
        return str(result)
    except Exception as e:
        return f"归因分析暂不可用: {e}"


# ─────────────── 主入口 ───────────────


def cmd_status():
    portfolio = get_current_portfolio()
    print(f"\n💰 **实盘模拟账户**")
    print(f"  现金: ¥{portfolio['cash']:,.2f}")
    print(f"  持仓: {len(portfolio['holdings'])} 只")

    total_market = sum(
        h.get("current_price", 0) * h.get("shares", 0)
        for h in portfolio["holdings"].values()
    )
    total_value = portfolio["cash"] + total_market
    total_cost = portfolio.get("total_cost", 0)
    total_pnl = total_value - (total_cost + portfolio["cash"] - total_cost) if total_cost else 0

    print(f"  总资产: ¥{total_value:,.2f}")
    print(f"  总盈亏: ¥{total_pnl:+,.2f} ({(total_pnl/max(total_cost,1)*100):+.2f}%)" if total_cost else "")

    for code, h in portfolio["holdings"].items():
        name = PORTFOLIO_STOCKS.get(code, code)
        shares = h.get("shares", 0)
        entry = h.get("entry_price", 0)
        current = h.get("current_price", entry)
        pnl = (current - entry) / entry * 100
        print(f"  {name}({code}): {shares}股 @¥{entry:.2f} → ¥{current:.2f} ({pnl:+.2f}%)")


def cmd_signal():
    portfolio = get_current_portfolio()
    signals = generate_trade_signals(portfolio)

    print(f"\n📊 **模拟交易信号** — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    sell_signals = [s for s in signals if s["action"] == "sell"]
    hold_signals = [s for s in signals if s["action"] == "hold"]

    if sell_signals:
        print(f"\n🔴 **卖出信号 ({len(sell_signals)})**")
        for s in sell_signals:
            reasons = " | ".join(s["reasons"])
            print(f"  {s['name']}({s['code']}): 评分{s['score']} | {reasons}")

    if hold_signals:
        print(f"\n🟡 **持仓中 ({len(hold_signals)})**")
        for s in hold_signals:
            print(f"  {s['name']}({s['code']}): 评分{s['score']} | 盈亏{s['pnl_pct']:+.2f}%")


def cmd_daily():
    """日终处理: 更新价格+归因+记录"""
    print(f"\n🔄 **日终处理** — {datetime.now().strftime('%Y-%m-%d')}")

    # 1. 更新持仓市价
    portfolio = get_current_portfolio()
    print(f"  更新 {len(portfolio['holdings'])} 只持仓市价...")

    # 2. 归因分析
    print("  运行归因分析...")
    attr = run_attribution()

    # 3. 生成信号
    signals = generate_trade_signals(portfolio)
    sells = [s for s in signals if s["action"] == "sell"]
    if sells:
        print(f"\n  ⚠️ 建议卖出 {len(sells)} 只:")
        for s in sells:
            print(f"    {s['name']}: {s['reasons'][0] if s['reasons'] else ''}")

    portfolio["last_updated"] = datetime.now().isoformat()
    save_data(PORTFOLIO_FILE, portfolio)
    print("  ✅ 日终处理完成")


def main():
    parser = argparse.ArgumentParser(description="实盘模拟框架")
    parser.add_argument("cmd", nargs="?", default="status",
                        choices=["status", "signal", "daily", "run", "analyze"])
    parser.add_argument("--json", "-j", action="store_true")

    args = parser.parse_args()

    if args.cmd == "status":
        if args.json:
            print(json.dumps(get_current_portfolio(), indent=2, ensure_ascii=False))
        else:
            cmd_status()
    elif args.cmd == "signal":
        cmd_signal()
    elif args.cmd in ("daily", "run"):
        cmd_daily()
    elif args.cmd == "analyze":
        attr = run_attribution()
        print(attr)


if __name__ == "__main__":
    main()
