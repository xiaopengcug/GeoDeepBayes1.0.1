"""正演算子: 基于 SimPEG 封装，暴露统一接口 forward(m)/jvp(v,m)/jtp(w,m)。

matrix-free Jv/Jᵀv 借力 SimPEG Simulation.Jvec/Jtvec（内部经 getJ 的 LinearOperator），
通过伴随点积、Taylor 余项、有限差分三类测试验证离散伴随正确性。
"""
from .gravity import GravityOperator
from .magnetic import MagneticOperator

__all__ = ["GravityOperator", "MagneticOperator"]
