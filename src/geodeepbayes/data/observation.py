"""Observation containers that preserve missingness, covariance and lineage."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np


def _readonly(value: Any, *, dtype: Any | None = None) -> np.ndarray:
    array = np.array(value, dtype=dtype, copy=True)
    array.setflags(write=False)
    return array


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, np.ndarray):
        return _readonly(value)
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ObservationSet:
    """Normalized observations with no silent filtering.

    Complex covariance always describes the explicitly declared real-valued
    stack. It may contain real/imaginary cross-covariance and therefore must
    have shape ``(2*n, 2*n)``.
    """

    data: np.ndarray
    coordinates: np.ndarray
    cluster: np.ndarray
    units: str
    crs: str
    data_mode: str = "real"
    covariance: np.ndarray | None = None
    frequencies: np.ndarray | None = None
    times: np.ndarray | None = None
    source_receiver_geometry: Mapping[str, Any] = field(default_factory=dict)
    quality_flags: np.ndarray | None = None
    raw_member_hashes: Mapping[str, str] = field(default_factory=dict)
    lineage: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    complex_layout: str | None = None
    standard_error: np.ndarray | None = None
    dataset_id: str = "unspecified"
    license_status: str = "unresolved"

    def __post_init__(self) -> None:
        data = _readonly(self.data)
        if data.ndim != 1 or len(data) == 0:
            raise ValueError("data must be a non-empty one-dimensional array")
        if np.any(np.isinf(data.real)) or (
            np.iscomplexobj(data) and np.any(np.isinf(data.imag))
        ):
            raise ValueError("data may preserve NaN but must reject infinity")
        if self.data_mode not in {"real", "complex", "time_decay", "frequency_response"}:
            raise ValueError("unsupported data_mode")
        if self.data_mode == "complex" and not np.iscomplexobj(data):
            raise ValueError("complex data_mode requires complex-valued data")
        if self.data_mode != "complex" and np.iscomplexobj(data):
            raise ValueError("complex data requires data_mode='complex'")
        coordinates = _readonly(self.coordinates, dtype=float)
        if coordinates.ndim != 2 or len(coordinates) != len(data):
            raise ValueError("coordinates must have shape (n_data, n_dimensions)")
        if not np.all(np.isfinite(coordinates)):
            raise ValueError("coordinates must be finite")
        cluster_values = np.asarray(self.cluster)
        if cluster_values.ndim != 1 or len(cluster_values) != len(data):
            raise ValueError("cluster must have shape (n_data,)")
        cluster = _readonly([str(value) for value in cluster_values])
        if any(not value.strip() or value.lower() in {"nan", "inf", "-inf"} for value in cluster):
            raise ValueError("cluster identifiers must be finite non-empty canonical strings")
        if not self.units or not self.crs:
            raise ValueError("units and crs are required")

        if self.data_mode == "complex":
            if self.complex_layout not in {"real_then_imag", "interleaved_real_imag"}:
                raise ValueError("complex_layout must explicitly define complex stacking")
            expected_covariance = 2 * len(data)
        else:
            if self.complex_layout is not None:
                raise ValueError("complex_layout is only valid for complex data")
            expected_covariance = len(data)
        covariance = None
        if self.covariance is not None:
            covariance = _readonly(self.covariance, dtype=float)
            if covariance.shape != (expected_covariance, expected_covariance):
                raise ValueError(
                    f"covariance must have shape ({expected_covariance}, {expected_covariance})"
                )
            if not np.allclose(covariance, covariance.T, equal_nan=False):
                raise ValueError("covariance must be symmetric")
            if not np.all(np.isfinite(covariance)):
                raise ValueError("covariance must be finite")
            if float(np.min(np.linalg.eigvalsh(covariance))) < 0:
                raise ValueError("covariance must be strictly positive semidefinite")
        standard_error = None
        if self.standard_error is not None:
            if covariance is not None:
                raise ValueError("standard_error and covariance are mutually exclusive")
            standard_error = _readonly(self.standard_error, dtype=float)
            if standard_error.shape != (len(data),):
                raise ValueError("standard_error must have shape (n_data,)")
            if not np.all(np.isfinite(standard_error)) or np.any(standard_error <= 0):
                raise ValueError("standard_error must contain finite positive values")

        flags = (
            _readonly(self.quality_flags, dtype=bool)
            if self.quality_flags is not None
            else _readonly(np.zeros(len(data), dtype=bool))
        )
        if flags.shape != (len(data),):
            raise ValueError("quality_flags must have shape (n_data,)")
        missing = np.isnan(data.real) | (np.isnan(data.imag) if np.iscomplexobj(data) else False)
        # Missing values are preserved and always marked. Existing bad-channel
        # flags are never cleared.
        flags = _readonly(flags | missing, dtype=bool)

        hashes = dict(self.raw_member_hashes)
        if not hashes or any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower())
            for value in hashes.values()
        ):
            raise ValueError("raw_member_hashes must contain SHA-256 hex digests")
        lineage = tuple(_deep_freeze(item) for item in self.lineage)
        if not lineage:
            raise ValueError("at least one lineage record is required")
        if not self.dataset_id or not self.license_status:
            raise ValueError("dataset_id and license_status are required")

        frequencies = None if self.frequencies is None else _readonly(self.frequencies, dtype=float)
        times = None if self.times is None else _readonly(self.times, dtype=float)
        for name, axis in (("frequencies", frequencies), ("times", times)):
            if axis is not None and (
                axis.shape != (len(data),)
                or not np.all(np.isfinite(axis))
                or np.any(axis <= 0)
            ):
                raise ValueError(
                    f"{name} must be a finite positive vector aligned to data"
                )
        if self.data_mode == "frequency_response" and frequencies is None:
            raise ValueError("frequency_response requires frequencies")
        if self.data_mode == "time_decay" and times is None:
            raise ValueError("time_decay requires times")

        object.__setattr__(self, "data", data)
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "cluster", cluster)
        object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "standard_error", standard_error)
        object.__setattr__(self, "quality_flags", flags)
        object.__setattr__(self, "frequencies", frequencies)
        object.__setattr__(self, "times", times)
        object.__setattr__(self, "source_receiver_geometry", _deep_freeze(self.source_receiver_geometry))
        object.__setattr__(self, "raw_member_hashes", MappingProxyType(hashes))
        object.__setattr__(self, "lineage", lineage)

    def real_stack(self) -> np.ndarray:
        if self.data_mode != "complex":
            return _readonly(self.data, dtype=float)
        if self.complex_layout == "real_then_imag":
            return _readonly(np.r_[self.data.real, self.data.imag])
        return _readonly(np.column_stack((self.data.real, self.data.imag)).ravel())


class DatasetAdapter(ABC):
    """Read-only adapter that proves source members did not change."""

    maximum_snapshot_member_bytes = 128 * 1024 * 1024
    maximum_snapshot_total_bytes = 256 * 1024 * 1024

    def __init__(self, raw_paths: Sequence[str | Path]):
        paths = tuple(Path(path).resolve() for path in raw_paths)
        if not paths or any(not path.is_file() for path in paths):
            raise ValueError("all raw_paths must identify existing files")
        self.raw_paths = paths

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def load(self) -> ObservationSet:
        captured: dict[str, bytes] = {}
        total = 0
        for path in self.raw_paths:
            chunks: list[bytes] = []
            member = 0
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(min(1024 * 1024, self.maximum_snapshot_member_bytes + 1))
                    if not chunk:
                        break
                    member += len(chunk)
                    total += len(chunk)
                    if (
                        member > self.maximum_snapshot_member_bytes
                        or total > self.maximum_snapshot_total_bytes
                    ):
                        raise ValueError("raw snapshot exceeds fail-closed byte budget")
                    chunks.append(chunk)
            captured[str(path)] = b"".join(chunks)
        snapshots = MappingProxyType(captured)
        before = {
            path: hashlib.sha256(content).hexdigest()
            for path, content in snapshots.items()
        }
        result = self.parse(before, snapshots)
        after = {str(path): self._hash(path) for path in self.raw_paths}
        if before != after:
            raise RuntimeError("raw input changed while adapter was reading it")
        if dict(result.raw_member_hashes) != before:
            raise ValueError("adapter result does not preserve exact raw member hashes")
        return result

    @abstractmethod
    def parse(
        self,
        raw_member_hashes: Mapping[str, str],
        raw_snapshots: Mapping[str, bytes],
    ) -> ObservationSet:
        """Parse immutable bytes; raw paths are provenance identifiers only."""


class MissingObservationContract(ValueError):
    pass


def validate_controlled_source_contract(
    method: str, metadata: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Validate field metadata before a CSAMT/WFEM adapter may read values."""
    requirements = {
        "csamt": (
            "source_vertices",
            "source_current_A",
            "receiver_locations",
            "frequencies_Hz",
            "components",
            "phase_convention",
            "apparent_resistivity_definition",
        ),
        "wfem": (
            "source_vertices",
            "source_current_A",
            "receiver_locations",
            "frequencies_Hz",
            "components",
            "phase_convention",
            "apparent_resistivity_definition",
            "geometric_factor",
        ),
    }
    if method not in requirements:
        raise ValueError("controlled-source method must be csamt or wfem")
    missing = [
        name
        for name in requirements[method]
        if name not in metadata or metadata[name] is None
    ]
    if missing:
        raise MissingObservationContract(
            f"{method} field adapter blocked; missing: {', '.join(missing)}"
        )
    vertices = np.asarray(metadata["source_vertices"], dtype=float)
    receivers = np.asarray(metadata["receiver_locations"], dtype=float)
    frequencies = np.asarray(metadata["frequencies_Hz"], dtype=float)
    if (
        vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 2
        or not np.all(np.isfinite(vertices))
        or np.any(np.linalg.norm(np.diff(vertices, axis=0), axis=1) == 0)
    ):
        raise MissingObservationContract("source_vertices must define a 3-D finite line")
    if (
        receivers.ndim != 2 or receivers.shape[1] != 3 or len(receivers) == 0
        or not np.all(np.isfinite(receivers))
    ):
        raise MissingObservationContract("receiver_locations must be explicit 3-D coordinates")
    if (
        frequencies.ndim != 1 or len(frequencies) == 0
        or not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 0)
    ):
        raise MissingObservationContract("frequencies_Hz must be a positive vector")
    current = metadata["source_current_A"]
    if (
        isinstance(current, (bool, str, bytes))
        or not np.isscalar(current)
        or not np.isfinite(current)
        or current <= 0
    ):
        raise MissingObservationContract("source_current_A must be finite and positive")
    for name in ("components", "phase_convention", "apparent_resistivity_definition"):
        value = metadata[name]
        if (
            (isinstance(value, str) and not value.strip())
            or (name == "components" and (
                not isinstance(value, Sequence) or isinstance(value, str)
                or len(value) == 0 or any(not str(item).strip() for item in value)
            ))
        ):
            raise MissingObservationContract(f"{name} must be explicit and non-empty")
    if method == "wfem":
        try:
            factor = np.asarray(metadata["geometric_factor"], dtype=float)
        except (TypeError, ValueError) as error:
            raise MissingObservationContract(
                "geometric_factor must be finite and non-zero"
            ) from error
        if factor.size == 0 or not np.all(np.isfinite(factor)) or np.any(factor == 0):
            raise MissingObservationContract("geometric_factor must be finite and non-zero")
    return _deep_freeze(metadata)
