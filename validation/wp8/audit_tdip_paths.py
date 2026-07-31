#!/usr/bin/env python
"""Freeze TDIP WP8-0 implementation/reference/resource path evidence."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np
from discretize import TensorMesh

from geodeepbayes.forward import DipoleDipoleSurvey, TDIPOperator
from geodeepbayes.validation.feasibility import enforce_resource_budget

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/tdip-path-readiness.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(count: int) -> tuple[TDIPOperator, np.ndarray]:
    mesh = TensorMesh([[8.0] * count] * 3, origin=[-4 * count, -4 * count, -8 * count])
    survey = DipoleDipoleSurvey(
        a=np.array([[-8.0, 0, 0]]),
        b=np.array([[-4.0, 0, 0]]),
        m=np.array([[4.0, 0, 0]]),
        n=np.array([[8.0, 0, 0]]),
        current=np.array([1.0]),
    )
    operator = TDIPOperator(
        mesh, survey, [0.01, 0.03], background_conductivity=0.02, tau=0.1, exponent_c=0.6
    )
    return operator, np.full(operator.n_param, 0.05)


def main() -> None:
    test_path = ROOT / "tests/forward/test_static_operators.py"
    test = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"{test_path}::test_tdip_forward_taylor_adjoint_and_wrong_convention",
            f"{test_path}::test_tdip_three_level_mesh_convergence",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    measurements = []
    for count in (3, 5, 7):
        operator, model = build(count)
        tracemalloc.start()
        started = time.perf_counter()
        prediction = operator.predict(model)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        measurements.append(
            {
                "mesh_cells": int(operator.n_param),
                "data": int(operator.n_data),
                "wall_time_seconds": elapsed,
                "peak_python_memory_bytes": peak,
                "finite": bool(np.all(np.isfinite(prediction))),
            }
        )
    max_wall = max(row["wall_time_seconds"] for row in measurements)
    max_memory = max(row["peak_python_memory_bytes"] for row in measurements)
    timeout = max(5.0, 10.0 * max_wall)
    memory_limit = max(64 * 1024 * 1024, 4 * max_memory)
    enforce_resource_budget(
        wall_time_seconds=max_wall,
        peak_memory_bytes=max_memory,
        timeout_seconds=timeout,
        memory_limit_bytes=memory_limit,
    )
    payload = {
        "schema_version": "wp8-tdip-path-readiness-v1",
        "formal_wp8_1_evidence": False,
        "scope": "WP8-0 path feasibility only",
        "implementation": {
            "entrypoint": "geodeepbayes.forward.static.TDIPOperator",
            "dependency_versions": {
                name: importlib.metadata.version(name)
                for name in ("simpeg", "discretize", "numpy", "scipy", "pymatsolver")
            },
            "applicable_dimension": "2-D profile represented on a 3-D tensor mesh with scalar isotropic cells",
            "limitations": [
                "research-scale SolverLU",
                "explicit sensitivity matrix from verified Jvec",
                "no topography, anisotropy, contact impedance or EM-coupling path",
            ],
        },
        "independent_reference": {
            "kind": "independent pulse-decay construction and three-level mesh discretization",
            "test_path": str(test_path.relative_to(ROOT)).replace("\\", "/"),
            "test_source_sha256": sha(test_path),
            "pytest_exit_code": test.returncode,
            "passed": test.returncode == 0,
        },
        "resource_measurement": {
            "kind": "representative development meshes; not formal WP8-1 field-scale evidence",
            "records": measurements,
            "timeout_seconds": timeout,
            "memory_limit_bytes": memory_limit,
            "abort_policy": "reject when measured wall time or peak memory exceeds its frozen limit",
            "negative_test": "tests/validation/test_wp8_resource_abort.py",
            "negative_test_source_sha256": sha(ROOT / "tests/validation/test_wp8_resource_abort.py"),
            "passed": all(row["finite"] for row in measurements),
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reference": test.returncode, "records": len(measurements), "timeout": timeout}))


if __name__ == "__main__":
    main()
