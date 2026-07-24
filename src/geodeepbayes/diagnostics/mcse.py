"""蒙特卡洛标准误差 (MCSE)。

对均值: MCSE = sd / sqrt(ess)；ess 取自 effective_sample_size。
对一般功能量（均值以外），完整的 MCSE 须结合其影响函数与 ESS 估计，此处给出均值版本作为基础。
"""
from __future__ import annotations

import numpy as np

from .rhat import _as_3d
from .ess import effective_sample_size


def monte_carlo_standard_error(chains):
    """均值的 MCSE = sd / sqrt(ess)。返回 float 或 (n_params,)。"""
    x = _as_3d(chains)
    flat = x.reshape(-1, x.shape[-1])
    sd = flat.std(axis=0, ddof=1)
    ess = np.atleast_1d(effective_sample_size(x))
    mcse = sd / np.sqrt(np.where(np.asarray(ess) > 0, ess, np.nan))
    return mcse[0] if mcse.size == 1 else mcse
