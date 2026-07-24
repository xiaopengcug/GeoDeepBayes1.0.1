"""GeoDeepBayes: 贝叶斯重磁电电磁联合反演（TRL 3-4 研究框架）。

子包:
    forward     —— 正演算子（matrix-free Jv/Jᵀv）
    sampling    —— MCMC 采样器与 POD 降维
    diagnostics —— 收敛诊断（rank-R̂、ESS、MCSE）
    divergence  —— 分布距离（k-NN KL 等）
    priors      —— 先验构造
    io          —— 数据契约读写
    benchmarks  —— 合成验证脚本
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
