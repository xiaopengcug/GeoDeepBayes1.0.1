"""先验构造: 结构耦合（交叉梯度软先验）、物性统计（GMM）、地质分层先验。"""
from .cross_gradient import (
    S_CHI_STAR_SI,
    S_RHO_STAR_G_CM3,
    CrossGradientPenalty,
    build_cell_gradient_operators,
)

__all__ = [
    "CrossGradientPenalty",
    "build_cell_gradient_operators",
    "S_RHO_STAR_G_CM3",
    "S_CHI_STAR_SI",
]
