#!/usr/bin/env python3
"""
quant_models.py — 量化核心模型：凯利公式 + GARCH + 马科维茨 + PCA
集成到现有交易系统
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ============================================================
# 1. 凯利公式 — 最优仓位管理
# ============================================================

def kelly_criterion(win_rate, avg_win, avg_loss):
    """
    标准凯利公式: f* = (bp - q) / b
    其中 b = avg_win / |avg_loss|, p = win_rate, q = 1-p
    """
    if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
        return 0
    b = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    q = 1 - win_rate
    f = (b * win_rate - q) / b if b > 0 else 0
    return max(0, min(f, 1))  # clamp 0~1

def half_kelly(win_rate, avg_win, avg_loss):
    """半凯利 — 更保守，推荐实战使用"""
    return kelly_criterion(win_rate, avg_win, avg_loss) / 2

def quarter_kelly(win_rate, avg_win, avg_loss):
    """1/4凯利 — 极保守"""
    return kelly_criterion(win_rate, avg_win, avg_loss) / 4

def kelly_with_stop(stock_price, stop_loss_pct, win_rate, avg_win_pct, avg_loss_pct):
    """
    带止损的凯利仓位计算
    stock_price: 当前股价
    stop_loss_pct: 每笔止损比例 (如 0.02 = 2%)
    win_rate: 历史胜率
    avg_win_pct: 平均盈利百分比
    avg_loss_pct: 平均亏损百分比
    返回: 应投入仓位比例 (0~1)
    """
    f = kelly_criterion(win_rate, avg_win_pct, avg_loss_pct)
    # 结合Marc Link的每笔风险1.5%原则
    max_risk_pct = min(stop_loss_pct, 0.015)  # 不超过1.5%
    # 限制仓位使最大亏损不超过 max_risk_pct
    max_pos = max_risk_pct / (avg_loss_pct * f) if f > 0 and avg_loss_pct > 0 else 1
    return min(f, max_pos)


# ============================================================
# 2. GARCH(1,1) 波动率预测
# ============================================================

def _garch_fit(returns, timeout=15):
    """GARCH拟合(带超时)"""
    import threading
    result = [None]
    exc = [None]
    
    def _run():
        try:
            from arch import arch_model
            am = arch_model(returns, vol='Garch', p=1, q=1, dist='normal')
            res = am.fit(disp='off', update_freq=0)
            result[0] = res
        except Exception as e:
            exc[0] = e
    
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        print("  [GARCH] 拟合超时, 回退历史波动率")
        return None
    if exc[0]:
        print(f"  [GARCH] 拟合失败: {exc[0]}, 回退历史波动率")
        return None
    return result[0]


def garch_predict_volatility(prices, forecast_days=1):
    """
    用 GARCH(1,1) 预测未来波动率
    回退到简单历史波动率
    prices: 历史价格列表/Series
    forecast_days: 预测天数
    返回: 年化波动率 (如 0.25 = 25%)
    """
    try:
        returns = np.diff(np.log(prices)) * 100  # 对数收益率(%)
        if len(returns) < 20:
            return _simple_historical_vol(prices)
        
        # 拟合 GARCH(1,1) (带超时)
        res = _garch_fit(returns, timeout=15)
        if res is None:
            return _simple_historical_vol(prices)
        
        # 预测
        forecasts = res.forecast(horizon=forecast_days)
        # 取预测方差
        var_forecast = float(forecasts.variance.values[-1][0])
        # 转换为年化波动率 (假设252交易日)
        daily_vol = np.sqrt(var_forecast / 10000)  # 还原到小数
        annual_vol = float(daily_vol * np.sqrt(252))
        return annual_vol
        
    except Exception as e:
        print(f"  [GARCH] 回退到历史波动率: {e}")
        return _simple_historical_vol(prices)

def _simple_historical_vol(prices):
    """简单历史波动率 (回退方法)"""
    returns = np.diff(np.log(prices))
    if len(returns) < 2:
        return 0.25
    daily_vol = float(np.std(returns))
    return float(daily_vol * np.sqrt(252))

def garch_vol_signal(annual_vol, portfolio_history_vol=None):
    """
    根据GARCH波动率产生交易信号
    annual_vol: GARCH预测的年化波动率
    portfolio_history_vol: 组合历史波动率 (用于对比)
    返回: (signal_str, multiplier)
    """
    if portfolio_history_vol is None:
        portfolio_history_vol = 0.25  # 默认A股均值约25%
    
    ratio = annual_vol / portfolio_history_vol
    
    if ratio < 0.5:
        return "🟢 低波动 — 可加仓", 1.5
    elif ratio < 0.8:
        return "🟢 偏低波动 — 正常操作", 1.2
    elif ratio < 1.2:
        return "🟡 正常波动 — 常规仓位", 1.0
    elif ratio < 1.5:
        return "🟠 偏高波动 — 减仓", 0.7
    elif ratio < 2.0:
        return "🔴 高波动 — 减仓!", 0.5
    else:
        return "⛔ 极高波动 — 观望!", 0.2


# ============================================================
# 3. 马科维茨均值-方差优化
# ============================================================

def markowitz_optimize(returns_df, risk_free_rate=0.02, short_allowed=False):
    """
    马科维茨均值-方差优化
    returns_df: DataFrame, 每列一个资产的日收益率, index为日期
    risk_free_rate: 无风险利率
    short_allowed: 是否允许做空
    返回: dict {ticker: weight, ...}
    """
    from scipy.optimize import minimize
    
    mean_returns = returns_df.mean() * 252  # 年化收益率
    cov_matrix = returns_df.cov() * 252     # 年化协方差矩阵
    
    num_assets = len(returns_df.columns)
    args = (mean_returns, cov_matrix, risk_free_rate)
    
    def neg_sharpe(weights, mean_returns, cov_matrix, risk_free_rate):
        port_ret = np.sum(mean_returns * weights)
        port_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return -(port_ret - risk_free_rate) / port_std
    
    def port_variance(weights, mean_returns, cov_matrix, risk_free_rate):
        return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    
    def check_sum(weights):
        return np.sum(weights) - 1
    
    # 约束: 满仓
    constraints = ({'type': 'eq', 'fun': check_sum})
    
    # 边界
    if short_allowed:
        bounds = tuple((-1, 1) for _ in range(num_assets))
    else:
        bounds = tuple((0, 1) for _ in range(num_assets))
    
    # 初始等权
    init_guess = [1.0/num_assets] * num_assets
    
    # 1. 最大夏普比率组合
    opt_sharpe = minimize(neg_sharpe, init_guess, args=args,
                          method='SLSQP', bounds=bounds, constraints=constraints)
    
    # 2. 最小方差组合
    opt_minvar = minimize(port_variance, init_guess, args=args,
                          method='SLSQP', bounds=bounds, constraints=constraints)
    
    weights_sharpe = opt_sharpe.x if opt_sharpe.success else init_guess
    weights_minvar = opt_minvar.x if opt_minvar.success else init_guess
    
    result = {}
    for i, col in enumerate(returns_df.columns):
        result[col] = {
            'current_weight': None,
            'max_sharpe': round(weights_sharpe[i], 4),
            'min_variance': round(weights_minvar[i], 4),
        }
    
    # 计算夏普组合的年化收益、波动
    def calc_metrics(weights):
        port_ret = np.sum(mean_returns * weights)
        port_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = (port_ret - risk_free_rate) / port_std if port_std > 0 else 0
        return port_ret, port_std, sharpe
    
    r_sharpe, s_sharpe, sr_sharpe = calc_metrics(weights_sharpe)
    r_minvar, s_minvar, sr_minvar = calc_metrics(weights_minvar)
    
    return {
        'weights': result,
        'max_sharpe': {'return': round(r_sharpe, 4), 'std': round(s_sharpe, 4), 'sharpe': round(sr_sharpe, 3)},
        'min_variance': {'return': round(r_minvar, 4), 'std': round(s_minvar, 4), 'sharpe': round(sr_minvar, 3)},
    }

def markowitz_compare(portfolio_dict, prices_df):
    """
    对比当前等权 vs 马科维茨最优权重
    portfolio_dict: {code: shares, ...}
    prices_df: DataFrame, {code: [price_series]}
    返回: 对比报告文本
    """
    returns_df = prices_df.pct_change().dropna()
    result = markowitz_optimize(returns_df)
    
    # 计算当前实际权重
    latest_prices = prices_df.iloc[-1]
    total_value = sum(latest_prices[code] * shares for code, shares in portfolio_dict.items()
                      if code in latest_prices.index)
    
    lines = ["═══ 马科维茨仓位优化 ═══",
             f"(基于 {len(returns_df)} 个交易日数据)\n"]
    
    lines.append(f"{'股票':<12} {'当前权重':<10} {'夏普最优':<10} {'方差最优':<10}")
    lines.append("-" * 42)
    
    for code, info in result['weights'].items():
        name = code  # 代码
        current_w = 0
        if code in portfolio_dict and code in latest_prices.index:
            current_w = latest_prices[code] * portfolio_dict[code] / total_value if total_value > 0 else 0
        
        lines.append(f"{code:<12} {current_w:<8.1%}  {info['max_sharpe']:<8.1%}  {info['min_variance']:<8.1%}")
    
    lines.append("")
    m = result['max_sharpe']
    v = result['min_variance']
    lines.append(f"📊 最大夏普: 年化 {m['return']:.1%}, 波动 {m['std']:.1%}, Sharpe {m['sharpe']}")
    lines.append(f"📊 最小方差: 年化 {v['return']:.1%}, 波动 {v['std']:.1%}, Sharpe {v['sharpe']}")
    
    return "\n".join(lines)


# ============================================================
# 4. PCA 因子正交化
# ============================================================

def pca_factor_orthogonalize(factor_df, n_components=None, explain_threshold=0.85):
    """
    PCA因子正交化
    factor_df: DataFrame, 每列一个因子, index为日期
    n_components: 保留主成分数 (auto=None, 按explain_threshold自动选)
    explain_threshold: 累计解释方差阈值
    返回: (ortho_df, pca_model, explained_ratio)
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    
    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(factor_df.fillna(factor_df.mean()))
    
    # 自动选择主成分数
    if n_components is None:
        pca_temp = PCA().fit(X_scaled)
        cumsum = np.cumsum(pca_temp.explained_variance_ratio_)
        n_components = int(np.searchsorted(cumsum, explain_threshold) + 1)
        n_components = min(n_components, X_scaled.shape[1])
    
    pca = PCA(n_components=n_components)
    X_ortho = pca.fit_transform(X_scaled)
    
    # 构建正交因子DataFrame
    ortho_cols = [f"PC{i+1}" for i in range(n_components)]
    ortho_df = pd.DataFrame(X_ortho, index=factor_df.index, columns=ortho_cols)
    
    # 计算因子负荷
    loadings = pd.DataFrame(
        pca.components_.T,
        index=factor_df.columns,
        columns=ortho_cols
    )
    
    return ortho_df, pca, loadings, pca.explained_variance_ratio_

def pca_factor_report(factor_df):
    """
    PCA因子报告
    factor_df: 原始因子数据
    返回: 报告文本
    """
    ortho_df, pca, loadings, ev_ratio = pca_factor_orthogonalize(factor_df)
    
    n_factors = factor_df.shape[1]
    n_pc = ortho_df.shape[1]
    
    lines = ["═══ PCA因子正交化报告 ═══",
             f"{n_factors}个原始因子 → {n_pc}个正交主成分",
             f"累计解释方差: {sum(ev_ratio):.1%}\n"]
    
    for i, (col, ratio) in enumerate(zip(ortho_df.columns, ev_ratio)):
        # 各主成分的主要贡献因子
        top_loadings = loadings[col].abs().sort_values(ascending=False).head(3)
        top_names = [f"{idx}({loadings.loc[idx,col]:.3f})" for idx in top_loadings.index]
        lines.append(f"  {col}: {ratio:.1%} — {' + '.join(top_names)}")
    
    return "\n".join(lines)


# ============================================================
# 5. 集成报告
# ============================================================

def full_model_report(portfolio_shares, prices_df, factor_df=None,
                      win_rate=0.55, avg_win_pct=0.03, avg_loss_pct=0.02):
    """
    全模型集成报告
    portfolio_shares: {code: shares}
    prices_df: 价格历史
    factor_df: 因子数据 (可选)
    win_rate, avg_win_pct, avg_loss_pct: 凯利公式参数
    """
    lines = []
    
    # --- 凯利公式 ---
    lines.append("═══ 凯利仓位管理 ═══")
    kelly = kelly_criterion(win_rate, avg_win_pct, avg_loss_pct)
    half = half_kelly(win_rate, avg_win_pct, avg_loss_pct)
    quarter = quarter_kelly(win_rate, avg_win_pct, avg_loss_pct)
    
    lines.append(f"  胜率 {win_rate:.0%}, 平均盈 {avg_win_pct:.1%}, 平均亏 {avg_loss_pct:.1%}")
    lines.append(f"  全凯利: {kelly:.1%} | 半凯利: {half:.1%} | ¼凯利: {quarter:.1%}")
    lines.append(f"  💡 建议: 初始用 '半凯利' {half:.1%} 仓位")
    
    # 结合止损
    if prices_df is not None and len(prices_df.columns) > 0:
        latest_price = prices_df.iloc[-1].mean()  # 平均股价作为参考
        with_stop = kelly_with_stop(latest_price, 0.015, win_rate, avg_win_pct, avg_loss_pct)
        lines.append(f"  止损限制后: {with_stop:.1%}")
    
    lines.append("")
    
    # --- GARCH波动率 ---
    lines.append("═══ GARCH(1,1) 波动率 ═══")
    if prices_df is not None and len(prices_df) > 30:
        for col in prices_df.columns:
            prices = prices_df[col].dropna().values
            if len(prices) > 30:
                vol = garch_predict_volatility(prices)
                sig, mult = garch_vol_signal(vol)
                lines.append(f"  {col}: 年化波动 {vol:.1%} → {sig}")
    lines.append("")
    
    # --- 马科维茨 ---
    if prices_df is not None and len(prices_df.columns) > 1:
        lines.append(markowitz_compare(portfolio_shares, prices_df))
    lines.append("")
    
    # --- PCA ---
    if factor_df is not None and factor_df.shape[1] > 1:
        lines.append(pca_factor_report(factor_df))
    
    return "\n".join(lines)


# ============================================================
# CLI入口
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="量化核心模型")
    parser.add_argument("--kelly", action="store_true", help="凯利公式演示")
    parser.add_argument("--garch", type=str, help="GARCH波动率: stock_code")
    parser.add_argument("--markowitz", action="store_true", help="马科维茨优化")
    parser.add_argument("--pca", action="store_true", help="PCA因子正交化")
    parser.add_argument("--all", action="store_true", help="完整报告")
    
    args = parser.parse_args()
    
    if args.kelly or args.all:
        print("═══ 凯利公式仓位管理 ═══")
        scenarios = [
            ("稳健策略", 0.55, 0.03, 0.02),
            ("激进策略", 0.50, 0.05, 0.02),
            ("保守策略", 0.60, 0.02, 0.01),
            ("高频策略", 0.45, 0.01, 0.008),
        ]
        print(f"{'策略':<10} {'胜率':<8} {'均盈':<8} {'均亏':<8} {'全凯利':<10} {'半凯利':<10}")
        print("-" * 54)
        for name, wr, aw, al in scenarios:
            k = kelly_criterion(wr, aw, al)
            h = half_kelly(wr, aw, al)
            print(f"{name:<10} {wr:<7.0%} {aw:<7.1%} {al:<7.1%} {k:<9.1%} {h:<9.1%}")
        print()

    if args.garch:
        print(f"═══ GARCH(1,1) 波动率: {args.garch} ═══")
        try:
            import urllib.request
            from urllib.request import urlopen, Request
            
            prefix = 'sh' if args.garch.startswith('6') else 'sz'
            url = f'https://hq.sinajs.cn/list={prefix}{args.garch}'
            req = Request(url, headers={'Referer': 'https://finance.sina.com.cn'})
            resp = urlopen(req, timeout=5)
            raw = resp.read().decode('gbk')
            
            import re
            match = re.search(r'\"(.+?)\"', raw)
            if match:
                fields = match.group(1).split(',')
                name = fields[0]
                print(f"  股票: {name}({args.garch})")
            
            # Also use FaceCat or efinance for kline data
            from scripts.market_monitor import fetch_kline
            klines = fetch_kline(args.garch)
            if klines is not None and len(klines) > 30:
                prices = klines.close.values
                vol = garch_predict_volatility(prices)
                sig, mult = garch_vol_signal(vol)
                print(f"  年化波动: {vol:.1%}")
                print(f"  信号: {sig}")
                print(f"  仓位乘数: {mult}")
            else:
                print("  ⚠️ K线数据不足 (<30天)")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        print()

    if args.markowitz or args.all:
        print("═══ 马科维茨组合优化 ═══")
        try:
            # 用最近的portfolio和价格数据
            from scripts.market_monitor import PORTFOLIO
            from scripts.market_monitor import fetch_kline
            prices_dict = {}
            for code, name in PORTFOLIO.items():
                klines = fetch_kline(code)
                if klines is not None and len(klines) > 20:
                    prices_dict[code] = klines.close.values[:60]
            
            if len(prices_dict) >= 2:
                # 对齐长度
                min_len = min(len(v) for v in prices_dict.values())
                aligned = {k: v[-min_len:] for k, v in prices_dict.items()}
                prices_df = pd.DataFrame(aligned)
                
                # 简单等权
                shares = {code: 1000 for code in PORTFOLIO.keys()}
                result = markowitz_compare(shares, prices_df)
                print(result)
            else:
                print("  ⚠️ 数据不足，无法优化")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        print()
    
    if args.pca:
        print("═══ PCA因子正交化 ═══")
        # 模拟因子数据
        np.random.seed(42)
        dates = pd.date_range('2026-01-01', '2026-05-06', freq='B')
        n = len(dates)
        # 模拟17个因子
        factor_names = ['量价背离', 'VWAP偏离', 'ATR波动率', '布林带', 'RSI', 'KDJ',
                       '换手率', '量比', '资金流向', '融资买入', '融券余额',
                       '市场情绪', '板块强度', '趋势强度', '动量因子', '反转因子', '波动因子']
        # 生成相关因子
        base = np.random.randn(n)
        data = {}
        for i, name in enumerate(factor_names):
            data[name] = base * (0.3 + 0.1 * (i % 3)) + np.random.randn(n) * 0.5
        
        factor_df = pd.DataFrame(data, index=dates)
        print(pca_factor_report(factor_df))
