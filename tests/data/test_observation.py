import hashlib
import io

import numpy as np
import pytest

from geodeepbayes.data import (
    DatasetAdapter,
    MissingObservationContract,
    ObservationSet,
    validate_controlled_source_contract,
)


HASH = "a" * 64


def _observation(**overrides):
    values = {
        "data": np.array([1.0, np.nan]),
        "coordinates": np.array([[0.0, 1.0], [2.0, 3.0]]),
        "cluster": np.array(["a", "b"]),
        "units": "mV",
        "crs": "EPSG:32612",
        "raw_member_hashes": {"raw.dat": HASH},
        "lineage": ({"operation": "identity", "version": "1"},),
    }
    values.update(overrides)
    return ObservationSet(**values)


def test_nan_is_preserved_and_flagged_and_arrays_are_read_only():
    observation = _observation()
    assert np.isnan(observation.data[1])
    assert observation.quality_flags.tolist() == [False, True]
    with pytest.raises(ValueError):
        observation.data[0] = 2


def test_complex_layout_preserves_cross_covariance():
    covariance = np.eye(4)
    covariance[0, 2] = covariance[2, 0] = 0.25
    observation = _observation(
        data=np.array([1 + 2j, 3 + 4j]),
        data_mode="complex",
        complex_layout="real_then_imag",
        covariance=covariance,
    )
    np.testing.assert_array_equal(observation.real_stack(), [1, 3, 2, 4])
    assert observation.covariance[0, 2] == 0.25
    with pytest.raises(ValueError):
        observation.covariance[0, 0] = 2


def test_complex_covariance_cannot_be_split_into_n_by_n_errors():
    with pytest.raises(ValueError, match="covariance"):
        _observation(
            data=np.array([1 + 2j, 3 + 4j]),
            data_mode="complex",
            complex_layout="interleaved_real_imag",
            covariance=np.eye(2),
        )


def test_invalid_shapes_and_hashes_fail():
    with pytest.raises(ValueError, match="coordinates"):
        _observation(coordinates=np.ones((1, 2)))
    with pytest.raises(ValueError, match="SHA-256"):
        _observation(raw_member_hashes={"raw.dat": "unknown"})


def test_frequency_time_axes_and_uncertainty_contracts_fail_closed():
    with pytest.raises(ValueError, match="frequencies"):
        _observation(
            data_mode="frequency_response",
            frequencies=[10.0, -1.0],
        )
    with pytest.raises(ValueError, match="times"):
        _observation(data_mode="time_decay", times=[0.1, 0.0])
    with pytest.raises(ValueError, match="standard_error"):
        _observation(standard_error=[0.1])
    with pytest.raises(ValueError, match="positive"):
        _observation(standard_error=[0.1, 0.0])


def test_license_dataset_and_geometry_contract_are_explicit_and_immutable():
    observation = _observation(
        dataset_id="example-v1",
        license_status="local-only-unresolved",
        source_receiver_geometry={"receivers": [[1.0, 2.0, 3.0]]},
    )
    assert observation.dataset_id == "example-v1"
    assert observation.license_status == "local-only-unresolved"
    with pytest.raises(TypeError):
        observation.source_receiver_geometry["new"] = "forbidden"
    with pytest.raises(TypeError):
        observation.source_receiver_geometry["receivers"][0] = (0, 0, 0)
    with pytest.raises(TypeError):
        observation.lineage[0]["operation"] = "mutated"
    for array in (
        observation.coordinates, observation.cluster, observation.quality_flags
    ):
        assert array.flags.writeable is False


def test_nonfinite_and_covariance_contracts_fail_closed():
    with pytest.raises(ValueError, match="infinity"):
        _observation(data=[1.0, np.inf])
    with pytest.raises(ValueError, match="coordinates"):
        _observation(coordinates=[[0, 1], [np.inf, 2]])
    with pytest.raises(ValueError, match="cluster"):
        _observation(cluster=["a", ""])
    with pytest.raises(ValueError, match="positive semidefinite"):
        _observation(covariance=[[1.0, 2.0], [2.0, 1.0]])
    with pytest.raises(ValueError, match="positive semidefinite"):
        _observation(covariance=[[1.0, 0.0], [0.0, -1e-14]])
    with pytest.raises(ValueError, match="mutually exclusive"):
        _observation(covariance=np.eye(2), standard_error=[0.1, 0.2])


def test_optional_uncertainty_and_axes_are_read_only():
    for name, observation in (
        ("standard_error", _observation(standard_error=[0.1, 0.2])),
        ("frequencies", _observation(
            data_mode="frequency_response", frequencies=[1.0, 2.0]
        )),
        ("times", _observation(data_mode="time_decay", times=[1.0, 2.0])),
    ):
        with pytest.raises(ValueError):
            getattr(observation, name)[0] = 9


class _TextAdapter(DatasetAdapter):
    def parse(self, raw_member_hashes, raw_snapshots):
        data = np.genfromtxt(io.BytesIO(next(iter(raw_snapshots.values()))))
        return _observation(
            data=np.atleast_1d(data),
            coordinates=np.column_stack((np.arange(np.size(data)), np.zeros(np.size(data)))),
            cluster=np.arange(np.size(data)),
            raw_member_hashes=raw_member_hashes,
        )


def test_adapter_binds_exact_raw_hash_and_does_not_modify(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("1\nnan\n", encoding="utf-8")
    before = raw.read_bytes()
    observation = _TextAdapter([raw]).load()
    assert raw.read_bytes() == before
    assert observation.raw_member_hashes[str(raw.resolve())] == hashlib.sha256(before).hexdigest()
    assert observation.quality_flags.tolist() == [False, True]


class _WrongHashAdapter(_TextAdapter):
    def parse(self, raw_member_hashes, raw_snapshots):
        result = super().parse(raw_member_hashes, raw_snapshots)
        object.__setattr__(result, "raw_member_hashes", {"wrong": "b" * 64})
        return result


class _MutatingAdapter(_TextAdapter):
    def parse(self, raw_member_hashes, raw_snapshots):
        result = super().parse(raw_member_hashes, raw_snapshots)
        self.raw_paths[0].write_text("changed\n", encoding="utf-8")
        return result


class _ABAAdapter(_TextAdapter):
    def parse(self, raw_member_hashes, raw_snapshots):
        original = self.raw_paths[0].read_bytes()
        self.raw_paths[0].write_bytes(b"999\n")
        result = super().parse(raw_member_hashes, raw_snapshots)
        self.raw_paths[0].write_bytes(original)
        return result


def test_adapter_rejects_hash_mismatch_and_read_during_change(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("1\n2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact raw member hashes"):
        _WrongHashAdapter([raw]).load()
    raw.write_text("1\n2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed while adapter"):
        _MutatingAdapter([raw]).load()
    raw.write_text("1\n2\n", encoding="utf-8")
    assert _ABAAdapter([raw]).load().data.tolist() == [1.0, 2.0]


def test_adapter_snapshot_byte_budgets_fail_before_parse(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_bytes(b"12345")
    adapter = _TextAdapter([raw])
    adapter.maximum_snapshot_member_bytes = 4
    with pytest.raises(ValueError, match="byte budget"):
        adapter.load()
    adapter.maximum_snapshot_member_bytes = 5
    adapter.maximum_snapshot_total_bytes = 5
    assert adapter.load().data.tolist() == [12345.0]


def test_csamt_and_wfem_field_contracts_fail_closed():
    incomplete = {
        "receiver_locations": [[0, 0, 0]],
        "frequencies_Hz": [1.0],
    }
    for method in ("csamt", "wfem"):
        with pytest.raises(MissingObservationContract, match="field adapter blocked"):
            validate_controlled_source_contract(method, incomplete)


def test_controlled_source_contract_rejects_nonfinite_and_degenerate_values():
    valid = {
        "source_vertices": [[0, 0, 0], [1, 0, 0]],
        "source_current_A": 1.0,
        "receiver_locations": [[2, 1, -1]],
        "frequencies_Hz": [1.0],
        "components": ["Ex"],
        "phase_convention": "exp(+iwt)",
        "apparent_resistivity_definition": "not_available",
        "geometric_factor": [1.0],
    }
    assert validate_controlled_source_contract("wfem", valid)["source_current_A"] == 1.0
    attacks = [
        ("source_vertices", [[0, 0, 0], [0, 0, 0]]),
        ("receiver_locations", [[np.inf, 0, 0]]),
        ("frequencies_Hz", [np.nan]),
        ("source_current_A", np.inf),
        ("components", []),
        ("phase_convention", ""),
        ("geometric_factor", [0.0]),
    ]
    for key, value in attacks:
        payload = dict(valid)
        payload[key] = value
        with pytest.raises(MissingObservationContract):
            validate_controlled_source_contract("wfem", payload)
