"""正演算子: 基于 SimPEG 封装，暴露统一接口 forward(m)/jvp(v,m)/jtp(w,m)。

matrix-free Jv/Jᵀv 借力 SimPEG Simulation.Jvec/Jtvec（内部经 getJ 的 LinearOperator），
通过伴随点积、Taylor 余项、有限差分三类测试验证离散伴随正确性。
"""
from .gravity import GravityOperator
from .magnetic import MagneticOperator
from .magnetic_vector import MagneticVectorOperator
from .mt3d import MT3DOperator
from .base import ForwardOperator
from .static import (
    ColeCole2DOperator,
    ColeColeFrequencyOperator,
    DCOperator,
    DipoleDipoleSurvey,
    TDIPOperator,
)
from .em1d import (
    DimensionalityUpgradeRequired,
    MT1DRecursiveOperator,
    TEM1DLayeredOperator,
    mt_dimensionality,
    tdem3d_path_status,
    tem_dimensionality,
)
from .controlled_source import CSAMTOperator, WFEMOperator, source_zone

__all__ = [
    "ForwardOperator",
    "GravityOperator",
    "MagneticOperator",
    "MagneticVectorOperator",
    "MT3DOperator",
    "DipoleDipoleSurvey",
    "DCOperator",
    "TDIPOperator",
    "ColeColeFrequencyOperator",
    "ColeCole2DOperator",
    "DimensionalityUpgradeRequired",
    "TEM1DLayeredOperator",
    "MT1DRecursiveOperator",
    "tem_dimensionality",
    "mt_dimensionality",
    "tdem3d_path_status",
    "CSAMTOperator",
    "WFEMOperator",
    "source_zone",
]
