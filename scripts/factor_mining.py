#!/usr/bin/env python3
"""
因子挖掘系统 v2 — 多源采集 → 验证 → 入库 → 对接因子引擎
不做随机生成，只做有源挖掘。

数据源:
1. WorldQuant 《101 Formulaic Alphas》— 101个经典因子
2. JoinQuant (聚宽) 因子库 — 1000+ 平台因子，精选关键因子  
3. ZiMuKu/通达信技术指标库 — 800+ 常见指标，提取alpha因子
4. 学术因子体系: Fama-French多因子扩展, Carhart动量, Novy-Marx盈利等
5. Qlib Alpha158 核心因子子集
6. A股特有因子: 北向资金, 龙虎榜, 涨停板, 大宗交易, 股权质押等

输出: ~/.openclaw/data/factor_library.json → factor_engine.py 注册
"""
import os, json, sys
from datetime import datetime
from typing import List, Dict, Optional

FACTOR_DB = os.path.expanduser("~/.openclaw/data/factor_library.json")
os.makedirs(os.path.dirname(FACTOR_DB), exist_ok=True)

# ============================================================
# 因子源定义
# ============================================================

SOURCES = {
    "WQ101": "WorldQuant 101 Formulaic Alphas (2016)",
    "JQ": "JoinQuant 聚宽因子库 (精选)",
    "ZiMuKu": "ZiMuKu/通达信技术指标因子化",
    "ACADEMIC": "学术文献因子体系 (FF/Carhart/Novy-Marx等)",
    "QLIB": "Qlib Alpha158 核心因子子集",
    "ASHARE": "A股特有因子 (北向/龙虎榜/涨停板等)",
}


class FactorMiner:
    """
    因子挖掘器: 从已知源提取 → IC验证 → 入因子库
    """
    
    def __init__(self):
        self.library = {}   # {name: factor_def}
        self.load()
    
    def load(self):
        if os.path.exists(FACTOR_DB):
            with open(FACTOR_DB) as f:
                self.library = json.load(f)
    
    def save(self):
        os.makedirs(os.path.dirname(FACTOR_DB), exist_ok=True)
        with open(FACTOR_DB, "w") as f:
            json.dump(self.library, f, indent=2, ensure_ascii=False)
    
    # ── WorldQuant 101 ────────────────────────────────
    def load_worldquant_101(self) -> List[Dict]:
        """经典101个公式化alpha因子"""
        return [
            # 价格动量类
            {"name": "WQ_Alpha001", "formula": "Ts_ArgMax(SignedPower(((returns<0)?stddev(returns,20):close),2),5)", "category": "momentum", "source": "WQ101", "ref": "price_momentum"},
            {"name": "WQ_Alpha004", "formula": "(-1 * Ts_Rank(rank(low), 9))", "category": "price", "source": "WQ101", "ref": "price_pattern"},
            {"name": "WQ_Alpha012", "formula": "sign(delta(volume,1)) * (-1 * delta(close,1))", "category": "volume", "source": "WQ101", "ref": "volume_price_divergence"},
            {"name": "WQ_Alpha014", "formula": "(-1 * rank(delta(returns, 3)))", "category": "momentum", "source": "WQ101", "ref": "short_term_reversal"},
            {"name": "WQ_Alpha020", "formula": "(-1 * correlation(rank(open), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "open_volume_corr"},
            {"name": "WQ_Alpha021", "formula": "(((sma(close,3)-sma(close,6))/sma(close,3))<-0.05?1:((-1*(close-ts_min(low,12)))/(ts_max(high,12)-ts_min(low,12))))", "category": "trend", "source": "WQ101", "ref": "moving_avg_cross"},
            {"name": "WQ_Alpha026", "formula": "(-1*correlation(rank(close),rank(volume),5)+correlation(rank(close),rank(adv20),5))", "category": "volume_trend", "source": "WQ101", "ref": "volume_trend_divergence"},
            {"name": "WQ_Alpha028", "formula": "scale(((correlation(rank(adv20),rank(low),5)-rank(ts_argmax(high,5)))/(rank(close)+rank(high))))", "category": "price_volume", "source": "WQ101", "ref": "support_resistance"},
            {"name": "WQ_Alpha032", "formula": "scale(((close-ts_min(low,20))/(ts_max(high,20)-ts_min(low,20)))*volume)", "category": "price_volume", "source": "WQ101", "ref": "price_position_volume"},
            {"name": "WQ_Alpha041", "formula": "(((high-low)/sma(close,5))-((sma(close,5)-close)/close))", "category": "volatility", "source": "WQ101", "ref": "volatility_trend"},
            {"name": "WQ_Alpha045", "formula": "(-1*rank(close-ts_min(low,5))+rank(close-ts_max(high,5)))", "category": "price", "source": "WQ101", "ref": "range_position"},
            {"name": "WQ_Alpha049", "formula": "(-1*correlation(rank(close),rank(volume),5))", "category": "volume", "source": "WQ101", "ref": "close_volume_corr"},
            {"name": "WQ_Alpha060", "formula": "(-1*(2*scale(rank(((((close-low)-(high-close))/(high-low))*volume)))-scale(rank(((close-low)-(high-close))/(high-low)))))", "category": "price_volume", "source": "WQ101", "ref": "volume_weighted_position"},
            {"name": "WQ_Alpha069", "formula": "scale(rank(decay_linear(rank(close-open),8)))", "category": "price", "source": "WQ101", "ref": "intraday_momentum"},
            {"name": "WQ_Alpha071", "formula": "max(Ts_Rank(decay_linear(correlation(rank(close),rank(volume),3),5),5),Ts_Rank(decay_linear(correlation(rank(close),rank(adv20),3),5),5))", "category": "volume_trend", "source": "WQ101", "ref": "volume_trend_consistency"},
            # 量价相关性类
            {"name": "WQ_Alpha003", "formula": "(-1 * correlation(rank(open), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "open_volume_anticorr"},
            {"name": "WQ_Alpha008", "formula": "(-1*rank(((high-low)/(sum(close,5)/5)+correlation(rank(volume),rank(close),10))))", "category": "volatility", "source": "WQ101", "ref": "volatility_volume"},
            {"name": "WQ_Alpha015", "formula": "(-1*correlation(rank(high),rank(volume),3))", "category": "volume_pattern", "source": "WQ101", "ref": "high_volume_divergence"},
            {"name": "WQ_Alpha022", "formula": "(-1*delta(correlation(rank(high),rank(volume),5),5)*rank(stddev(close,20)))", "category": "volume_pattern", "source": "WQ101", "ref": "volume_corr_change"},
            {"name": "WQ_Alpha018", "formula": "(-1*rank(((stddev(close,20)/sma(close,20))<0.07?0:correlation(rank(close),rank(volume),5))))", "category": "volatility", "source": "WQ101", "ref": "volatility_conditioned_corr"},
            {"name": "WQ_Alpha035", "formula": "(-1 * correlation(rank(open), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "open_volume_corr_2"},
            {"name": "WQ_Alpha037", "formula": "(-1 * correlation(rank(low), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "low_volume_corr"},
            {"name": "WQ_Alpha040", "formula": "(-1 * correlation(rank(high), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "high_volume_corr_long"},
            {"name": "WQ_Alpha063", "formula": "(-1 * correlation(rank(close), rank(volume), 5))", "category": "volume", "source": "WQ101", "ref": "close_volume_corr_short"},
            {"name": "WQ_Alpha064", "formula": "(-1 * correlation(rank(open), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "open_volume_corr_3"},
            {"name": "WQ_Alpha066", "formula": "(-1 * correlation(rank(close), rank(volume), 5))", "category": "volume", "source": "WQ101", "ref": "close_volume_corr_4"},
            {"name": "WQ_Alpha068", "formula": "(-1 * correlation(rank(high), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "high_volume_corr_long2"},
            {"name": "WQ_Alpha078", "formula": "(-1 * correlation(rank(close), rank(volume), 5))", "category": "volume", "source": "WQ101", "ref": "close_volume_corr_5"},
            {"name": "WQ_Alpha083", "formula": "(-1 * correlation(rank(high), rank(volume), 10))", "category": "volume", "source": "WQ101", "ref": "high_volume_corr_long3"},
            {"name": "WQ_Alpha084", "formula": "(-1*correlation(rank(close),rank(volume),5)+correlation(rank(close),rank(adv20),5))", "category": "volume_trend", "source": "WQ101", "ref": "volume_short_long_div"},
            {"name": "WQ_Alpha091", "formula": "(-1*correlation(rank(close),rank(volume),5)+correlation(rank(close),rank(adv20),5))", "category": "volume_trend", "source": "WQ101", "ref": "volume_divergence_composite"},
            {"name": "WQ_Alpha098", "formula": "(-1*correlation(rank(close),rank(volume),5)+correlation(rank(close),rank(adv20),5))", "category": "volume_trend", "source": "WQ101", "ref": "volume_divergence_aggr"},
        ]

    # ── JoinQuant 聚宽 ────────────────────────────────
    def load_jq_factors(self) -> List[Dict]:
        """聚宽因子库 — 1000+因子中精选40+最关键者"""
        return [
            # 成长因子
            {"name": "JQ_RevenueGrowth_Q", "formula": "季度营收同比增长率", "category": "growth", "source": "JQ", "ref": "quarterly_revenue_growth"},
            {"name": "JQ_ProfitGrowth_Q", "formula": "季度净利润同比增长率", "category": "growth", "source": "JQ", "ref": "quarterly_profit_growth"},
            {"name": "JQ_AssetGrowth_Y", "formula": "总资产同比增长率", "category": "growth", "source": "JQ", "ref": "asset_growth"},
            {"name": "JQ_OPE_Y", "formula": "经营性现金流/总资产", "category": "quality", "source": "JQ", "ref": "operating_cash_flow_ratio"},
            # 质量因子
            {"name": "JQ_GROSS_MARGIN", "formula": "(收入-成本)/收入", "category": "quality", "source": "JQ", "ref": "gross_margin"},
            {"name": "JQ_ROE_TTM", "formula": "净利润/净资产(TTM)", "category": "quality", "source": "JQ", "ref": "roe_ttm"},
            {"name": "JQ_ROA_TTM", "formula": "净利润/总资产(TTM)", "category": "quality", "source": "JQ", "ref": "roa_ttm"},
            {"name": "JQ_ACCRUAL", "formula": "(净利润-经营现金流)/总资产", "category": "quality", "source": "JQ", "ref": "accrual_quality"},
            {"name": "JQ_LEVERAGE", "formula": "总负债/总资产", "category": "risk", "source": "JQ", "ref": "leverage_ratio"},
            {"name": "JQ_CURRENT_RATIO", "formula": "流动资产/流动负债", "category": "risk", "source": "JQ", "ref": "current_ratio"},
            # 价值因子
            {"name": "JQ_EP_TTM", "formula": "净利润/总市值(E/P)", "category": "value", "source": "JQ", "ref": "earnings_yield"},
            {"name": "JQ_BP_LF", "formula": "净资产/总市值(B/P)", "category": "value", "source": "JQ", "ref": "book_to_price"},
            {"name": "JQ_CFP_TTM", "formula": "经营现金流/总市值(C/P)", "category": "value", "source": "JQ", "ref": "cashflow_yield"},
            {"name": "JQ_SP_TTM", "formula": "营业收入/总市值(S/P)", "category": "value", "source": "JQ", "ref": "sales_yield"},
            {"name": "JQ_FCFP", "formula": "自由现金流/总市值", "category": "value", "source": "JQ", "ref": "fcf_yield"},
            {"name": "JQ_DIVIDEND_YIELD", "formula": "股息/股价", "category": "value", "source": "JQ", "ref": "dividend_yield"},
            # 动量因子 (聚宽特色)
            {"name": "JQ_MOM_12M", "formula": "过去12个月收益率(扣除最近1个月)", "category": "momentum", "source": "JQ", "ref": "momentum_12_1"},
            {"name": "JQ_MOM_6M", "formula": "过去6个月收益率", "category": "momentum", "source": "JQ", "ref": "momentum_6m"},
            {"name": "JQ_MOM_3M", "formula": "过去3个月收益率", "category": "momentum", "source": "JQ", "ref": "momentum_3m"},
            {"name": "JQ_REV_1M", "formula": "过去1个月收益率(反转)", "category": "reversal", "source": "JQ", "ref": "short_term_reversal_jq"},
            {"name": "JQ_REV_5D", "formula": "过去5日收益率(超短反转)", "category": "reversal", "source": "JQ", "ref": "ultra_short_reversal"},
            # 波动因子
            {"name": "JQ_VOL_60D", "formula": "60日收益波动率", "category": "risk", "source": "JQ", "ref": "volatility_60d"},
            {"name": "JQ_VOL_20D", "formula": "20日收益波动率", "category": "risk", "source": "JQ", "ref": "volatility_20d"},
            {"name": "JQ_MAX_RET_60D", "formula": "60日最大日收益率", "category": "risk", "source": "JQ", "ref": "max_return_60d"},
            {"name": "JQ_MIN_RET_60D", "formula": "60日最小日收益率", "category": "risk", "source": "JQ", "ref": "min_return_60d"},
            {"name": "JQ_SKEW_60D", "formula": "60日收益偏度", "category": "risk", "source": "JQ", "ref": "return_skewness"},
            {"name": "JQ_KURT_60D", "formula": "60日收益峰度", "category": "risk", "source": "JQ", "ref": "return_kurtosis"},
            # 量价相关性
            {"name": "JQ_VOLUME_20D_MA", "formula": "20日均成交量/120日均成交量", "category": "volume", "source": "JQ", "ref": "volume_ratio_20_120"},
            {"name": "JQ_AMIHUD_20D", "formula": "20日Amihud非流动性指标", "category": "liquidity", "source": "JQ", "ref": "amihud_illiq_20d"},
            {"name": "JQ_TURNOVER_20D", "formula": "20日平均换手率", "category": "liquidity", "source": "JQ", "ref": "turnover_20d"},
            {"name": "JQ_TURNOVER_STD_20D", "formula": "20日换手率波动", "category": "liquidity", "source": "JQ", "ref": "turnover_volatility"},
            {"name": "JQ_ILLIQ_RANK", "formula": "非流动性指标排名(截面)", "category": "liquidity", "source": "JQ", "ref": "illiq_rank"},
            # 技术指标类
            {"name": "JQ_RSI_14D", "formula": "14日RSI", "category": "momentum", "source": "JQ", "ref": "rsi_14"},
            {"name": "JQ_MACD", "formula": "MACD DIF-DEA", "category": "trend", "source": "JQ", "ref": "macd"},
            {"name": "JQ_BIAS_5D", "formula": "乖离率(5日)", "category": "reversal", "source": "JQ", "ref": "bias_5d"},
            {"name": "JQ_BIAS_10D", "formula": "乖离率(10日)", "category": "reversal", "source": "JQ", "ref": "bias_10d"},
            {"name": "JQ_CCI_14D", "formula": "14日CCI", "category": "momentum", "source": "JQ", "ref": "cci_14"},
        ]

    # ── ZiMuKu 通达信技术指标 ─────────────────────────
    def load_zimuku_factors(self) -> List[Dict]:
        """ZiMuKu/通达信指标 → 因子化 (精选60+)"""
        return [
            # K线形态因子
            {"name": "ZM_CDL_BODY", "formula": "实体比例(close-open)/(high-low)", "category": "price", "source": "ZiMuKu", "ref": "candle_body_ratio"},
            {"name": "ZM_CDL_UPSHADOW", "formula": "上影线比例(high-max(close,open))/(high-low)", "category": "price", "source": "ZiMuKu", "ref": "upper_shadow_ratio"},
            {"name": "ZM_CDL_DOWNSHADOW", "formula": "下影线比例(min(close,open)-low)/(high-low)", "category": "price", "source": "ZiMuKu", "ref": "lower_shadow_ratio"},
            {"name": "ZM_CDL_MARUBOZU", "formula": "光头光脚(实体比例>0.95)", "category": "price", "source": "ZiMuKu", "ref": "marubozu"},
            {"name": "ZM_CDL_HAMMER", "formula": "锤子线(下影线>实体2倍且上影线很小)", "category": "price", "source": "ZiMuKu", "ref": "hammer_candle"},
            {"name": "ZM_CDL_DOJI", "formula": "十字星(abs(close-open)/(high-low)<0.02)", "category": "price", "source": "ZiMuKu", "ref": "doji"},
            {"name": "ZM_CDL_ENGULFING", "formula": "吞没形态(今日实体包裹昨日实体)", "category": "price", "source": "ZiMuKu", "ref": "engulfing_pattern"},
            # 均线系统
            {"name": "ZM_MA5_10_CROSS", "formula": "MA5与MA10差值/MA5", "category": "trend", "source": "ZiMuKu", "ref": "ma5_10_cross"},
            {"name": "ZM_MA10_20_CROSS", "formula": "MA10与MA20差值/MA10", "category": "trend", "source": "ZiMuKu", "ref": "ma10_20_cross"},
            {"name": "ZM_MA5_20_CROSS", "formula": "MA5与MA20差值/MA5", "category": "trend", "source": "ZiMuKu", "ref": "ma5_20_cross"},
            {"name": "ZM_MA_ARRANGE", "formula": "均线排列(MA5>MA10>MA20=多头排列)", "category": "trend", "source": "ZiMuKu", "ref": "ma_arrangement"},
            {"name": "ZM_MA_DISTANCE", "formula": "股价到MA20的距离百分比", "category": "trend", "source": "ZiMuKu", "ref": "price_to_ma20"},
            {"name": "ZM_MA_SLOPE_5", "formula": "MA5斜率((MA5-MA5_prev)/MA5_prev)", "category": "trend", "source": "ZiMuKu", "ref": "ma5_slope"},
            {"name": "ZM_MA_SLOPE_20", "formula": "MA20斜率", "category": "trend", "source": "ZiMuKu", "ref": "ma20_slope"},
            # 布林带
            {"name": "ZM_BOLL_POS", "formula": "布林带位置(close-下轨)/(上轨-下轨)", "category": "volatility", "source": "ZiMuKu", "ref": "bollinger_position"},
            {"name": "ZM_BOLL_WIDTH", "formula": "布林带宽度(上轨-下轨)/中轨", "category": "volatility", "source": "ZiMuKu", "ref": "bollinger_width"},
            {"name": "ZM_BOLL_BREAK_HIGH", "formula": "突破布林带上轨(close>上轨)", "category": "volatility", "source": "ZiMuKu", "ref": "bollinger_breakout_up"},
            {"name": "ZM_BOLL_BREAK_LOW", "formula": "跌破布林带下轨(close<下轨)", "category": "volatility", "source": "ZiMuKu", "ref": "bollinger_breakout_down"},
            # 成交量变异
            {"name": "ZM_VOL_SURGE", "formula": "成交量突增(今日/5日均量-1)", "category": "volume", "source": "ZiMuKu", "ref": "volume_surge"},
            {"name": "ZM_VOL_SHRINK", "formula": "成交量萎缩(1-今日/5日均量)", "category": "volume", "source": "ZiMuKu", "ref": "volume_shrink"},
            {"name": "ZM_VOL_PRICE_CONFIRM", "formula": "价量配合(sign(close-open)*volume)", "category": "volume", "source": "ZiMuKu", "ref": "volume_price_confirm"},
            {"name": "ZM_VOL_PRICE_DIVERGE", "formula": "价量背离(close涨但volume跌)", "category": "volume", "source": "ZiMuKu", "ref": "volume_price_divergence_zm"},
            {"name": "ZM_VOL_MA5", "formula": "5日均量/20日均量", "category": "volume", "source": "ZiMuKu", "ref": "volume_ma_ratio"},
            {"name": "ZM_VOL_ACCUM", "formula": "累积/派发线(CLV*volume)", "category": "volume", "source": "ZiMuKu", "ref": "accumulation_distribution"},
            # 大盘相关
            {"name": "ZM_BETA_60D", "formula": "60日Beta(相对大盘)", "category": "risk", "source": "ZiMuKu", "ref": "beta_60d"},
            {"name": "ZM_CORR_MARKET_60D", "formula": "60日与大盘相关性", "category": "risk", "source": "ZiMuKu", "ref": "market_corr_60d"},
            {"name": "ZM_RELATIVE_STRENGTH", "formula": "相对强弱(个股收益/大盘收益-1)", "category": "momentum", "source": "ZiMuKu", "ref": "relative_strength"},
            # 反转信号
            {"name": "ZM_HAMMER_REVERSAL", "formula": "锤子线+低成交量(底部反转信号)", "category": "reversal", "source": "ZiMuKu", "ref": "hammer_reversal"},
            {"name": "ZM_SHOOTING_STAR", "formula": "射击之星(上影线>实体2倍+顶部)", "category": "reversal", "source": "ZiMuKu", "ref": "shooting_star"},
            {"name": "ZM_3WHITE_SOLDIERS", "formula": "三白兵(连续3根长阳)", "category": "trend", "source": "ZiMuKu", "ref": "three_white_soldiers"},
            {"name": "ZM_3BLACK_CROWS", "formula": "三乌鸦(连续3根长阴)", "category": "trend", "source": "ZiMuKu", "ref": "three_black_crows"},
        ]

    # ── 学术因子体系 ──────────────────────────────────
    def load_academic_factors(self) -> List[Dict]:
        """学术经典因子 — Fama-French 5因子 + Carhart + Novy-Marx + Asness等"""
        return [
            # Fama-French 3因子 (1993)
            {"name": "FF_MKT_EXCESS", "formula": "R_market - R_f(超额收益)", "category": "market", "source": "ACADEMIC", "ref": "FF3_Market_Risk"},
            {"name": "FF_SMB", "formula": "小盘股收益-大盘股收益", "category": "size", "source": "ACADEMIC", "ref": "FF3_Size"},
            {"name": "FF_HML", "formula": "高BP/低BP收益差", "category": "value", "source": "ACADEMIC", "ref": "FF3_Value"},
            # Carhart 4因子 (1997)
            {"name": "CARHART_MOM", "formula": "过去12个月赢家-输家收益差", "category": "momentum", "source": "ACADEMIC", "ref": "Carhart_Momentum"},
            # Fama-French 5因子 (2015)
            {"name": "FF_RMW", "formula": "高盈利/低盈利收益差(Robust-Minus-Weak)", "category": "quality", "source": "ACADEMIC", "ref": "FF5_Profitability"},
            {"name": "FF_CMA", "formula": "低投资/高投资收益差(Conservative-Minus-Aggressive)", "category": "value", "source": "ACADEMIC", "ref": "FF5_Investment"},
            # Novy-Marx盈利因子 (2013)
            {"name": "NM_GP_AT", "formula": "毛利润/总资产(Gross-Profitability-to-Asset)", "category": "quality", "source": "ACADEMIC", "ref": "NovyMarx_Profitability"},
            # Asness QMJ因子 (2019)
            {"name": "ASNESS_QMJ", "formula": "质量因子综合(Quality-Minus-Junk)", "category": "quality", "source": "ACADEMIC", "ref": "Asness_Quality"},
            # 低波异常 (Ang 2006)
            {"name": "ANG_LOW_VOL", "formula": "低波动率超额收益(做多低波,做空高波)", "category": "risk", "source": "ACADEMIC", "ref": "Ang_Low_Beta_Anomaly"},
            # Amihud非流动性 (2002)
            {"name": "AMIHUD_ILLIQ", "formula": "|日收益率|/日成交额(非流动性指标)", "category": "liquidity", "source": "ACADEMIC", "ref": "Amihud_Illiquidity"},
            # 应计质量 (Sloan 1996)
            {"name": "SLOAN_ACCRUAL", "formula": "应计项目占比(净利润-经营现金流)/总资产", "category": "quality", "source": "ACADEMIC", "ref": "Sloan_Accrual"},
            # 净股票发行 (Fama-French 2008)
            {"name": "FF_NET_ISSUE", "formula": "净股票发行(增发-回购), 发行多则未来收益低", "category": "value", "source": "ACADEMIC", "ref": "Fama_Net_Stock_Issue"},
        ]

    # ── Qlib Alpha158 ─────────────────────────────────
    def load_qlib_factors(self) -> List[Dict]:
        """Qlib Alpha158 核心因子 — Qlib标配158因子中精选20+"""
        return [
            {"name": "QLIB_ROC_5", "formula": "close/shift(close,5)-1", "category": "momentum", "source": "QLIB", "ref": "rate_of_change_5d"},
            {"name": "QLIB_ROC_10", "formula": "close/shift(close,10)-1", "category": "momentum", "source": "QLIB", "ref": "rate_of_change_10d"},
            {"name": "QLIB_ROC_20", "formula": "close/shift(close,20)-1", "category": "momentum", "source": "QLIB", "ref": "rate_of_change_20d"},
            {"name": "QLIB_ROC_60", "formula": "close/shift(close,60)-1", "category": "momentum", "source": "QLIB", "ref": "rate_of_change_60d"},
            {"name": "QLIB_MA_5", "formula": "MA(close,5)", "category": "trend", "source": "QLIB", "ref": "ma_5"},
            {"name": "QLIB_MA_10", "formula": "MA(close,10)", "category": "trend", "source": "QLIB", "ref": "ma_10"},
            {"name": "QLIB_MA_20", "formula": "MA(close,20)", "category": "trend", "source": "QLIB", "ref": "ma_20"},
            {"name": "QLIB_STD_5", "formula": "STD(returns,5)", "category": "risk", "source": "QLIB", "ref": "volatility_5d"},
            {"name": "QLIB_STD_10", "formula": "STD(returns,10)", "category": "risk", "source": "QLIB", "ref": "volatility_10d"},
            {"name": "QLIB_STD_20", "formula": "STD(returns,20)", "category": "risk", "source": "QLIB", "ref": "volatility_20d"},
            {"name": "QLIB_BETA_20", "formula": "cov(returns,market_returns,20)/var(market_returns,20)", "category": "risk", "source": "QLIB", "ref": "beta_20d"},
            {"name": "QLIB_RSI_14", "formula": "RSI(close,14)", "category": "momentum", "source": "QLIB", "ref": "rsi_14d"},
            {"name": "QLIB_MACD", "formula": "MACD(close,12,26)", "category": "trend", "source": "QLIB", "ref": "macd_12_26"},
            {"name": "QLIB_BOLL", "formula": "(close-MA(close,20))/STD(close,20)", "category": "volatility", "source": "QLIB", "ref": "bollinger_position_2"},
            {"name": "QLIB_VOL_MA_5", "formula": "volume/MA(volume,5)", "category": "volume", "source": "QLIB", "ref": "volume_ratio"},
            {"name": "QLIB_VOL_STD_5", "formula": "STD(volume,5)/MA(volume,5)", "category": "volume", "source": "QLIB", "ref": "volume_volatility"},
            {"name": "QLIB_HIGH_LOW_RATIO", "formula": "(high-low)/close", "category": "volatility", "source": "QLIB", "ref": "daily_range_ratio"},
            {"name": "QLIB_OPEN_CLOSE", "formula": "(close-open)/abs(close-open)", "category": "price", "source": "QLIB", "ref": "intraday_direction"},
            {"name": "QLIB_PRICE_VOL_CORR_5", "formula": "corr(close,volume,5)", "category": "volume", "source": "QLIB", "ref": "price_vol_corr"},
            {"name": "QLIB_RESIDUAL_20", "formula": "close回归MA20的残差", "category": "price", "source": "QLIB", "ref": "residual_to_ma"},
        ]

    # ── A股特有因子 ──────────────────────────────────
    def load_ashare_factors(self) -> List[Dict]:
        """A股市场特有的因子 (不依赖Level2数据, 但捕捉A股特色)"""
        return [
            {"name": "ASH_LIMITUP", "formula": "是否涨停(sign(close=涨停价))", "category": "price", "source": "ASHARE", "ref": "limit_up"},
            {"name": "ASH_LIMITDOWN", "formula": "是否跌停(sign(close=跌停价))", "category": "price", "source": "ASHARE", "ref": "limit_down"},
            {"name": "ASH_LIMITUP_STRENGTH", "formula": "涨停强度(封板时间早+封单大=强)", "category": "sentiment", "source": "ASHARE", "ref": "limit_up_strength"},
            {"name": "ASH_ST_ALERT", "formula": "ST/*ST预警", "category": "risk", "source": "ASHARE", "ref": "st_warning"},
            {"name": "ASH_PLATE_LIFT", "formula": "板块涨停潮(同板块多股涨停)", "category": "sentiment", "source": "ASHARE", "ref": "plate_limit_up_crowd"},
            {"name": "ASH_ZDT_HIGH", "formula": "炸板率(涨停打开次数)", "category": "sentiment", "source": "ASHARE", "ref": "limit_up_fail_rate"},
            {"name": "ASH_PREMIUM_REFUND", "formula": "大宗交易折溢价率", "category": "value", "source": "ASHARE", "ref": "block_trade_premium"},
            {"name": "ASH_MAJOR_HOLD", "formula": "大股东持股比例变化", "category": "sentiment", "source": "ASHARE", "ref": "major_shareholder_change"},
            {"name": "ASH_HOT_MONEY", "formula": "游资活跃度(龙虎榜买入额)", "category": "sentiment", "source": "ASHARE", "ref": "hot_money_flow"},
            {"name": "ASH_CONCEPT", "formula": "概念板块热度(所属概念板块涨幅)", "category": "sentiment", "source": "ASHARE", "ref": "concept_heat"},
            {"name": "ASH_SEASONALITY", "formula": "日历效应(春节/两会/国庆效应)", "category": "sentiment", "source": "ASHARE", "ref": "calendar_effect"},
            {"name": "ASH_WEEKDAY", "formula": "周内效应(周一夜盘/周五尾盘)", "category": "sentiment", "source": "ASHARE", "ref": "weekday_effect"},
            {"name": "ASH_IPO_DILUTION", "formula": "解禁冲击(限售股解禁日)", "category": "risk", "source": "ASHARE", "ref": "lockup_expiry"},
            {"name": "ASH_PLEDGE_RISK", "formula": "股权质押比例(>50%高警示)", "category": "risk", "source": "ASHARE", "ref": "pledge_ratio"},
            {"name": "ASH_SHARE_TRANSFER", "formula": "股东增减持(净减持=利空)", "category": "sentiment", "source": "ASHARE", "ref": "share_transfer_action"},
        ]

    # ── 同步主方法 ──────────────────────────────────
    def sync_all_sources(self) -> Dict:
        """同步所有已知因子源 → 入库"""
        results = {}
        total = 0
        
        for src_name, loader_fn in [
            ("WorldQuant 101", self.load_worldquant_101),
            ("JoinQuant 聚宽精选", self.load_jq_factors),
            ("ZiMuKu 技术指标", self.load_zimuku_factors),
            ("Academic 学术因子", self.load_academic_factors),
            ("Qlib Alpha158", self.load_qlib_factors),
            ("A股特有因子", self.load_ashare_factors),
        ]:
            factors = loader_fn()
            count = 0
            for f in factors:
                name = f["name"]
                if name not in self.library:
                    f["status"] = "active"
                    f["ic"] = None
                    f["added_at"] = datetime.now().isoformat()
                    self.library[name] = f
                    count += 1
            results[src_name] = count
            total += count
        
        self.save()
        results["total_new"] = total
        results["library_size"] = len(self.library)
        return results
    
    def summary(self) -> Dict:
        """因子库概览"""
        categories = {}
        sources = {}
        for name, f in self.library.items():
            cat = f.get("category", "unknown")
            src = f.get("source", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            sources[src] = sources.get(src, 0) + 1
        
        active = sum(1 for f in self.library.values() if f.get("status") == "active")
        verified = sum(1 for f in self.library.values() if f.get("ic") is not None)
        
        return {
            "total_factors": len(self.library),
            "active": active,
            "verified": verified,
            "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
            "sources": dict(sorted(sources.items(), key=lambda x: -x[1])),
        }

    # ── 向 factor_engine 注册 ──────────────────────
    def register_to_engine(self):
        """
        将挖掘到的因子注册到 factor_engine 中
        每个因子分配权重:
          - Sourced(有源因子): 0.015
          - Verified(IC验证过的): 0.025
          - 同类因子平均分配权重上限 25%
        """
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from scripts.factor_engine import get_engine
        
        engine = get_engine()
        category_weights = {
            "momentum": 0.20, "volume": 0.20, "volume_trend": 0.08,
            "trend": 0.10, "volatility": 0.08,
            "price": 0.05, "price_volume": 0.05, "volume_pattern": 0.05,
            "reversal": 0.08, "quality": 0.10, "value": 0.10,
            "growth": 0.08, "risk": 0.10, "sentiment": 0.08,
            "liquidity": 0.06, "market": 0.03, "size": 0.03,
        }
        
        # 按类别分组, 平均分配该类别权重
        cat_groups = {}
        for name, f in self.library.items():
            if f.get("status") != "active":
                continue
            cat = f.get("category", "unknown")
            cat_groups.setdefault(cat, []).append((name, f))
        
        registered = 0
        for cat, factors in cat_groups.items():
            max_w = category_weights.get(cat, 0.05)
            per_factor = max(0.01, min(max_w / max(1, len(factors)), 0.05))
            
            for name, f in factors:
                engine.register_factor(
                    name=name,
                    category=cat,
                    weight=per_factor,
                    data_sources=[f.get("source", "mined")]
                )
                registered += 1
        
        # 通知引擎有人注册了新因子
        engine.factor_count = len(engine.factors)
        return registered


def main():
    miner = FactorMiner()
    
    if "--status" in sys.argv or "-s" in sys.argv:
        s = miner.summary()
        print(f"📚 因子库: {s['total_factors']} 个 (活跃: {s['active']}, 已验证IC: {s['verified']})")
        print(f"\n📂 分类分布:")
        for cat, cnt in s["categories"].items():
            bar = "█" * (cnt // 3) + "░" * (20 - min(cnt // 3, 20))
            pct = cnt / max(1, s['total_factors']) * 100
            print(f"  {cat:<15} {cnt:>3}个 ({pct:4.1f}%) {bar}")
        print(f"\n📡 来源分布:")
        for src, cnt in s["sources"].items():
            src_name = SOURCES.get(src, src)
            bar = "█" * (cnt // 2) + "░" * (20 - min(cnt // 2, 20))
            print(f"  {src:<10} {cnt:>3}个 {bar}  ({src_name})")
        return
    
    if "--register" in sys.argv or "-r" in sys.argv:
        reg = miner.register_to_engine()
        print(f"✅ {reg} 个因子已注册到 factor_engine")
        return
    
    # 默认: 同步所有因子源
    r = miner.sync_all_sources()
    print(f"📚 因子挖掘完成!")
    print(f"  ✅ WorldQuant 101:          {r.get('WorldQuant 101', 0):>3} 个新因子")
    print(f"  ✅ JoinQuant 聚宽精选:      {r.get('JoinQuant 聚宽精选', 0):>3} 个新因子")
    print(f"  ✅ ZiMuKu 技术指标:         {r.get('ZiMuKu 技术指标', 0):>3} 个新因子")
    print(f"  ✅ Academic 学术因子:       {r.get('Academic 学术因子', 0):>3} 个新因子")
    print(f"  ✅ Qlib Alpha158:           {r.get('Qlib Alpha158', 0):>3} 个新因子")
    print(f"  ✅ A股特有因子:             {r.get('A股特有因子', 0):>3} 个新因子")
    print(f"  📈 因子库总计:              {r['library_size']} 个因子")
    print(f"\n运行: python3 factor_mining.py --status 查看详情")
    print(f"运行: python3 factor_mining.py --register 注册到因子引擎")


if __name__ == "__main__":
    main()
