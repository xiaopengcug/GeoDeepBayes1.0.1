"""Immutable scenario/result contracts for validation runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ValidationScenario:
    scenario_id: str
    method: str
    preregistration_version: str
    split_root: str
    thresholds: Mapping[str, float]
    seed: int
    dimensionality: str
    baseline_id: str

    def __post_init__(self) -> None:
        for name in ("scenario_id", "method", "preregistration_version", "dimensionality", "baseline_id"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if len(self.split_root) != 64:
            raise ValueError("split_root must be a SHA-256 digest")
        object.__setattr__(self, "thresholds", MappingProxyType(dict(self.thresholds)))


@dataclass(frozen=True)
class ValidationResult:
    scenario_id: str
    status: str
    evidence_id: str
    metrics: Mapping[str, float] = field(default_factory=dict)
    failure_reasons: tuple[Mapping[str, str], ...] = field(default_factory=tuple)
    raw_prediction_root: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"passed", "failed", "blocked"}:
            raise ValueError("invalid validation status")
        if not self.scenario_id or not self.evidence_id:
            raise ValueError("scenario_id and evidence_id are required")
        if self.status != "passed" and not self.failure_reasons:
            raise ValueError("failed/blocked results require machine-readable reasons")
        if self.raw_prediction_root is not None and len(self.raw_prediction_root) != 64:
            raise ValueError("raw_prediction_root must be a SHA-256 digest")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
        object.__setattr__(
            self,
            "failure_reasons",
            tuple(MappingProxyType(dict(reason)) for reason in self.failure_reasons),
        )
