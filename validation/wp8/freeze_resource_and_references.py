#!/usr/bin/env python
"""Freeze measured development costs and registered independent references."""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent / "evidence/feasibility-v1"
TIMINGS = Path(__file__).resolve().parent / "evidence/development-synthetic/raw-timings.json"

REFERENCES = {
    "gravity": {"type": "SimPEG analytic-integral regression", "test": "tests/forward/test_interface_and_vector.py"},
    "magnetic": {"type": "SimPEG vector-integral regression", "test": "tests/forward/test_interface_and_vector.py"},
    "dc": {"type": "homogeneous half-space analytic reference", "test": "tests/forward/test_static_operators.py"},
    "tdip": {"type": "independent pulse-decay construction plus derivative checks", "test": "tests/forward/test_static_operators.py"},
    "sip_fdip": {"type": "Cole-Cole homogeneous half-space analytic reference", "test": "tests/forward/test_static_operators.py"},
    "tem": {"type": "independent digital-linear-filter refinement", "test": "tests/forward/test_em1d.py"},
    "mt_amt": {"type": "layered-earth analytic impedance reference", "test": "tests/forward/test_em1d.py"},
    "csamt": {"type": "Geoana finite-wire Ex reference", "test": "tests/forward/test_controlled_source.py"},
    "wfem": {"type": "independent mesh-discretization refinement", "test": "tests/forward/test_controlled_source.py"},
}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    raw = json.loads(TIMINGS.read_text(encoding="utf-8"))
    methods = {}
    for method, payload in raw["methods"].items():
        passed = [row for row in payload["records"] if row["status"] == "passed"]
        methods[method] = {
            "measurement": "perf_counter_ns wall time",
            "record_count": len(passed),
            "minimum_elapsed_ns": min(row["elapsed_ns"] for row in passed),
            "maximum_elapsed_ns": max(row["elapsed_ns"] for row in passed),
            "maximum_observed_n_param": max(row["n_param"] for row in passed),
            "maximum_observed_n_data": max(row["n_data"] for row in passed),
            "peak_memory_bytes": None,
            "formal_field_scale_extrapolation": None,
            "status": "blocked",
            "reason": "development wall time is measured, but peak memory and formal field scale were not measured",
        }
    resource = {
        "schema_version": "wp8-development-resource-freeze-v1",
        "source_sha256_required": "protected by the enclosing WP8 evidence manifest",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
        },
        "cross_method_ranking_forbidden": True,
        "formal_wp8_1_evidence": False,
        "methods": methods,
    }
    references = {
        "schema_version": "wp8-independent-reference-record-v1",
        "formal_wp8_1_evidence": False,
        "methods": {
            method: {
                **reference,
                "test_exists": (ROOT / reference["test"]).is_file(),
                "status": "candidate",
                "reason": "registered development reference; formal readiness still requires protected test output and field-scale applicability",
            }
            for method, reference in REFERENCES.items()
        },
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    write(EVIDENCE / "resource-budget-freeze.json", resource)
    write(EVIDENCE / "independent-reference-record.json", references)
    print(json.dumps({"methods": len(methods), "status": "blocked"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
