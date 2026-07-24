"""采样器与降维: 自适应 Metropolis-Hastings、POD 降维与代理误差传播框架。"""
from .metropolis import AdaptiveMetropolis
from .pod import PODReducer

__all__ = ["AdaptiveMetropolis", "PODReducer"]
