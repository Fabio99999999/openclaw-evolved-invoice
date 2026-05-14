"""
对抗训练框架 — 提升模型泛化能力
文献参考: 《Deep Learning for Finance》Ch.12
"""
import numpy as np
import pandas as pd
from typing import Optional, Callable, Dict, Any

class AdversarialTrainer:
    """
    对抗训练器: 用对抗样本增强模型鲁棒性
    适配 LightGBM/XGBoost
    """
    
    def __init__(self, epsilon: float = 0.05, alpha: float = 0.01):
        self.epsilon = epsilon  # 扰动幅度
        self.alpha = alpha      # 步长 (FGSM)
    
    def fgsm_attack(self, features: np.ndarray, gradients: np.ndarray) -> np.ndarray:
        """
        Fast Gradient Sign Method
        生成对抗样本
        """
        # 计算梯度方向
        grad_sign = np.sign(gradients)
        # 施加扰动
        perturbed = features + self.epsilon * grad_sign
        return perturbed
    
    def generate_adversarial(self, df: pd.DataFrame, model: Any, 
                               feature_cols: List[str], label_col: str) -> pd.DataFrame:
        """
        基于模型梯度的对抗样本生成
        (简化版: 使用特征扰动 + 标签翻转)
        """
        adv_df = df.copy()
        
        # 对连续特征添加高斯噪声 (模拟对抗)
        for col in feature_cols:
            if df[col].dtype in [np.float64, np.float32]:
                noise = np.random.normal(0, self.epsilon * df[col].std(), len(df))
                adv_df[col] = df[col] + noise
        
        # 部分样本标签翻转 (10%)
        n_flip = max(1, int(len(df) * 0.1))
        flip_idx = np.random.choice(len(df), n_flip, replace=False)
        adv_df.iloc[flip_idx, adv_df.columns.get_loc(label_col)] = \
            1 - df.iloc[flip_idx][label_col]
        
        return adv_df

