"""
绩效归因引擎 — 因子贡献度分析
文献参考: 《超额收益归因模型》JPM 2025
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

class PerformanceAttribution:
    """
    绩效归因: R_α = Σ(w_i · IC_i · σ_i) + λ·T_timing + ε
    """
    
    def __init__(self):
        self.factor_contribs = defaultdict(float)
        self.timing_contrib = 0.0
        self.residual = 0.0
    
    def decompose(self, returns: List[float], 
                   factor_exposures: Dict[str, List[float]],
                   factor_ic: Dict[str, float],
                   factor_weights: Dict[str, float]) -> Dict:
        """
        分解收益为因子贡献
        R_alpha = Σ(weight_i * IC_i * sigma_i) + timing + residual
        """
        total_return = np.sum(returns)
        
        explained = 0.0
        details = {}
        
        for factor_name, exposures in factor_exposures.items():
            w = factor_weights.get(factor_name, 0)
            ic = factor_ic.get(factor_name, 0)
            sigma = np.std(exposures) if len(exposures) > 1 else 0
            
            contribution = w * ic * sigma * len(returns)
            explained += contribution
            details[factor_name] = {
                "weight": w,
                "ic": ic,
                "sigma": sigma,
                "contribution": contribution,
                "pct": 0  # will calc after
            }
        
        # 计算占比
        for name in details:
            if abs(explained) > 1e-8:
                details[name]["pct"] = details[name]["contribution"] / explained * 100
        
        self.timing_contrib = total_return * 0.05  # 简化: 5%归因于择时
        self.residual = total_return - explained - self.timing_contrib
        
        return {
            "total_return": total_return,
            "explained_by_factors": explained,
            "explain_ratio": abs(explained / (total_return + 1e-8)),
            "timing_contribution": self.timing_contrib,
            "residual": self.residual,
            "factor_details": details
        }
    
    def format_report(self, result: Dict) -> str:
        """格式化归因报告"""
        lines = ["📊 收益归因分析"]
        lines.append(f"总收益: {result['total_return']:+.2%}")
        lines.append(f"因子解释: {result['explain_ratio']:.1%}")
        lines.append(f"")
        lines.append("因子贡献明细:")
        for name, detail in sorted(
            result['factor_details'].items(), 
            key=lambda x: abs(x[1]['contribution']), 
            reverse=True
        )[:8]:
            bar = "█" * int(abs(detail['pct'])) + "░" * (20 - int(abs(detail['pct'])))
            sign = "+" if detail['contribution'] >= 0 else ""
            lines.append(f"  {name:<12} {bar} {sign}{detail['contribution']:+.2%} ({detail['pct']:.0f}%)")
        return "\n".join(lines)

