"""Validation primitives used by auditable work-package gates."""

from .feasibility import (
    METHOD_NAMES,
    FeasibilityDecision,
    evaluate_feasibility,
)
from .models import ValidationResult, ValidationScenario

__all__ = [
    "METHOD_NAMES",
    "FeasibilityDecision",
    "ValidationResult",
    "ValidationScenario",
    "evaluate_feasibility",
]
