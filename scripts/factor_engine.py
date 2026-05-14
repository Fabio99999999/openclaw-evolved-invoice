"""
因子工程引擎 v1 — 因子监管 + 自动因子合成
文献参考: 《因子投资：方法与实践》Sec.6 / 《阿尔法因子工程》(WorldQuant)
"""
import os, json, math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

FACTOR_LIBRARY_PATH = os.path.expanduser("~/.openclaw/data/factor_library.json")

class FactorEngine:
    """
    因子工程核心引擎
    功能: 因子计算 → IC评估 → 因子回收/重组
    """
    
    def __init__(self):
        self.factors = {}      # {name: factor_def}
        self.ic_history = {}   # {name: [ic_values]}
        self.factor_count = 0
    
    def load_from_library(self):
        """从因子挖掘库(factor_library.json)加载因子"""
        if not os.path.exists(FACTOR_LIBRARY_PATH):
            return 0
        try:
            with open(FACTOR_LIBRARY_PATH) as f:
                lib = json.load(f)
            
            # 分类权重上限 (同类别因子平均分配该上限)
            category_max_weight = {
                "momentum": 0.18, "volume": 0.16, "trend": 0.12,
                "volatility": 0.10, "risk": 0.08, "quality": 0.10,
                "value": 0.08, "reversal": 0.08, "price": 0.06,
                "volume_trend": 0.06, "price_volume": 0.05,
                "sentiment": 0.08, "liquidity": 0.06,
                "growth": 0.06, "volume_pattern": 0.04,
                "market": 0.03, "size": 0.03,
            }
            
            # 先按类别分组
            cat_groups = {}
            for name, fdef in lib.items():
                if fdef.get("status") == "active" and name not in self.factors:
                    cat = fdef.get("category", "unknown")
                    cat_groups.setdefault(cat, []).append(name)
            
            count = 0
            for cat, names in cat_groups.items():
                max_w = category_max_weight.get(cat, 0.05)
                per_factor = min(max(0.008, max_w / max(1, len(names))), 0.05)
                
                for name in names:
                    fdef = lib[name]
                    self.factors[name] = {
                        "name": name,
                        "category": cat,
                        "weight": round(per_factor, 4),
                        "compute_fn": None,
                        "data_sources": [fdef.get("source", "library")],
                        "ic": fdef.get("ic", 0.0) or 0.0,
                        "half_life": 90,
                        "active": True,
                        "registered_at": fdef.get("added_at", datetime.now().isoformat()),
                        "source": fdef.get("source", ""),
                        "ref": fdef.get("ref", ""),
                        "mined": True,
                    }
                    self.ic_history[name] = []
                    count += 1
            
            self.factor_count = len(self.factors)
            return count
        except Exception as e:
            print(f"[factor_engine] 加载因子库失败: {e}")
            return 0
    
    def register_factor(self, name: str, category: str, weight: float, 
                         compute_fn=None, data_sources: List[str] = None):
        """注册一个新因子"""
        self.factors[name] = {
            "name": name,
            "category": category,
            "weight": weight,
            "compute_fn": compute_fn,
            "data_sources": data_sources or [],
            "ic": 0.0,
            "half_life": 90,       # 因子半衰期(天)
            "active": True,
            "registered_at": datetime.now().isoformat()
        }
        self.ic_history[name] = []
        self.factor_count += 1
    
    def register_core_factors(self):
        """注册核心因子 (来自文献)"""
        # ===== 技术因子 (权重 25%) =====
        for name, w in [
            ("均线趋势", 0.05), ("MACD背离", 0.04), ("布林带挤压", 0.04),
            ("RSI超买超卖", 0.03), ("成交量异动", 0.03), ("KDJ金叉死叉", 0.03),
            ("WR威廉指标", 0.01), ("OBV能量潮", 0.01), ("ATR波动率", 0.01)
        ]:
            self.register_factor(name, "技术", w)
        
        # ===== 资金因子 (权重 20%) =====
        for name, w in [
            ("主力资金净流入", 0.05), ("北向资金", 0.04), ("大单占比", 0.04),
            ("散户动向", 0.03), ("融资融券余额", 0.02), ("大宗交易折溢价", 0.02)
        ]:
            self.register_factor(name, "资金", w)
        
        # ===== 基本面因子 (权重 18%) =====
        for name, w in [
            ("PE分位数", 0.03), ("PB分位数", 0.02), ("ROE", 0.03),
            ("营收增速", 0.03), ("净利润增速", 0.04), ("毛利率趋势", 0.02),
            ("资产负债率", 0.01)
        ]:
            self.register_factor(name, "基本面", w)
        
        # ===== 市场情绪 (权重 12%) =====
        for name, w in [
            ("换手率异常", 0.03), ("封板率", 0.02), ("龙虎榜", 0.02),
            ("舆情指数", 0.03), ("期权PCR", 0.02)
        ]:
            self.register_factor(name, "情绪", w)
        
        # ===== 量化模型 (权重 10%) =====
        for name, w in [
            ("LightGBM预测", 0.04), ("GRU时序", 0.03), ("XGBoost集成", 0.03)
        ]:
            self.register_factor(name, "模型", w)
        
        # ===== 文献新增因子 (09:21 优化) =====
        self.register_factor("机构调研密度", "事件驱动", 0.08)
        self.register_factor("股东增减持链", "事件驱动", 0.05)
        self.register_factor("业绩超预期概率", "基本面", 0.05)
        self.register_factor("实控人变更影响", "事件驱动", 0.04)
        self.register_factor("产业链位置变化", "基本面", 0.03)
        
        self.register_factor("板块轮动强度", "情绪", 0.02)
        self.register_factor("融资买入占比", "资金", 0.02)
        self.register_factor("限售解禁冲击", "事件驱动", 0.02)
        self.register_factor("股权质押风险", "事件驱动", 0.02)
        self.register_factor("商誉减值风险", "基本面", 0.01)
        
        # ===== 2026-05-05 盘中监控升级新增因子 =====
        # 文献: WorldQuant Alpha#3 (量价背离), 《因子投资》p.158
        self.register_factor("量价背离", "技术", 0.03)
        # 文献: 《算法交易》Kissell Ch.7 — VWAP偏离
        self.register_factor("VWAP偏离度", "技术", 0.02)
        # 文献: 平头哥短线系统 — 市场温度
        self.register_factor("市场温度", "情绪", 0.03)
        # 文献: BigQuant多因子 — 板块联动效应
        self.register_factor("板块情绪", "情绪", 0.02)
        # 文献: WorldQuant Alpha#50 — 涨跌停效应
        self.register_factor("涨跌停信号", "情绪", 0.02)
        # 增强: 北向资金因子权重提升
        for f in self.factors.values():
            if f["name"] == "北向资金":
                f["weight"] = 0.05
                break
        # 新增: 全市场融资融券方向
        self.register_factor("融资融券方向", "资金", 0.02)
        # 新增: 概念热点热度
        self.register_factor("概念热点热度", "资金", 0.02)
    
    def get_total_score(self, factor_scores: Dict[str, float]) -> Tuple[float, Dict]:
        """
        综合评分 (0-100)
        使用加权求和 + 非线性修正
        """
        raw_score = 0.0
        details = {}
        
        for name, score in factor_scores.items():
            if name in self.factors and self.factors[name]["active"]:
                w = self.factors[name]["weight"]
                raw_score += w * score
                details[name] = {"score": score, "weight": w, "contribution": w * score}
        
        # 非线性修正: 机构调研密度 >80 时放大12%
        if "机构调研密度" in factor_scores and factor_scores["机构调研密度"] > 80:
            raw_score *= 1.12
        
        # 股东链断裂惩罚
        if "股东增减持链" in factor_scores and factor_scores["股东增减持链"] < 20:
            raw_score -= 25
        
        normalized = max(0, min(100, raw_score))
        
        return normalized, details
    
    def get_factor_count(self) -> int:
        return len([f for f in self.factors.values() if f["active"]])
    
    def list_factors(self, category: str = None) -> List[Dict]:
        if category:
            return [f for f in self.factors.values() if f["category"] == category and f["active"]]
        return [f for f in self.factors.values() if f["active"]]
    
    def summary(self) -> dict:
        cats = {}
        for f in self.factors.values():
            if not f["active"]: continue
            cats.setdefault(f["category"], {"count": 0, "weight": 0})
            cats[f["category"]]["count"] += 1
            cats[f["category"]]["weight"] += f["weight"]
        return {
            "total_factors": self.get_factor_count(),
            "categories": cats,
            "active": True
        }


# 全局因子引擎
_engine = FactorEngine()
_engine.register_core_factors()
_loaded = _engine.load_from_library()  # 加载因子挖掘库
if _loaded:
    print(f"[factor_engine] 已加载 {_loaded} 个挖掘因子, 总计 {_engine.factor_count} 个")

def get_engine() -> FactorEngine:
    return _engine

def factor_summary() -> str:
    """因子概览文本"""
    s = _engine.summary()
    lines = [f"🧬 因子引擎: {s['total_factors']} 个因子"]
    for cat, info in s["categories"].items():
        pct = info["weight"] * 100
        bars = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"   {cat:<8} {info['count']:>3}个 {bars} {pct:.0f}%")
    return "\n".join(lines)

