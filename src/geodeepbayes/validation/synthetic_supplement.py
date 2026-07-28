"""Deterministic, contract-complete synthetic cohorts for WP8-1 development.

These cohorts exercise adapters, split logic, covariance handling, and metric
pipelines.  They are deliberately labelled as substitutes and are never field
validation evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np


SUPPORTED_METHODS = ("sip_fdip", "csamt", "wfem")


@dataclass(frozen=True)
class SyntheticSupplement:
    method: str
    seed: int
    cluster_id: np.ndarray
    role: np.ndarray
    frequencies_hz: np.ndarray
    receiver_xyz_m: np.ndarray
    source_vertices_xyz_m: np.ndarray
    source_current_a: np.ndarray
    response: np.ndarray
    standard_error: np.ndarray
    provenance: str = "synthetic-substitute"
    field_validation_eligible: bool = False

    @property
    def cluster_count(self) -> int:
        return int(self.cluster_id.size)

    @property
    def test_cluster_count(self) -> int:
        return int(np.count_nonzero(self.role == "test"))

    def digest(self) -> str:
        digest = sha256()
        digest.update(self.method.encode("utf-8") + b"\0")
        digest.update(int(self.seed).to_bytes(8, "little", signed=True))
        digest.update(self.provenance.encode("utf-8") + b"\0")
        digest.update(b"\x01" if self.field_validation_eligible else b"\x00")
        for value in (
            self.cluster_id,
            self.role.astype("U16"),
            self.frequencies_hz,
            self.receiver_xyz_m,
            self.source_vertices_xyz_m,
            self.source_current_a,
            self.response,
            self.standard_error,
        ):
            digest.update(np.ascontiguousarray(value).tobytes())
        return digest.hexdigest()


def make_synthetic_supplement(
    method: str,
    *,
    seed: int = 8101,
    cluster_count: int = 500,
) -> SyntheticSupplement:
    """Create a reproducible cohort with 100/100/remaining train/cal/test split."""
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"unsupported synthetic supplement method: {method}")
    if cluster_count < 423:
        raise ValueError("cluster_count must leave at least 223 independent test clusters")

    rng = np.random.default_rng(seed)
    cluster_id = np.arange(cluster_count, dtype=np.int64)
    role = np.full(cluster_count, "test", dtype="U16")
    assignment = rng.permutation(cluster_count)
    role[assignment[:100]] = "training"
    role[assignment[100:200]] = "calibration"

    frequencies = np.geomspace(0.25, 2048.0, 16)
    receiver = np.column_stack(
        (
            cluster_id.astype(float) * 50.0,
            (cluster_id % 17).astype(float) * 75.0,
            np.zeros(cluster_count),
        )
    )
    source_vertices = np.empty((cluster_count, 2, 3), dtype=float)
    source_vertices[:, 0, :] = receiver + np.array([-2500.0, -500.0, 0.0])
    source_vertices[:, 1, :] = receiver + np.array([-1500.0, -500.0, 0.0])
    source_current = 4.0 + 0.2 * np.sin(cluster_id / 13.0)

    distance = np.linalg.norm(
        receiver - source_vertices.mean(axis=1), axis=1
    )[:, None]
    spectral_shape = 1.0 / np.sqrt(frequencies[None, :])
    spatial_shape = np.exp(-distance / 8000.0)
    phase = -0.08 * np.log1p(frequencies)[None, :]
    if method == "sip_fdip":
        amplitude = (0.8 + 0.1 * np.sin(cluster_id[:, None] / 19.0)) * (
            1.0 + 0.04 * np.log1p(frequencies)[None, :]
        )
        phase = -0.02 - 0.12 / (1.0 + frequencies[None, :])
    elif method == "wfem":
        amplitude = source_current[:, None] * spatial_shape * spectral_shape * 1e-4
        phase = phase - 0.1
    else:
        amplitude = source_current[:, None] * spatial_shape * spectral_shape * 8e-5

    clean = amplitude * np.exp(1j * phase)
    sigma = np.maximum(np.abs(clean) * 0.03, 1e-9)
    noise = rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape)
    response = clean + sigma * noise / np.sqrt(2.0)

    return SyntheticSupplement(
        method=method,
        seed=seed,
        cluster_id=cluster_id,
        role=role,
        frequencies_hz=frequencies,
        receiver_xyz_m=receiver,
        source_vertices_xyz_m=source_vertices,
        source_current_a=source_current,
        response=response,
        standard_error=sigma,
    )
