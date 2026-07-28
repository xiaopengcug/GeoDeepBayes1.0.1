from pathlib import Path

import numpy as np

from geodeepbayes.data.mt_edi import MTEDIAdapter


ROOT = Path(__file__).resolve().parents[2]
MEMBER = ROOT / "validation/wp8/data/usarray-ta-emtf-v1/edi/14856037.edi"


def test_mt_edi_adapter_preserves_complex_response_variance_and_hash():
    before = MEMBER.read_bytes()
    observation = MTEDIAdapter([MEMBER]).load()
    assert observation.data_mode == "complex"
    assert observation.complex_layout == "real_then_imag"
    assert observation.frequencies is not None
    assert len(observation.data) == 4 * len(np.unique(observation.frequencies))
    assert observation.covariance.shape == (2 * len(observation.data),) * 2
    assert np.all(np.diag(observation.covariance) >= 0)
    assert np.count_nonzero(
        observation.covariance - np.diag(np.diag(observation.covariance))
    ) == 0
    assert MEMBER.read_bytes() == before
