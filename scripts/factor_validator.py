#!/usr/bin/env python3
"""
因子有效性验证引擎 v1
========================
功能:
  1. WQ101 DSL公式解析器 (26个函数)
  2. JQ/ZM/ASH/QLib等标准因子计算
  3. IC (信息系数) 验证
  4. 因子过滤 → 更新 factor_library.json
  
用法:
    python3 factor_validator.py --run          # 全量验证
    python3 factor_validator.py --factor MA    # 验证单个因子
    python3 factor_validator.py --report       # 只看报告
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr
from typing import Dict, List, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
import os, json, re, math
from collections import defaultdict

# ─────────────── 配置 ───────────────

FACTOR_LIB_PATH = os.path.expanduser("~/.openclaw/data/factor_library.json")
VALIDATION_RESULTS_PATH = os.path.expanduser("~/.openclaw/data/factor_validation.json")
MIN_IC_THRESHOLD = 0.02      # 因子存活IC阈值
GOOD_IC_THRESHOLD = 0.05     # 好因子
EXCELLENT_IC_THRESHOLD = 0.10  # 优秀因子
MIN_DATA_POINTS = 15         # 最小IC计算点数

# ─────────────── WQ101 DSL 函数实现 ───────────────

class WQ101Env:
    """WorldQuant Alpha101 DSL 执行环境"""
    
    def __init__(self, opens, highs, lows, closes, volumes, returns=None, adv20=None):
        self.open = np.array(opens, dtype=float)
        self.high = np.array(highs, dtype=float)
        self.low = np.array(lows, dtype=float)
        self.close = np.array(closes, dtype=float)
        self.volume = np.array(volumes, dtype=float)
        self._n = len(self.close)
        self.vwap = (self.high + self.low + self.close) / 3
        # returns 对齐长度为 n (pad第一个值为NaN)
        if returns is not None and len(returns) == self._n - 1:
            self.returns = np.concatenate([[np.nan], returns])
        elif returns is not None and len(returns) == self._n:
            self.returns = returns
        else:
            r = np.diff(np.log(self.close))
            self.returns = np.concatenate([[np.nan], r])
        # pad adv20
        if adv20 is not None and len(adv20) == self._n - 1:
            self.adv20 = np.concatenate([[np.nan], adv20])
        elif adv20 is not None and len(adv20) == self._n:
            self.adv20 = adv20
        elif adv20 is not None:
            self.adv20 = np.full(self._n, np.mean(adv20))
        else:
            self.adv20 = np.full(self._n, np.mean(self.volume))
    
    @staticmethod
    def rank(x):
        """截面排名 (0~1归一化)"""
        return pd.Series(x).rank(pct=True).values
    
    @staticmethod
    def scale(x):
        """缩放为abs sum=1"""
        s = np.nansum(np.abs(x))
        return x / s if s != 0 else x
    
    @staticmethod
    def delta(x, d):
        """x - delay(x, d)"""
        x_arr = np.array(x)
        result = np.full_like(x_arr, np.nan)
        result[d:] = x_arr[d:] - x_arr[:-d]
        return result
    
    @staticmethod
    def delay(x, d):
        """shift back by d"""
        x_arr = np.array(x)
        result = np.full_like(x_arr, np.nan)
        result[d:] = x_arr[:-d]
        return result
    
    @staticmethod
    def correlation(x, y, d):
        """滚动相关系数"""
        x_s, y_s = pd.Series(x), pd.Series(y)
        return x_s.rolling(d).corr(y_s).values
    
    @staticmethod
    def covariance(x, y, d):
        """滚动协方差"""
        x_s, y_s = pd.Series(x), pd.Series(y)
        return x_s.rolling(d).cov(y_s).values
    
    @staticmethod
    def stddev(x, d):
        """滚动标准差"""
        return pd.Series(x).rolling(d).std(ddof=0).values
    
    @staticmethod
    def var(x, d):
        """滚动方差"""
        return pd.Series(x).rolling(d).var(ddof=0).values
    
    @classmethod
    def signed_power(cls, x, e):
        """sign(x) * |x|^e"""
        return np.sign(x) * np.abs(x) ** e
    
    @staticmethod
    def ts_argmax(x, d):
        """过去d天内最大值的位置"""
        x_arr = np.array(x)
        result = np.full_like(x_arr, np.nan)
        for i in range(d, len(x_arr)):
            result[i] = np.argmax(x_arr[i-d:i])
        return result
    
    @staticmethod
    def ts_argmin(x, d):
        """过去d天内最小值的位置"""
        x_arr = np.array(x)
        result = np.full_like(x_arr, np.nan)
        for i in range(d, len(x_arr)):
            result[i] = np.argmin(x_arr[i-d:i])
        return result
    
    @staticmethod
    def ts_rank(x, d):
        """过去d天滚动排名"""
        return pd.Series(x).rolling(d).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1]).values
    
    @staticmethod
    def ts_max(x, d):
        """过去d天滚动最大值"""
        return pd.Series(x).rolling(d).max().values
    
    @staticmethod
    def ts_min(x, d):
        """过去d天滚动最小值"""
        return pd.Series(x).rolling(d).min().values
    
    @staticmethod
    def ts_sum(x, d):
        """过去d天滚动求和"""
        return pd.Series(x).rolling(d).sum().values
    
    @staticmethod
    def ts_product(x, d):
        """过去d天滚动乘积"""
        return pd.Series(x).rolling(d).apply(np.prod).values
    
    @staticmethod
    def decay_linear(x, d):
        """线性衰减加权移动平均"""
        x_arr = np.array(x)
        weights = np.arange(d, 0, -1)
        result = np.full_like(x_arr, np.nan)
        for i in range(d-1, len(x_arr)):
            result[i] = np.dot(x_arr[i-d+1:i+1], weights) / weights.sum()
        return result
    
    @staticmethod
    def sma(x, d):
        """简单移动平均"""
        return pd.Series(x).rolling(d).mean().values
    
    @staticmethod
    def sum(x, d):
        """同ts_sum"""
        return pd.Series(x).rolling(d).sum().values
    
    @classmethod
    def cumprod(cls, x, d):
        """累积乘积"""
        x_arr = np.array(x)
        result = np.ones_like(x_arr)
        if d > 0:
            for i in range(min(d, len(x_arr))):
                result[i] = np.prod(x_arr[:i+1] + 1) if i > 0 else (1 + x_arr[0])
        else:
            result = np.cumprod(1 + x_arr)
        return result
    
    @staticmethod
    def sign(x):
        return np.sign(x)
    
    @staticmethod
    def abs(x):
        return np.abs(x)
    
    @staticmethod
    def log(x):
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(x > 0, np.log(x), 0)
    
    @staticmethod
    def sqrt(x):
        with np.errstate(invalid='ignore'):
            return np.where(x >= 0, np.sqrt(x), 0)
    
    @staticmethod
    def MA(x, d):
        return pd.Series(x).rolling(d).mean().values
    
    @staticmethod
    def STD(x, d):
        return pd.Series(x).rolling(d).std(ddof=0).values
    
    @staticmethod
    def MACD(close, fast=12, slow=26):
        """MACD值"""
        c = pd.Series(close)
        ema_fast = c.ewm(span=fast).mean()
        ema_slow = c.ewm(span=slow).mean()
        return (ema_fast - ema_slow).values
    
    @classmethod
    def RSI(cls, close, period=14):
        """RSI指标"""
        c = pd.Series(close)
        delta = c.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        return (100 - 100 / (1 + rs)).values
    
    @staticmethod
    def Beta(y, x, d):
        """滚动Beta"""
        y_s, x_s = pd.Series(y), pd.Series(x)
        def _beta(ys, xs):
            if len(ys) < 2:
                return np.nan
            cov = np.cov(ys, xs)[0, 1]
            var_x = np.var(xs)
            return cov / var_x if var_x != 0 else 0
        return np.array([_beta(y_s[max(0,i-d):i].values, x_s[max(0,i-d):i].values) 
                        if i > 0 else np.nan for i in range(len(y_s))])
    
    @staticmethod
    def shift(x, d):
        return WQ101Env.delay(x, d)
    
    def _get_var(self, name):
        """获取变量值"""
        var_map = {
            'open': self.open, 'high': self.high, 'low': self.low,
            'close': self.close, 'volume': self.volume, 'vwap': self.vwap,
            'returns': self.returns, 'adv20': self.adv20,
        }
        if name in var_map:
            return var_map[name]
        raise ValueError(f"未知变量: {name}")
    
    def _eval_atom(self, atom):
        """计算WQ101表达式 (简单的递归下降)"""
        atom = atom.strip()
        
        # 数字
        try:
            return float(atom) * np.ones(self._n)
        except ValueError:
            pass
        
        # 变量 (close, open, volume...)
        try:
            return self._get_var(atom)
        except ValueError:
            pass
        
        return None
    
    def eval(self, formula):
        """评估WQ101公式字符串 - 简化版本"""
        if not formula or formula == 'None':
            return np.full(self._n, np.nan)
        
        formula = formula.strip()
        
        # 去除外围括号
        while formula.startswith('(') and formula.endswith(')'):
            inner = formula[1:-1]
            if inner.count('(') == inner.count(')'):
                formula = inner
        
        # 替换别名函数
        formula = formula.replace('corr(', 'correlation(')
        formula = formula.replace('cov(', 'covariance(')
        formula = formula.replace('ts_sum(', 'sum(')
        
        # 先尝试直接计算已知公式模式
        try:
            return self._eval_formula(formula)
        except Exception as e:
            return None
    
    def _eval_formula(self, formula):
        """递归计算公式"""
        formula = formula.strip()
        
        # 三元条件: (cond) ? a : b
        q_idx = formula.find('?')
        if q_idx > 0:
            # 找到最外层 ? 前的整个三元表达式
            # strategy: 找到 ? 和 : 之间的区域，考虑括号嵌套
            # 先找最顶层 ? 的位置（depth=0时的第一个?）
            depth = 0
            cond_end = 0
            for i, c in enumerate(formula):
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                elif c == '?' and depth == 0:
                    cond_end = i
                    break
            
            after_q = formula[cond_end+1:]
            # 在after_q中找到顶层的 : 
            depth = 0
            colon_idx = -1
            for i, c in enumerate(after_q):
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                elif c == ':' and depth == 0:
                    colon_idx = i
                    break
            
            if colon_idx > 0:
                a_str = after_q[:colon_idx].strip()
                b_str = after_q[colon_idx+1:].strip()
                cond_str = formula[:cond_end].strip()
                # 如果cond有外层()，去掉
                if cond_str.startswith('(') and cond_str.endswith(')'):
                    cond_str = cond_str[1:-1]
                
                cond = self._eval_formula(cond_str)
                a = self._eval_formula(a_str)
                b = self._eval_formula(b_str)
                if cond is not None and a is not None and b is not None:
                    return np.where(cond > 0, a, b)
            return None
        
        # 函数调用: func(arg1, arg2, ...) — 找第一个顶级函数调用
        match = re.match(r'([A-Za-z_]\w*)\s*\(', formula)
        if match:
            func_name = match.group(1).lower()
            start = match.end() - 1  # 定位到'('
            end = self._find_matching_paren(formula, start)
            if end > 0 and end == len(formula) - 1:
                # 整个公式 = func(args)
                args_str = formula[start+1:end]
                args = self._split_args(args_str)
                return self._call_func(func_name, args)
            elif end > 0:
                # func(args) + more
                inner = self._call_func(func_name, self._split_args(formula[start+1:end]))
                if inner is not None:
                    rest = formula[end+1:].strip()
                    if rest:
                        # 继续解析剩余部分 (如 func(x) OP y)
                        result = self._eval_formula(f'_{rest}')
                        # Try all binary ops
                        for op, op_func in [('*',lambda a,b:a*b),('/',lambda a,b:a/(b+1e-10)),
                                            ('+',lambda a,b:a+b),('-',lambda a,b:a-b)]:
                            parts = self._split_binary(rest, op)
                            if len(parts) == 2:
                                r = self._eval_formula(parts[1])
                                if r is not None:
                                    return op_func(inner, r)
                        return inner
                    return inner
        
        # 一元操作: -expr
        unary_match = re.match(r'-\s*(.+)$', formula)
        if unary_match:
            val = self._eval_formula(unary_match.group(1))
            return -val if val is not None else None
        
        # 二元操作 (按优先级: * / 先于 + - 先于 < >)
        for op, op_func in [
            ('*', lambda a,b: a*b),
            ('/', lambda a,b: a/(b+1e-10)),
            ('+', lambda a,b: a+b),
            ('-', lambda a,b: a-b),
            ('<', lambda a,b: (a < b).astype(float)),
            ('>', lambda a,b: (a > b).astype(float)),
        ]:
            parts = self._split_binary(formula, op)
            if len(parts) == 2:
                left = self._eval_formula(parts[0])
                right = self._eval_formula(parts[1])
                if left is not None and right is not None:
                    return op_func(left, right)
        
        # 原子
        return self._eval_atom(formula)
    
    def _find_matching_paren(self, s, start):
        """找到匹配的右括号"""
        depth = 0
        for i in range(start, len(s)):
            if s[i] == '(':
                depth += 1
            elif s[i] == ')':
                depth -= 1
                if depth == 0:
                    return i
        return -1
    
    def _split_args(self, s):
        """分割逗号参数 (考虑括号嵌套)"""
        args = []
        depth = 0
        current = ''
        for c in s:
            if c == '(':
                depth += 1
                current += c
            elif c == ')':
                depth -= 1
                current += c
            elif c == ',' and depth == 0:
                args.append(current.strip())
                current = ''
            else:
                current += c
        if current.strip():
            args.append(current.strip())
        return args
    
    def _split_binary(self, s, op):
        """分割二元操作符 (考虑括号嵌套)"""
        depth = 0
        for i, c in enumerate(s):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == op and depth == 0:
                left = s[:i].strip()
                right = s[i+1:].strip()
                if left and right:
                    return [left, right]
        return [s]
    
    def _call_func(self, name, args):
        """调用DSL函数"""
        func_map = {
            'rank': lambda args: self.rank(self._eval_formula(args[0])),
            'scale': lambda args: self.scale(self._eval_formula(args[0])),
            'delta': lambda args: self.delta(*[self._eval_formula(args[0]), int(args[1])]),
            'delay': lambda args: self.delay(*[self._eval_formula(args[0]), int(args[1])]),
            'correlation': lambda args: self.correlation(*[self._eval_formula(args[0]), self._eval_formula(args[1]), int(args[2])]),
            'covariance': lambda args: self.covariance(*[self._eval_formula(args[0]), self._eval_formula(args[1]), int(args[2])]),
            'stddev': lambda args: self.stddev(self._eval_formula(args[0]), int(args[1])),
            'var': lambda args: self.var(self._eval_formula(args[0]), int(args[1])),
            'signedpower': lambda args: self.signed_power(self._eval_formula(args[0]), float(args[1])),
            'ts_argmax': lambda args: self.ts_argmax(self._eval_formula(args[0]), int(args[1])),
            'ts_argmin': lambda args: self.ts_argmin(self._eval_formula(args[0]), int(args[1])),
            'ts_rank': lambda args: self.ts_rank(self._eval_formula(args[0]), int(args[1])),
            'ts_max': lambda args: self.ts_max(self._eval_formula(args[0]), int(args[1])),
            'ts_min': lambda args: self.ts_min(self._eval_formula(args[0]), int(args[1])),
            'sum': lambda args: self.ts_sum(self._eval_formula(args[0]), int(args[1])),
            'decay_linear': lambda args: self.decay_linear(self._eval_formula(args[0]), int(args[1])),
            'sma': lambda args: self.sma(self._eval_formula(args[0]), int(args[1])),
            'sign': lambda args: self.sign(self._eval_formula(args[0])),
            'abs': lambda args: np.abs(self._eval_formula(args[0])),
            'log': lambda args: self.log(self._eval_formula(args[0])),
            'sqrt': lambda args: self.sqrt(self._eval_formula(args[0])),
            'cumprod': lambda args: self.cumprod(self._eval_formula(args[0]), int(args[1]) if len(args) > 1 else 0),
            'shift': lambda args: self.delay(self._eval_formula(args[0]), int(args[1])),
            'ma': lambda args: self.MA(self._eval_formula(args[0]), int(args[1])),
            'std': lambda args: self.STD(self._eval_formula(args[0]), int(args[1])),
            'macd': lambda args: self.MACD(
                self._eval_formula(args[0]), 
                int(args[1]) if len(args) > 1 else 12,
                int(args[2]) if len(args) > 2 else 26),
            'rsi': lambda args: self.RSI(self._eval_formula(args[0]), int(args[1]) if len(args) > 1 else 14),
            'beta': lambda args: self.Beta(self._eval_formula(args[0]), self._eval_formula(args[1]), int(args[2])),
            'corr': lambda args: self.correlation(*[self._eval_formula(args[0]), self._eval_formula(args[1]), int(args[2])]),
            'min': lambda args: np.minimum(self._eval_formula(args[0]), self._eval_formula(args[1])),
            'max': lambda args: np.maximum(self._eval_formula(args[0]), self._eval_formula(args[1])),
        }
        
        if name in func_map:
            try:
                return func_map[name](args)
            except Exception as e:
                return None
        
        return None


# ─────────────── 标准因子计算 (JQ, ZM, QLIB, etc.) ───────────────

def compute_standard_factor(name: str, ohlcv: dict, formula: str) -> Optional[np.ndarray]:
    """计算标准因子(非WQ101 DSL)"""
    try:
        close = np.array(ohlcv['close'], dtype=float)
        open_p = np.array(ohlcv['open'], dtype=float)
        high = np.array(ohlcv['high'], dtype=float)
        low = np.array(ohlcv['low'], dtype=float)
        volume = np.array(ohlcv['volume'], dtype=float)
        n = len(close)
        
        # JQ因子
        if name.startswith('JQ_'):
            return _compute_jq_factor(name, close, open_p, high, low, volume)
        elif name.startswith('ZM_'):
            return _compute_zm_factor(name, close, open_p, high, low, volume)
        elif name.startswith('QLIB_'):
            return _compute_qlib_factor(name, close, open_p, high, low, volume)
        elif name.startswith('ASH_'):
            return _compute_ash_factor(name, close, open_p, high, low, volume)
        elif name.startswith('FF_') or name.startswith('NM_') or name.startswith('ANG_') or name.startswith('SLOAN_'):
            # 学术因子 - 部分需要全市场数据，简化实现
            return _compute_academic_factor(name, close, open_p, high, low, volume)
        elif name.startswith('ASNESS_'):
            return _compute_academic_factor(name, close, open_p, high, low, volume)
        elif name.startswith('CARHART_'):
            return _compute_academic_factor(name, close, open_p, high, low, volume)
        # 其他非WQ101公式
        elif formula and (formula.startswith('JQ_') or formula.startswith('ZM_') or formula.startswith('QLIB_')
                          or formula.startswith('ASH_') or formula.startswith('FF_')
                          or formula.startswith('WQ_') or formula.startswith('ZL_')):
            return _compute_standard_formula(formula, close, open_p, high, low, volume)
        else:
            return None
    except Exception as e:
        return None


def _compute_jq_factor(name, close, open_p, high, low, volume):
    """JQ聚宽因子"""
    ret1 = np.diff(close) / close[:-1]
    
    if name == 'JQ_REV_5D':
        r = pd.Series(close).pct_change(5).values
        return -r
    elif name == 'JQ_REV_1M':
        r = pd.Series(close).pct_change(20).values
        return -r
    elif name == 'JQ_MOM_3M':
        return pd.Series(close).pct_change(60).values
    elif name == 'JQ_MOM_6M':
        return pd.Series(close).pct_change(120).values
    elif name == 'JQ_MOM_12M':
        # 12个月扣除最近1个月
        r12 = pd.Series(close).pct_change(252).values
        r1 = pd.Series(close).pct_change(21).values
        return r12 - r1
    elif name == 'JQ_VOL_20D':
        return pd.Series(ret1).rolling(20).std().values * np.sqrt(252)
    elif name == 'JQ_VOL_60D':
        return pd.Series(ret1).rolling(60).std().values * np.sqrt(252)
    elif name == 'JQ_MAX_RET_60D':
        return pd.Series(ret1).rolling(60).max().values
    elif name == 'JQ_MIN_RET_60D':
        return pd.Series(ret1).rolling(60).min().values
    elif name == 'JQ_SKEW_60D':
        return pd.Series(ret1).rolling(60).skew().values
    elif name == 'JQ_KURT_60D':
        return pd.Series(ret1).rolling(60).kurt().values
    elif name == 'JQ_RSI_14D':
        return WQ101Env.RSI(close, 14)
    elif name == 'JQ_MACD':
        return WQ101Env.MACD(close, 12, 26)
    elif name == 'JQ_BIAS_5D':
        return (close / pd.Series(close).rolling(5).mean() - 1).values
    elif name == 'JQ_BIAS_10D':
        return (close / pd.Series(close).rolling(10).mean() - 1).values
    elif name == 'JQ_CCI_14D':
        tp = (high + low + close) / 3
        sma = pd.Series(tp).rolling(14).mean()
        mad = pd.Series(tp).rolling(14).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        return ((tp - sma) / (0.015 * mad)).values if mad is not None else np.full(n, np.nan)
    elif name == 'JQ_VOLUME_20D_MA':
        v20 = pd.Series(volume).rolling(20).mean()
        v120 = pd.Series(volume).rolling(120).mean()
        return (v20 / v120).values
    elif name == 'JQ_AMIHUD_20D':
        ret = np.abs(np.diff(close) / close[:-1])
        amihud = np.full(n, np.nan)
        for i in range(20, n):
            amihud[i] = np.mean(ret[i-20:i] / (volume[i-20:i] + 1))
        return amihud
    elif name == 'JQ_TURNOVER_20D':
        return pd.Series(volume).rolling(20).mean().values
    elif name == 'JQ_TURNOVER_STD_20D':
        return pd.Series(volume).rolling(20).std().values
    elif name == 'JQ_ILLIQ_RANK':
        return np.full(n, np.nan)  # 需要截面数据
    # 基本面因子 - 非交易日数据不可用
    elif name in ['JQ_RevenueGrowth_Q', 'JQ_ProfitGrowth_Q', 'JQ_AssetGrowth_Y',
                  'JQ_OPE_Y', 'JQ_GROSS_MARGIN', 'JQ_ROE_TTM', 'JQ_ROA_TTM',
                  'JQ_ACCRUAL', 'JQ_LEVERAGE', 'JQ_CURRENT_RATIO',
                  'JQ_EP_TTM', 'JQ_BP_LF', 'JQ_CFP_TTM', 'JQ_SP_TTM',
                  'JQ_FCFP', 'JQ_DIVIDEND_YIELD']:
        return np.full(n, np.nan)  # 需要财务数据
    
    return None


def _compute_zm_factor(name, close, open_p, high, low, volume):
    """ZM子沐K线形态因子"""
    n = len(close)
    result = np.full(n, np.nan)
    
    body = close - open_p
    body_abs = np.abs(body)
    hl = high - low
    
    if name == 'ZM_CDL_BODY':
        safe_hl = np.where(hl == 0, 1, hl)
        return body_abs / safe_hl
    elif name == 'ZM_CDL_UPSHADOW':
        up = high - np.maximum(close, open_p)
        safe_hl = np.where(hl == 0, 1, hl)
        return up / safe_hl
    elif name == 'ZM_CDL_DOWNSHADOW':
        down = np.minimum(close, open_p) - low
        safe_hl = np.where(hl == 0, 1, hl)
        return down / safe_hl
    elif name == 'ZM_CDL_MARUBOZU':
        body_ratio = body_abs / np.where(hl == 0, 1, hl)
        return (body_ratio > 0.95).astype(float)
    elif name == 'ZM_CDL_HAMMER':
        # 下影线 > 实体2倍 且 上影线很小
        lower = np.minimum(close, open_p) - low
        upper = high - np.maximum(close, open_p)
        return np.where((lower > body_abs * 2) & (upper < body_abs * 0.5), 1.0, 0.0)
    elif name == 'ZM_CDL_DOJI':
        safe_hl = np.where(hl == 0, 1, hl)
        return (body_abs / safe_hl < 0.02).astype(float)
    elif name == 'ZM_MA5_10_CROSS':
        ma5 = pd.Series(close).rolling(5).mean()
        ma10 = pd.Series(close).rolling(10).mean()
        return ((ma5 - ma10) / ma5).values
    elif name == 'ZM_MA10_20_CROSS':
        ma10 = pd.Series(close).rolling(10).mean()
        ma20 = pd.Series(close).rolling(20).mean()
        return ((ma10 - ma20) / ma10).values
    elif name == 'ZM_MA5_20_CROSS':
        ma5 = pd.Series(close).rolling(5).mean()
        ma20 = pd.Series(close).rolling(20).mean()
        return ((ma5 - ma20) / ma5).values
    elif name == 'ZM_MA_ARRANGE':
        ma5 = pd.Series(close).rolling(5).mean()
        ma10 = pd.Series(close).rolling(10).mean()
        ma20 = pd.Series(close).rolling(20).mean()
        return ((ma5 > ma10) & (ma10 > ma20)).astype(float)
    elif name == 'ZM_MA_DISTANCE':
        ma20 = pd.Series(close).rolling(20).mean()
        return ((close - ma20) / ma20).values
    elif name == 'ZM_MA_SLOPE_5':
        ma5 = pd.Series(close).rolling(5).mean()
        ma5_prev = pd.Series(ma5).shift(1)
        return ((ma5 - ma5_prev) / ma5_prev).values
    elif name == 'ZM_MA_SLOPE_20':
        ma20 = pd.Series(close).rolling(20).mean()
        ma20_prev = pd.Series(ma20).shift(1)
        return ((ma20 - ma20_prev) / ma20_prev).values
    elif name == 'ZM_BOLL_POS':
        ma20 = pd.Series(close).rolling(20).mean()
        std20 = pd.Series(close).rolling(20).std()
        upper = ma20 + 2 * std20
        lower = ma20 - 2 * std20
        safe_range = upper - lower
        safe_range = np.where(safe_range == 0, 1, safe_range)
        return ((close - lower) / safe_range).values
    elif name == 'ZM_BOLL_WIDTH':
        ma20 = pd.Series(close).rolling(20).mean()
        std20 = pd.Series(close).rolling(20).std()
        width = 4 * std20
        safe_ma20 = np.where(ma20 == 0, 1, ma20)
        return (width / safe_ma20).values
    elif name == 'ZM_BOLL_BREAK_HIGH':
        ma20 = pd.Series(close).rolling(20).mean()
        std20 = pd.Series(close).rolling(20).std()
        upper = ma20 + 2 * std20
        return (close > upper).astype(float)
    elif name == 'ZM_BOLL_BREAK_LOW':
        ma20 = pd.Series(close).rolling(20).mean()
        std20 = pd.Series(close).rolling(20).std()
        lower = ma20 - 2 * std20
        return (close < lower).astype(float)
    elif name == 'ZM_VOL_SURGE':
        v5 = pd.Series(volume).rolling(5).mean()
        return (volume / v5 - 1).values
    elif name == 'ZM_VOL_SHRINK':
        v5 = pd.Series(volume).rolling(5).mean()
        return (1 - volume / v5).values
    elif name == 'ZM_VOL_PRICE_CONFIRM':
        price_dir = np.sign(body)
        return price_dir * volume
    elif name == 'ZM_VOL_PRICE_DIVERGE':
        price_dir = np.sign(body)
        return np.where(price_dir > 0, -volume, 0)  # 价涨量缩 = 背离
    elif name == 'ZM_VOL_MA5':
        v5 = pd.Series(volume).rolling(5).mean()
        v20 = pd.Series(volume).rolling(20).mean()
        return (v5 / v20).values
    elif name == 'ZM_VOL_ACCUM':
        clv = ((close - low) - (high - close)) / (high - low + 1e-10)
        return (clv * volume).values
    elif name == 'ZM_HAMMER_REVERSAL':
        lower = np.minimum(close, open_p) - low
        upper = high - np.maximum(close, open_p)
        hammer = (lower > body_abs * 2) & (upper < body_abs * 0.5)
        v5 = pd.Series(volume).rolling(5).mean().values
        low_vol = volume < v5 * 0.7
        return (hammer & low_vol).astype(float)
    elif name == 'ZM_3WHITE_SOLDIERS':
        if n < 3: return result
        bull = close > open_p
        for i in range(2, n):
            result[i] = 1.0 if (bull[i] and bull[i-1] and bull[i-2] and
                                close[i] > close[i-1] > close[i-2]) else 0.0
        return result
    elif name == 'ZM_3BLACK_CROWS':
        if n < 3: return result
        bear = close < open_p
        for i in range(2, n):
            result[i] = 1.0 if (bear[i] and bear[i-1] and bear[i-2] and
                                close[i] < close[i-1] < close[i-2]) else 0.0
        return result
    
    return None


def _compute_qlib_factor(name, close, open_p, high, low, volume):
    """QLib基础因子"""
    ret1 = np.diff(close) / close[:-1]
    
    if name == 'QLIB_ROC_5':
        return pd.Series(close).pct_change(5).values
    elif name == 'QLIB_ROC_10':
        return pd.Series(close).pct_change(10).values
    elif name == 'QLIB_ROC_20':
        return pd.Series(close).pct_change(20).values
    elif name == 'QLIB_ROC_60':
        return pd.Series(close).pct_change(60).values
    elif name == 'QLIB_MA_5':
        return pd.Series(close).rolling(5).mean().values
    elif name == 'QLIB_MA_10':
        return pd.Series(close).rolling(10).mean().values
    elif name == 'QLIB_MA_20':
        return pd.Series(close).rolling(20).mean().values
    elif name == 'QLIB_STD_5':
        return pd.Series(ret1).rolling(5).std().values
    elif name == 'QLIB_STD_10':
        return pd.Series(ret1).rolling(10).std().values
    elif name == 'QLIB_STD_20':
        return pd.Series(ret1).rolling(20).std().values
    elif name == 'QLIB_RSI_14':
        return WQ101Env.RSI(close, 14).values if hasattr(WQ101Env.RSI(close, 14), 'values') else WQ101Env.RSI(close, 14)
    elif name == 'QLIB_RSI':
        return WQ101Env.RSI(close, 14)
    elif name == 'QLIB_VOL_MA_5':
        return (volume / pd.Series(volume).rolling(5).mean()).values
    elif name == 'QLIB_VOL_STD_5':
        v_ma = pd.Series(volume).rolling(5).mean()
        v_std = pd.Series(volume).rolling(5).std()
        return (v_std / v_ma).values
    elif name == 'QLIB_HIGH_LOW_RATIO':
        safe_close = np.where(close == 0, 1, close)
        return (high - low) / safe_close
    elif name == 'QLIB_VOL_MA5':
        return (volume / pd.Series(volume).rolling(5).mean()).values
    elif name == 'QLIB_MACD':
        return WQ101Env.MACD(close, 12, 26)
    elif name == 'QLIB_BOLL':
        ma20 = pd.Series(close).rolling(20).mean()
        std20 = pd.Series(close).rolling(20).std()
        safe_std20 = np.where(std20 == 0, 1, std20)
        return ((close - ma20) / safe_std20).values
    elif name == 'QLIB_MA5_MA20':
        ma5 = pd.Series(close).rolling(5).mean()
        ma20 = pd.Series(close).rolling(20).mean()
        safe_ma20 = np.where(ma20 == 0, 1, ma20)
        return (ma5 / ma20 - 1).values
    elif name == 'QLIB_PRICE_VOL_CORR_5':
        c, v = pd.Series(close), pd.Series(volume)
        return c.rolling(5).corr(v).values
    elif name == 'QLIB_RESIDUAL_20':
        ma20 = pd.Series(close).rolling(20).mean()
        return (close - ma20).values
    elif name == 'QLIB_OPEN_CLOSE':
        return (close - open_p) / np.where(np.abs(close - open_p) == 0, 1, np.abs(close - open_p))
    
    return None


def _compute_ash_factor(name, close, open_p, high, low, volume):
    """ASH A股特色因子 (简化版, 部分需外部数据)"""
    n = len(close)
    result = np.full(n, np.nan)
    
    if name == 'ASH_LIMITUP':
        return np.full(n, np.nan)  # 需要涨停价
    elif name == 'ASH_LIMITDOWN':
        return np.full(n, np.nan)
    elif name == 'ASH_LIMITUP_STRENGTH':
        return np.full(n, np.nan)
    elif name == 'ASH_ZDT_HIGH':
        return np.full(n, np.nan)
    elif name == 'ASH_PLATE_LIFT':
        return np.full(n, np.nan)  # 需要板块数据
    elif name == 'ASH_ST_ALERT':
        return np.full(n, 0)  # 简化: 默认非ST
    elif name == 'ASH_CONCEPT':
        return np.full(n, np.nan)
    elif name == 'ASH_HOT_MONEY':
        return np.full(n, np.nan)
    elif name == 'ASH_SEASONALITY':
        return np.full(n, np.nan)
    elif name == 'ASH_WEEKDAY':
        # 周内效应: 星期五尾盘=1, 周一=0, 其他=0.5
        import datetime
        from datetime import datetime as dt
        weekday = np.full(n, 0.5)
        # 简化: 无法获取日期信息，跳过
        return weekday
    elif name == 'ASH_MAJOR_HOLD':
        return np.full(n, np.nan)
    elif name == 'ASH_PREMIUM_REFUND':
        return np.full(n, np.nan)
    elif name == 'ASH_IPO_DILUTION':
        return np.full(n, np.nan)
    elif name == 'ASH_PLEDGE_RISK':
        return np.full(n, np.nan)
    elif name == 'ASH_SHARE_TRANSFER':
        return np.full(n, np.nan)
    
    return None


def _compute_academic_factor(name, close, open_p, high, low, volume):
    """学术因子 (简化版)"""
    n = len(close)
    ret1 = np.diff(close) / close[:-1]
    
    if name == 'FF_MKT_EXCESS':
        return pd.Series(ret1).values  # 近似: 个股超额收益
    elif name == 'CARHART_MOM':
        r12 = pd.Series(close).pct_change(252).values
        r1 = pd.Series(close).pct_change(21).values
        return (r12 - r1).values
    elif name == 'ANG_LOW_VOL':
        r_std = pd.Series(ret1).rolling(60).std().values
        return -r_std  # 低波
    elif name == 'SLOAN_ACCRUAL':
        return np.full(n, np.nan)  # 需要财务数据
    elif name.startswith('FF_') or name.startswith('NM_') or name.startswith('ASNESS_'):
        return np.full(n, np.nan)
    
    return None


def _compute_standard_formula(formula, close, open_p, high, low, volume):
    """计算 '公式名' 格式的因子"""
    # 纯公式名的映射
    name = formula.strip()
    
    all_factors = {}
    for prefix_funcs in [
        _compute_jq_factor(name, close, open_p, high, low, volume),
        _compute_zm_factor(name, close, open_p, high, low, volume),
        _compute_qlib_factor(name, close, open_p, high, low, volume),
        _compute_ash_factor(name, close, open_p, high, low, volume),
        _compute_academic_factor(name, close, open_p, high, low, volume),
    ]:
        if prefix_funcs is not None:
            return prefix_funcs
    
    return None


# ─────────────── IC验证引擎 ───────────────

class FactorValidator:
    """因子有效性验证引擎"""
    
    def __init__(self):
        self.results = {}  # {name: ic_data}
        self._load_library()
    
    def _load_library(self):
        with open(FACTOR_LIB_PATH) as f:
            self.lib = json.load(f)
        print(f"[validator] 加载 {len(self.lib)} 个因子")
    
    def compute_factor_value(self, name: str, ohlcv: dict) -> Optional[np.ndarray]:
        """计算因子值"""
        close = np.array(ohlcv['close'], dtype=float)
        open_p = np.array(ohlcv['open'], dtype=float)
        high = np.array(ohlcv['high'], dtype=float)
        low = np.array(ohlcv['low'], dtype=float)
        volume = np.array(ohlcv['volume'], dtype=float)
        n = len(close)
        
        fdef = self.lib.get(name)
        if not fdef:
            return None
        
        formula = fdef.get('formula', '')
        
        # 1. 先试标准因子计算器
        result = compute_standard_factor(name, ohlcv, formula)
        if result is not None:
            return result
        
        # 2. 再试WQ101 DSL
        try:
            returns = np.diff(np.log(close))
            adv20 = pd.Series(volume).rolling(20).mean().values
            env = WQ101Env(open_p, high, low, close, volume, returns, adv20)
            result = env.eval(formula)
            if result is not None and not np.all(np.isnan(result)):
                return result
        except Exception:
            pass
        
        return None
    
    def compute_ic(self, factor_values: np.ndarray, forward_returns: np.ndarray) -> dict:
        """计算IC值"""
        valid = ~(np.isnan(factor_values) | np.isnan(forward_returns))
        valid_count = valid.sum()
        
        if valid_count < MIN_DATA_POINTS:
            return {'rank_ic': 0, 'pearson_ic': 0, 'ic_std': 1, 't_stat': 0, 'n': 0}
        
        fv = factor_values[valid]
        fr = forward_returns[valid]
        
        # Rank IC (Spearman)
        rank_ic, p_value = spearmanr(fv, fr)
        
        # Pearson IC
        pearson_ic, _ = pearsonr(fv, fr)
        
        # 分位数收益率差 (top 20% - bottom 20%)
        nq = len(fv) // 5
        if nq >= 3:
            sorted_idx = np.argsort(fv)
            top_ret = np.mean(fr[sorted_idx[-nq:]])
            bot_ret = np.mean(fr[sorted_idx[:nq]])
            quintile_spread = top_ret - bot_ret
        else:
            quintile_spread = 0
        
        # 命中率 (方向正确率)
        hit_rate = np.mean(np.sign(fv) == np.sign(fr))
        
        # IC_IR (IC均值 / IC标准差) — 用滚动IC
        if valid_count > 30:
            ic_history = []
            for i in range(20, valid_count - 5):
                sub_fv = fv[i-20:i+5]
                sub_fr = fr[i-20:i+5]
                ic, _ = spearmanr(sub_fv, sub_fr)
                ic_history.append(ic if not np.isnan(ic) else 0)
            ic_ir = np.mean(ic_history) / (np.std(ic_history) + 1e-10) if ic_history else 0
        else:
            ic_ir = 0
        
        return {
            'rank_ic': float(rank_ic) if not np.isnan(rank_ic) else 0,
            'pearson_ic': float(pearson_ic) if not np.isnan(pearson_ic) else 0,
            'ic_std': float(np.std(fv)),
            't_stat': float(rank_ic * np.sqrt(valid_count)) if not np.isnan(rank_ic) else 0,
            'n': int(valid_count),
            'hit_rate': float(hit_rate),
            'quintile_spread': float(quintile_spread),
            'ic_ir': float(ic_ir),
        }
    
    def validate_all(self, ohlcv_data: Dict[str, dict]) -> Dict[str, dict]:
        """全量验证所有因子"""
        results = {}
        
        # 每只股票的K线
        stock_codes = list(ohlcv_data.keys())
        print(f"[validator] 验证 {len(self.lib)} 个因子 × {len(stock_codes)} 只股票")
        
        for name, fdef in self.lib.items():
            all_ics = []
            all_forward_rets = []
            valid_codes = 0
            error_msg = None
            
            for code, ohlcv in ohlcv_data.items():
                # 计算因子值
                fv = self.compute_factor_value(name, ohlcv)
                if fv is None or np.all(np.isnan(fv)):
                    continue
                
                # 计算未来收益 (forward 1日)
                close = np.array(ohlcv['close'], dtype=float)
                forward_ret = np.diff(close) / close[:-1]
                
                # 对齐 (因子值可能是full length或diff -1)
                min_len = min(len(fv), len(forward_ret))
                if min_len < MIN_DATA_POINTS:
                    continue
                
                fv_aligned = fv[:min_len]
                fr_aligned = forward_ret[:min_len]
                
                # 对该股票计算IC
                ic = self.compute_ic(fv_aligned, fr_aligned)
                if ic['n'] > 0:
                    all_ics.append(ic['rank_ic'])
                    all_forward_rets.extend(fr_aligned[~np.isnan(fv_aligned)].tolist())
                    valid_codes += 1
            
            # 汇总
            if all_ics:
                avg_ic = np.mean(all_ics)
                ic_std = np.std(all_ics)
                tstat = avg_ic * np.sqrt(len(all_ics)) / (ic_std + 1e-10)
                
                results[name] = {
                    'avg_rank_ic': float(avg_ic),
                    'ic_std_cross': float(ic_std),
                    't_stat_cross': float(tstat),
                    'valid_stocks': valid_codes,
                    'category': fdef.get('category', 'unknown'),
                    'source': fdef.get('source', ''),
                    'formula': fdef.get('formula', '')[:60],
                    'passed': abs(avg_ic) >= MIN_IC_THRESHOLD,
                    'good': abs(avg_ic) >= GOOD_IC_THRESHOLD,
                    'excellent': abs(avg_ic) >= EXCELLENT_IC_THRESHOLD,
                }
            else:
                results[name] = {
                    'avg_rank_ic': 0,
                    'ic_std_cross': 0,
                    't_stat_cross': 0,
                    'valid_stocks': 0,
                    'category': fdef.get('category', 'unknown'),
                    'source': fdef.get('source', ''),
                    'formula': fdef.get('formula', '')[:60],
                    'passed': False,
                    'good': False,
                    'excellent': False,
                    'note': '无法计算',
                }
        
        self.results = results
        return results
    
    def print_report(self, top_n=30):
        """打印验证报告"""
        if not self.results:
            print("[validator] 无验证结果，请先运行 validate_all()")
            return
        
        # 按IC排序
        sorted_factors = sorted(self.results.items(), 
                                key=lambda x: abs(x[1]['avg_rank_ic']), reverse=True)
        
        total = len(sorted_factors)
        passed = sum(1 for r in sorted_factors if r[1]['passed'])
        good = sum(1 for r in sorted_factors if r[1]['good'])
        excellent = sum(1 for r in sorted_factors if r[1]['excellent'])
        cannot = sum(1 for r in sorted_factors if r[1]['valid_stocks'] == 0)
        
        print("=" * 70)
        print(f"📊 因子IC验证报告")
        print(f"   验证 {total} 个因子 | ✅通过 {passed} | 🟢好 {good} | 🏆优秀 {excellent} | ❌无法计算 {cannot}")
        print("=" * 70)
        
        for cat in ['momentum', 'volume', 'risk', 'price', 'trend', 'volatility', 'value', 
                     'quality', 'sentiment', 'reversal', 'liquidity', 'volume_trend',
                     'price_volume', 'volume_pattern', 'growth', 'market', 'size', 
                     '技术', '资金', '基本面', '情绪', '模型', '事件驱动', '其他', 'unknown']:
            cat_factors = [(n, r) for n, r in sorted_factors 
                          if r['category'] == cat and r['valid_stocks'] > 0]
            if not cat_factors:
                continue
            
            top_cat = sorted(cat_factors, key=lambda x: abs(x[1]['avg_rank_ic']), reverse=True)[:5]
            print(f"\n📁 {cat} ({len(cat_factors)}个可计算)")
            for name, r in top_cat:
                ic = r['avg_rank_ic']
                if abs(ic) >= EXCELLENT_IC_THRESHOLD:
                    badge = "🏆"
                elif abs(ic) >= GOOD_IC_THRESHOLD:
                    badge = "🟢"
                elif abs(ic) >= MIN_IC_THRESHOLD:
                    badge = "✅"
                else:
                    badge = "⬜"
                stocks = r['valid_stocks']
                ic_str = f"{ic:+.4f}"
                print(f"  {badge} {name:<30} IC={ic_str:>8}  stocks={stocks:>2}  IR={r['ic_std_cross']:+.2f}  n={r['n'] if r.get('n') else '-'}")
        
        print()
        print("=" * 70)
        print("🏆 最佳因子 Top 10")
        print("=" * 70)
        top10 = sorted_factors[:top_n]
        for i, (name, r) in enumerate(top10):
            if r['valid_stocks'] == 0:
                continue
            badge = "🏆" if r['excellent'] else "🟢" if r['good'] else "✅" if r['passed'] else "⬜"
            print(f"  {badge} {name:<30} IC={r['avg_rank_ic']:+.4f}  stk={r['valid_stocks']:>2}  src={r['source']:<8}")
            if i >= top_n:
                break
    
    def update_library(self, output_path=None):
        """根据验证结果更新因子库"""
        if not self.results:
            print("[validator] 无验证结果")
            return
        
        updated = 0
        for name, r in self.results.items():
            if name in self.lib:
                self.lib[name]['ic'] = round(r['avg_rank_ic'], 4)
                self.lib[name]['ic_ir'] = round(r['ic_std_cross'], 4)
                self.lib[name]['t_stat'] = round(r['t_stat_cross'], 3)
                self.lib[name]['valid_stocks'] = r['valid_stocks']
                self.lib[name]['validated_at'] = datetime.now().isoformat()
                updated += 1
        
        path = output_path or FACTOR_LIB_PATH
        with open(path, 'w') as f:
            json.dump(self.lib, f, ensure_ascii=False, indent=2)
        print(f"[validator] 已更新 {updated}/{len(self.lib)} 个因子的IC值 → {path}")


# ─────────────── CLI ───────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="因子有效性验证引擎")
    parser.add_argument("--run", action="store_true", help="全量验证并更新因子库")
    parser.add_argument("--report", action="store_true", help="只查看报告")
    parser.add_argument("--factor", type=str, help="验证单个因子")
    
    args = parser.parse_args()
    
    validator = FactorValidator()
    
    # 获取数据
    print("[validator] 获取K线数据...")
    from market_monitor import PORTFOLIO, fetch_kline
    
    ohlcv_data = {}
    for code in PORTFOLIO:
        klines = fetch_kline(code)
        if klines and len(klines) > 20:
            ohlcv_data[code] = {
                'open': [k['open'] for k in klines],
                'high': [k['high'] for k in klines],
                'low': [k['low'] for k in klines],
                'close': [k['close'] for k in klines],
                'volume': [k['volume'] for k in klines],
            }
    print(f"[validator] 获取 {len(ohlcv_data)} 只股票K线")
    
    if args.factor:
        # 验证单个因子
        code = list(ohlcv_data.keys())[0]
        fv = validator.compute_factor_value(args.factor, ohlcv_data[code])
        if fv is not None:
            print(f"  {args.factor}: {len(fv)} 个值, nan={np.isnan(fv).sum()}")
        else:
            print(f"  {args.factor}: 无法计算")
        import sys; sys.exit(0)
    
    if args.run or args.report:
        if args.run:
            results = validator.validate_all(ohlcv_data)
            validator.print_report()
            validator.update_library()
        else:
            # 尝试加载已有结果
            if os.path.exists(VALIDATION_RESULTS_PATH):
                with open(VALIDATION_RESULTS_PATH) as f:
                    validator.results = json.load(f)
                validator.print_report()
            else:
                print("[validator] 无缓存结果, 运行 --run")
