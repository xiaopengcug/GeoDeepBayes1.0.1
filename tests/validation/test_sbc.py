import pytest

from geodeepbayes.validation.feasibility import METHOD_NAMES
from geodeepbayes.validation.sbc import (
    normal_conjugate_reference_sbc,
    rank_uniformity,
    required_sbc_repetitions,
)


def test_nine_method_calibration_engine_runs_at_least_400_repetitions():
    results = {
        method: normal_conjugate_reference_sbc(
            seed=100 + index, sensitivity=0.5 + index / 10, qoi=f"{method}_scalar_qoi"
        )
        for index, method in enumerate(METHOD_NAMES)
    }
    assert all(result["repetitions"] == 400 for result in results.values())
    assert all(result["scope"].endswith("_reference") for result in results.values())
    assert all(len(result["raw_ranks"]) == 400 for result in results.values())
    assert required_sbc_repetitions() == 400


def test_sbc_rejects_underpowered_repetition_count():
    with pytest.raises(ValueError, match="at least 400"):
        rank_uniformity([1] * 399, posterior_draw_count=99)
