import numpy as np
import pytest

from geodeepbayes.validation.synthetic_supplement import (
    SUPPORTED_METHODS,
    make_synthetic_supplement,
)


@pytest.mark.parametrize("method", SUPPORTED_METHODS)
def test_synthetic_supplement_is_contract_complete_and_explicitly_non_field(method):
    cohort = make_synthetic_supplement(method)
    assert cohort.cluster_count == 500
    assert cohort.test_cluster_count == 300
    assert not np.array_equal(cohort.role[:100], np.full(100, "training"))
    assert cohort.response.shape == (500, 16)
    assert cohort.standard_error.shape == cohort.response.shape
    assert np.all(cohort.standard_error > 0)
    assert cohort.receiver_xyz_m.shape == (500, 3)
    assert cohort.source_vertices_xyz_m.shape == (500, 2, 3)
    assert cohort.provenance == "synthetic-substitute"
    assert cohort.field_validation_eligible is False


def test_synthetic_supplement_is_reproducible_and_seed_sensitive():
    first = make_synthetic_supplement("sip_fdip", seed=7)
    repeat = make_synthetic_supplement("sip_fdip", seed=7)
    changed = make_synthetic_supplement("sip_fdip", seed=8)
    assert first.digest() == repeat.digest()
    assert first.digest() != changed.digest()


def test_synthetic_supplement_preserves_minimum_test_cluster_requirement():
    with pytest.raises(ValueError, match="223"):
        make_synthetic_supplement("wfem", cluster_count=422)
