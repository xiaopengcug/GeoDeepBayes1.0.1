"""Fail-closed WP8 feasibility evaluation.

This module deliberately treats missing evidence as failure.  It never infers
licensing, statistical power, dimensionality, or solver readiness from the
mere presence of a data file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np
from scipy import stats
from scipy.spatial.distance import pdist, squareform
import hashlib
import json

METHOD_NAMES = (
    "gravity",
    "magnetic",
    "dc",
    "tdip",
    "sip_fdip",
    "tem",
    "mt_amt",
    "csamt",
    "wfem",
)

REQUIRED_GATES = (
    "license",
    "integrity",
    "observation_contract",
    "clusters",
    "power",
    "dimensionality",
    "solver",
    "independent_reference",
    "resource_budget",
)


@dataclass(frozen=True)
class FeasibilityDecision:
    method: str
    status: str
    failed_gates: tuple[str, ...]
    reasons: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["failed_gates"] = list(self.failed_gates)
        value["reasons"] = list(self.reasons)
        return value


def bind_gate_evidence(
    *,
    method: str,
    dataset_slug: str,
    gate_name: str,
    status: str,
    reason: str,
    producer: str,
    producer_sha256: str,
    measurements: Mapping[str, Any],
    thresholds: Mapping[str, Any],
) -> dict[str, Any]:
    basis = {
        "method": method, "dataset_slug": dataset_slug, "gate_name": gate_name,
        "status": status, "reason": reason, "producer": producer,
        "producer_sha256": producer_sha256,
        "measurements": dict(measurements), "thresholds": dict(thresholds),
    }
    digest = hashlib.sha256(
        json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**basis, "evidence_id": f"wp8-{method}-{gate_name}-{digest[:16]}", "evidence_sha256": digest}


def _finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _finite_tree(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, (float, np.floating)):
        return bool(np.isfinite(value))
    return value is None or isinstance(value, (str, bool, int, np.integer))


def _gate_passed(
    value: Any,
    *,
    expected_method: str,
    expected_gate: str,
    expected_dataset_slug: str,
    trusted_producers: Mapping[str, str],
) -> bool:
    if not isinstance(value, Mapping) or value.get("status") != "passed":
        return False
    required = {
        "method", "dataset_slug", "gate_name", "reason", "producer",
        "producer_sha256", "measurements", "thresholds", "evidence_id",
        "evidence_sha256",
    }
    if not required.issubset(value):
        return False
    if (
        value.get("method") != expected_method
        or value.get("gate_name") != expected_gate
        or value.get("dataset_slug") != expected_dataset_slug
        or not isinstance(value.get("dataset_slug"), str)
        or not value["dataset_slug"]
        or not isinstance(value.get("measurements"), Mapping)
        or not value["measurements"]
        or not isinstance(value.get("thresholds"), Mapping)
        or not value["thresholds"]
        or not _finite_tree(value["measurements"])
        or not _finite_tree(value["thresholds"])
        or not isinstance(value.get("producer_sha256"), str)
        or len(value["producer_sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in value["producer_sha256"].lower())
        or not isinstance(value.get("producer"), str)
        or not value["producer"]
        or trusted_producers.get(value["producer"]) != value["producer_sha256"]
        or not isinstance(value.get("reason"), str)
        or not value["reason"]
    ):
        return False
    expected = bind_gate_evidence(
        method=value["method"], dataset_slug=value["dataset_slug"],
        gate_name=value["gate_name"], status=value["status"],
        reason=value["reason"], producer=value["producer"],
        producer_sha256=value["producer_sha256"],
        measurements=value["measurements"], thresholds=value["thresholds"],
    )
    return (
        value.get("evidence_id") == expected["evidence_id"]
        and value.get("evidence_sha256") == expected["evidence_sha256"]
    )


def evaluate_feasibility(
    registration: Mapping[str, Any],
    *,
    expected_registration_hashes: Mapping[str, str],
    trusted_producers: Mapping[str, str],
) -> dict[str, Any]:
    """Return a structural decision; this function alone never authorizes field use.

    SHA-256 values checked here are integrity digests, not producer signatures.
    Field authorization requires the validator's live authoritative replay.
    """
    for name in ("manifest_sha256", "dataset_selection_sha256", "preregistration_sha256"):
        if registration.get(name) != expected_registration_hashes.get(name):
            raise ValueError(f"registration.{name} does not match trusted anchor")
    configured = registration.get("methods")
    if not isinstance(configured, Mapping):
        raise ValueError("registration.methods must be an object")

    unknown = sorted(set(configured) - set(METHOD_NAMES))
    if unknown:
        raise ValueError(f"unknown methods: {unknown}")

    decisions: list[FeasibilityDecision] = []
    for method in METHOD_NAMES:
        method_data = configured.get(method)
        reasons: list[dict[str, str]] = []
        failed: list[str] = []
        if not isinstance(method_data, Mapping):
            failed = list(REQUIRED_GATES)
            reasons.append({"code": "METHOD_NOT_REGISTERED", "detail": method})
        else:
            gates = method_data.get("gates", {})
            if not isinstance(gates, Mapping):
                gates = {}
            for gate in REQUIRED_GATES:
                evidence = gates.get(gate)
                if (
                    not _gate_passed(
                        evidence,
                        expected_method=method,
                        expected_gate=gate,
                        expected_dataset_slug=method_data.get("dataset_slug"),
                        trusted_producers=trusted_producers,
                    )
                ):
                    failed.append(gate)
                    detail = (
                        evidence.get("reason", "missing affirmative evidence")
                        if isinstance(evidence, Mapping)
                        else "gate evidence missing"
                    )
                    reasons.append(
                        {"code": f"{gate.upper()}_NOT_PASSED", "detail": str(detail)}
                    )
        decisions.append(
            FeasibilityDecision(
                method=method,
                status="passed" if not failed else "failed",
                failed_gates=tuple(failed),
                reasons=tuple(reasons),
            )
        )

    overall = "passed" if all(d.status == "passed" for d in decisions) else "failed"
    return {
        "schema_version": "wp8-feasibility-v1",
        "phase": "feasibility",
        "status": overall,
        "wp8_1_allowed": overall == "passed",
        "methods": [decision.to_dict() for decision in decisions],
    }


def required_paired_clusters(
    standardized_effect: float,
    *,
    alpha_one_sided: float = 0.05,
    power: float = 0.8,
) -> int:
    """Minimum independent paired clusters for a one-sided mean test.

    The standardized effect must be estimated only from the training candidate
    region. Frequencies, time channels and repeated readings are not accepted
    as independent units by this API.
    """
    if not np.isfinite(standardized_effect) or standardized_effect <= 0:
        raise ValueError("standardized_effect must be positive")
    if (
        not np.isfinite(alpha_one_sided)
        or not np.isfinite(power)
        or not 0 < alpha_one_sided < 0.5
        or not 0.5 < power < 1
    ):
        raise ValueError("invalid alpha or power")

    def achieved(n: int) -> float:
        critical = stats.t.ppf(1 - alpha_one_sided, n - 1)
        return float(stats.nct.sf(critical, n - 1, standardized_effect * np.sqrt(n)))

    low, high = 2, 2
    while high <= 1_000_000 and achieved(high) < power:
        low, high = high + 1, high * 2
    if high > 1_000_000:
        high = 1_000_000
        if achieved(high) < power:
            raise ValueError("required cluster count exceeds supported bound")
    while low < high:
        middle = (low + high) // 2
        if achieved(middle) >= power:
            high = middle
        else:
            low = middle + 1
    return low


def required_coverage_clusters(
    *,
    nominal: float,
    equivalence_margin: float = 0.05,
    alpha_two_sided: float = 0.05,
    power: float = 0.8,
) -> int:
    """Conservative normal-approximation size for a coverage equivalence TOST."""
    if not np.isfinite(nominal) or not 0 < nominal < 1:
        raise ValueError("nominal must be in (0, 1)")
    if not np.isfinite(equivalence_margin) or not 0 < equivalence_margin < min(nominal, 1 - nominal):
        raise ValueError("invalid equivalence margin")
    if (
        not np.isfinite(alpha_two_sided)
        or not np.isfinite(power)
        or not 0 < alpha_two_sided < 0.5
        or not 0.5 < power < 1
    ):
        raise ValueError("invalid alpha or power")
    z_alpha = stats.norm.ppf(1 - alpha_two_sided)
    z_power = stats.norm.ppf(power)
    variance = nominal * (1 - nominal)
    return int(np.ceil(variance * ((z_alpha + z_power) / equivalence_margin) ** 2))


def enforce_resource_budget(
    *,
    wall_time_seconds: float,
    peak_memory_bytes: int,
    timeout_seconds: float,
    memory_limit_bytes: int,
) -> None:
    """Fail closed before accepting an operator run that exceeds its frozen budget."""
    values = (
        wall_time_seconds, peak_memory_bytes, timeout_seconds, memory_limit_bytes,
    )
    if any(isinstance(value, (bool, str, bytes)) for value in values):
        raise ValueError("resource measurements and limits must be finite numeric values")
    if (
        not np.isfinite(wall_time_seconds)
        or not np.isfinite(peak_memory_bytes)
        or wall_time_seconds < 0
        or peak_memory_bytes < 0
    ):
        raise ValueError("resource measurements must be non-negative")
    if (
        not np.isfinite(timeout_seconds)
        or not np.isfinite(memory_limit_bytes)
        or timeout_seconds <= 0
        or memory_limit_bytes <= 0
    ):
        raise ValueError("resource limits must be positive")
    if wall_time_seconds > timeout_seconds:
        raise RuntimeError("resource abort: wall-time limit exceeded")
    if peak_memory_bytes > memory_limit_bytes:
        raise RuntimeError("resource abort: peak-memory limit exceeded")


def estimate_correlation_length(
    coordinates: np.ndarray, values: np.ndarray, *, bins: int = 12
) -> float:
    """Estimate a conservative first empirical semivariance plateau distance."""
    coordinates = np.asarray(coordinates, dtype=float)
    values = np.asarray(values, dtype=float)
    if len(values) > 3_162:
        raise ValueError("correlation analysis exceeds five-million-pair resource limit")
    if (
        coordinates.ndim != 2
        or len(coordinates) != len(values)
        or len(values) < 4
        or not np.all(np.isfinite(coordinates))
        or not np.all(np.isfinite(values))
        or not isinstance(bins, int)
        or isinstance(bins, bool)
        or bins < 3
        or bins > min(256, len(values) * (len(values) - 1) // 2)
    ):
        raise ValueError("at least four coordinate/value pairs are required")
    distances = []
    semivariances = []
    for i in range(len(values) - 1):
        delta = coordinates[i + 1 :] - coordinates[i]
        distances.extend(np.linalg.norm(delta, axis=1))
        semivariances.extend(0.5 * (values[i + 1 :] - values[i]) ** 2)
    distances = np.asarray(distances)
    semivariances = np.asarray(semivariances)
    edges = np.linspace(0, float(distances.max()), bins + 1)
    empirical = []
    centers = []
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (distances >= low) & (distances < high)
        if mask.any():
            centers.append((low + high) / 2)
            empirical.append(float(np.median(semivariances[mask])))
    if len(empirical) < 3:
        raise ValueError("insufficient populated distance bins")
    sill = float(np.median(np.sort(empirical)[-max(2, len(empirical) // 3) :]))
    threshold = 0.95 * sill
    for center, value in zip(centers, empirical):
        if value >= threshold:
            return float(center)
    raise ValueError("empirical semivariance plateau not identified")


def buffered_cluster_split(
    centroids: np.ndarray,
    *,
    buffer_distance: float,
    seed: int,
    fractions: tuple[float, float, float] = (0.6, 0.2, 0.2),
) -> dict[str, list[int]]:
    """Outcome-blind cluster split with cross-partition buffer enforcement."""
    points = np.asarray(centroids, dtype=float)
    if points.ndim != 2 or len(points) < 3 or not np.all(np.isfinite(points)):
        raise ValueError("at least three cluster centroids are required")
    n_points = len(points)
    projected_bytes = (
        n_points * (n_points - 1) // 2 * np.dtype(float).itemsize
        + n_points * n_points * np.dtype(float).itemsize
        + n_points * n_points * np.dtype(bool).itemsize
    )
    projected_bytes = int(projected_bytes * 1.1)
    if len(points) > 5_000 or projected_bytes > 128 * 1024 * 1024:
        raise ValueError("buffered split exceeds projected distance-memory resource limit")
    if (
        not np.isfinite(buffer_distance)
        or buffer_distance < 0
        or len(fractions) != 3
        or any(not np.isfinite(value) or value < 0 or value > 1 for value in fractions)
        or not np.isclose(sum(fractions), 1)
    ):
        raise ValueError("invalid buffer or fractions")
    labels = ("train", "calibration", "test")
    targets = np.floor(np.asarray(fractions) * len(points)).astype(int)
    targets[-1] = len(points) - targets[:-1].sum()
    if np.any(targets < 1):
        raise ValueError("every buffered split partition must contain at least one cluster")
    adjacency = squareform(pdist(points)) < buffer_distance
    np.fill_diagonal(adjacency, True)
    unseen = set(range(len(points)))
    components: list[list[int]] = []
    while unseen:
        stack = [unseen.pop()]
        component = []
        while stack:
            index = stack.pop()
            component.append(index)
            neighbors = {int(value) for value in np.flatnonzero(adjacency[index])} & unseen
            unseen -= neighbors
            stack.extend(neighbors)
        components.append(sorted(component))
    order = np.random.default_rng(seed).permutation(len(components))
    components = [components[index] for index in order]
    result = {label: [] for label in labels}
    maximum_states = 100_000
    states_visited = 0

    def assign(component_index: int) -> bool:
        nonlocal states_visited
        states_visited += 1
        if states_visited > maximum_states:
            raise ValueError("deterministic buffered split search exhausted its state limit")
        if component_index == len(components):
            return all(len(result[label]) == targets[index] for index, label in enumerate(labels))
        component = components[component_index]
        for index, label in enumerate(labels):
            if len(result[label]) + len(component) <= targets[index]:
                result[label].extend(component)
                if assign(component_index + 1):
                    return True
                del result[label][-len(component):]
        return False

    if len(components) > 256:
        raise ValueError("deterministic buffered split search exceeds component limit")
    if not assign(0):
        raise ValueError(
            "deterministic component-partition search found no buffered split at exact target sizes"
        )
    return {label: sorted(indices) for label, indices in result.items()}


def exact_paired_randomization_test(
    paired_improvements: np.ndarray,
    *,
    null_improvement: float = 0.1,
) -> dict[str, Any]:
    """Exact one-sided sign randomization for small independent cluster sets."""
    values = np.asarray(paired_improvements, dtype=float)
    if values.ndim != 1 or len(values) == 0 or len(values) > 20:
        raise ValueError("exact randomization requires 1..20 paired clusters")
    if not np.all(np.isfinite(values)) or not np.isfinite(null_improvement):
        raise ValueError("paired improvements must be finite")
    centered = values - null_improvement
    observed = float(np.mean(centered))
    permutation_count = 1 << len(centered)
    exceed = 0
    for mask in range(permutation_count):
        signs = np.array(
            [1.0 if mask & (1 << index) else -1.0 for index in range(len(centered))]
        )
        exceed += float(np.mean(signs * centered)) >= observed
    return {
        "cluster_count": int(len(values)),
        "permutations": permutation_count,
        "observed_mean_above_null": observed,
        "one_sided_p": float(exceed / permutation_count),
        "test": "exact_paired_sign_randomization",
    }


def bootstrap_stability_gate(
    cluster_values: np.ndarray,
    *,
    seed: int,
    repetitions: int = 400,
    minimum_clusters: int = 20,
    maximum_relative_mc_error: float = 0.1,
) -> dict[str, Any]:
    """Permit bootstrap reporting only when cluster count and MC stability suffice."""
    values = np.asarray(cluster_values, dtype=float)
    if (
        values.ndim != 1
        or not np.all(np.isfinite(values))
        or repetitions < 200
        or minimum_clusters < 2
    ):
        raise ValueError("invalid bootstrap stability inputs")
    if len(values) < minimum_clusters:
        return {
            "passed": False,
            "reason_code": "INSUFFICIENT_INDEPENDENT_CLUSTERS_FOR_BOOTSTRAP",
            "cluster_count": int(len(values)),
            "minimum_clusters": minimum_clusters,
        }
    if float(np.var(values)) == 0:
        return {
            "passed": False,
            "reason_code": "ZERO_VARIANCE_BOOTSTRAP_UNINFORMATIVE",
            "cluster_count": int(len(values)),
        }
    rng = np.random.default_rng(seed)
    estimates = np.array([
        np.mean(rng.choice(values, size=len(values), replace=True))
        for _ in range(repetitions)
    ])
    bootstrap_sd = float(np.std(estimates, ddof=1))
    point_estimate = float(np.mean(values))
    ci_low, ci_high = np.quantile(estimates, [0.025, 0.975])
    checkpoints = (repetitions // 2, 3 * repetitions // 4, repetitions)
    summaries = np.asarray([
        [np.mean(estimates[:count]), np.std(estimates[:count], ddof=1),
         *np.quantile(estimates[:count], [0.025, 0.975])]
        for count in checkpoints
    ])
    scale = max(ci_high - ci_low, bootstrap_sd, np.finfo(float).eps)
    convergence_errors = {
        "point_estimate": float(abs(summaries[-1, 0] - summaries[-2, 0]) / scale),
        "standard_error": float(abs(summaries[-1, 1] - summaries[-2, 1]) / scale),
        "ci_low": float(abs(summaries[-1, 2] - summaries[-2, 2]) / scale),
        "ci_high": float(abs(summaries[-1, 3] - summaries[-2, 3]) / scale),
    }
    relative_mc_error = max(convergence_errors.values())
    passed = relative_mc_error <= maximum_relative_mc_error
    return {
        "passed": bool(passed),
        "reason_code": (
            "BOOTSTRAP_STABILITY_PASSED"
            if passed
            else "BOOTSTRAP_MONTE_CARLO_UNSTABLE"
        ),
        "cluster_count": int(len(values)),
        "repetitions": repetitions,
        "relative_mc_error": float(relative_mc_error),
        "point_estimate": point_estimate,
        "bootstrap_mean": float(np.mean(estimates)),
        "batch_convergence_relative_errors": convergence_errors,
        "percentile_95_interval": [float(ci_low), float(ci_high)],
        "maximum_relative_mc_error": maximum_relative_mc_error,
    }


def select_required_dimensionality(
    *,
    method: str,
    diagnostics: Mapping[str, float],
    available_solver_dimensions: tuple[str, ...],
) -> dict[str, Any]:
    """Map preregistered diagnostics to a mandatory solver dimension."""
    if method not in METHOD_NAMES or not isinstance(diagnostics, Mapping):
        raise ValueError("known method and diagnostic mapping required")
    def finite_number(value: Any) -> bool:
        return (
            not isinstance(value, (bool, str, bytes))
            and np.isscalar(value)
            and bool(np.isfinite(value))
        )

    if method in {"tem", "dc", "tdip", "sip_fdip"}:
        lateral = diagnostics.get("lateral_inconsistency")
        if (
            set(diagnostics) != {"lateral_inconsistency"}
            or not finite_number(lateral)
            or lateral < 0
        ):
            raise ValueError("lateral_inconsistency finite non-negative diagnostic required")
        required = "3d" if float(diagnostics["lateral_inconsistency"]) > 0.1 else "1d"
    elif method == "mt_amt":
        if (
            set(diagnostics) != {"skew_deg", "tipper_amplitude"}
            or not all(finite_number(diagnostics.get(key)) for key in diagnostics)
            or diagnostics["skew_deg"] < 0
            or not 0 <= diagnostics["tipper_amplitude"] <= 1
        ):
            raise ValueError("finite MT skew_deg and tipper_amplitude diagnostics required")
        required = (
            "3d" if float(diagnostics["skew_deg"]) > 6
            or float(diagnostics["tipper_amplitude"]) > 0.2
            else "2d" if float(diagnostics["skew_deg"]) > 3 else "1d"
        )
    elif method in {"csamt", "wfem"}:
        if set(diagnostics) != {"source_zone"} or diagnostics.get("source_zone") not in {
            "near", "transition", "far"
        }:
            raise ValueError("controlled-source source_zone must be near, transition, or far")
        required = (
            "3d"
            if diagnostics["source_zone"] in {"near", "transition"}
            else "1d"
        )
    else:
        if set(diagnostics) != {"requires_3d"} or not isinstance(
            diagnostics.get("requires_3d"), bool
        ):
            raise ValueError("potential-field requires_3d boolean diagnostic required")
        required = "3d"
    allowed_dimensions = {"1d", "2d", "3d"}
    available = tuple(str(value).lower() for value in available_solver_dimensions)
    if not available or any(value not in allowed_dimensions for value in available):
        raise ValueError("available solver dimensions must be non-empty allowed values")
    return {
        "method": method,
        "selected": required,
        "available_solver_dimensions": list(available),
        "status": "passed" if required in available else "failed",
        "reason_code": (
            "REQUIRED_DIMENSION_AVAILABLE"
            if required in available
            else "REQUIRED_DIMENSION_SOLVER_UNAVAILABLE"
        ),
    }
