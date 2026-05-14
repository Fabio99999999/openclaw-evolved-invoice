"""
算法交易执行器 — VWAP + 动态切片
文献参考: 《算法交易实战》Sec.7.4
设计: 框架级实现 (无券商账户, 生成信号+模拟执行)
"""
import math, random
from typing import List, Dict, Optional
from datetime import datetime, time

class VWAPExecutor:
    """
    VWAP算法交易执行器
    功能: 计算最优交易路径 + 动态切片 + 冲击成本估算
    """
    
    def __init__(self, initial_capital: float = 0):
        self.capital = initial_capital
        self.trades = []
    
    def calc_vwap(self, volumes: List[float], prices: List[float]) -> float:
        """计算VWAP"""
        if not volumes or not prices or len(volumes) != len(prices):
            return 0
        total_vol = sum(volumes)
        if total_vol == 0:
            return 0
        return sum(v * p for v, p in zip(volumes, prices)) / total_vol
    
    def optimal_slices(self, order_size: float, 
                        volume_profile: List[float],
                        volatility: float,
                        n_slices: int = 24) -> List[float]:
        """
        动态切片算法
        根据历史成交量分布，智能分配每笔交易量
        """
        if not volume_profile or sum(volume_profile) == 0:
            # 均匀分配
            return [order_size / n_slices] * n_slices
        
        # 归一化成交量分布
        vol_profile = np.array(volume_profile)
        vol_pct = vol_profile / vol_profile.sum()
        
        # 波动调整: 高波动时段减少交易量
        volatility_adj = 1.0 / (1.0 + volatility * 10)
        vol_pct = vol_pct * (1 - volatility_adj * 0.3)
        vol_pct = vol_pct / vol_pct.sum()
        
        # 切片
        slices = []
        remaining = order_size
        for i, pct in enumerate(vol_pct[:n_slices - 1]):
            slice_size = order_size * pct
            slices.append(slice_size)
            remaining -= slice_size
        slices.append(remaining)
        
        return slices
    
    def impact_cost(self, order_size: float, avg_daily_vol: float, 
                     price: float, urgency: float = 0.5) -> Dict:
        """
        冲击成本估算
        Almgren-Chriss 模型简化版
        """
        participation = order_size / (avg_daily_vol + 1e-8)
        
        # 永久冲击
        perm_impact = 0.01 * math.sqrt(participation) * price
        # 暂时冲击
        temp_impact = 0.005 * (participation ** 0.6) * price * (1 + urgency)
        # 总成本
        total_cost = perm_impact + temp_impact
        
        return {
            "participation_rate": participation,
            "permanent_impact": perm_impact,
            "temporary_impact": temp_impact,
            "total_cost": total_cost,
            "cost_per_share": total_cost / (order_size + 1e-8)
        }


