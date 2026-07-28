from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from geodeepbayes.data.mt_xml import MTXMLAdapter, _matrix


ROOT = Path(__file__).resolve().parents[2]
MEMBER = ROOT / "validation/wp8/data/usarray-ta-emtf-v1/xml/14856037.xml"


def test_mt_xml_adapter_reconstructs_full_complex_covariance_without_mutation():
    before = MEMBER.read_bytes()
    observation = MTXMLAdapter([MEMBER]).load()
    assert observation.data_mode == "complex"
    assert observation.complex_layout == "real_then_imag"
    assert len(observation.data) == 4 * len(np.unique(observation.frequencies))
    assert observation.covariance.shape == (2 * len(observation.data),) * 2
    off_diagonal = observation.covariance - np.diag(np.diag(observation.covariance))
    assert np.count_nonzero(np.abs(off_diagonal) > 0) > 0
    np.testing.assert_allclose(observation.covariance, observation.covariance.T)
    assert np.min(np.linalg.eigvalsh(observation.covariance)) > -1e-12
    assert "residual covariance" in observation.source_receiver_geometry["covariance"]
    assert MEMBER.read_bytes() == before


def test_mt_xml_covariance_factorization_reproduces_published_z_variance():
    period = next(ET.parse(MEMBER).getroot().iter("Period"))
    inverse_signal = _matrix(period, "Z.INVSIGCOV", ("Hx", "Hy"))
    residual = _matrix(period, "Z.RESIDCOV", ("Ex", "Ey"))
    reconstructed = np.outer(
        np.diag(residual).real, np.diag(inverse_signal).real
    )
    published = np.asarray(
        [float(value.text) for value in period.find("Z.VAR").findall("value")]
    ).reshape(2, 2)
    np.testing.assert_allclose(reconstructed, published, rtol=1e-5)
