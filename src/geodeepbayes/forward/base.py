"""Unified forward-operator contract."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray


@runtime_checkable
class ForwardOperator(Protocol):
    """Structural protocol shared by every WP8 physical operator."""

    method: str
    dimensionality: str
    data_mode: str
    source_type: str
    waveform: str | None
    components: Any
    units: str
    parameterization: str
    n_param: int
    n_data: int

    def predict(self, model: ArrayLike) -> NDArray[np.floating | np.complexfloating]: ...

    def forward(self, model: ArrayLike) -> NDArray[np.floating | np.complexfloating]: ...

    def jvp(
        self, vector: ArrayLike, model: ArrayLike | None = None
    ) -> NDArray[np.floating | np.complexfloating]: ...

    def jtp(
        self, vector: ArrayLike, model: ArrayLike | None = None
    ) -> NDArray[np.floating | np.complexfloating]: ...


def validate_vector(value: ArrayLike, expected: int, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 1 or len(array) != expected:
        raise ValueError(f"{name} must have shape ({expected},), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")
    return array
