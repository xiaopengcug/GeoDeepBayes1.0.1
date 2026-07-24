"""收敛诊断: rank-normalized split-R̂、bulk/tail ESS、MCSE。

参考 Vehtari et al. (2021) "Rank-normalization, folding, and localization:
An improved R̂ for assessing convergence of MCMC", Bayesian Analysis。
"""
from .rhat import split_rhat, rank_normalized_split_rhat
from .ess import effective_sample_size, bulk_ess, tail_ess
from .mcse import monte_carlo_standard_error

__all__ = [
    "split_rhat",
    "rank_normalized_split_rhat",
    "effective_sample_size",
    "bulk_ess",
    "tail_ess",
    "monte_carlo_standard_error",
]
