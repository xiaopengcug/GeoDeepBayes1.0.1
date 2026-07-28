#!/usr/bin/env python
"""Freeze gravity and magnetic WP8-0 solver/reference/resource evidence."""
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

from geodeepbayes.forward import GravityOperator, MagneticOperator
from geodeepbayes.validation.feasibility import enforce_resource_budget

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/potential-path-readiness.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(count: int, method: str):
    mesh = TensorMesh(
        [[50.0] * count, [50.0] * count, [50.0] * max(2, count // 2)],
        origin=[-25.0 * count, -25.0 * count, -50.0 * max(2, count // 2)],
    )
    axis = np.linspace(-20.0 * count, 20.0 * count, count)
    x, y = np.meshgrid(axis, axis)
    receivers = np.c_[x.ravel(), y.ravel(), np.full(x.size, 25.0)]
    operator = (
        GravityOperator(mesh, receivers)
        if method == "gravity"
        else MagneticOperator(mesh, receivers, inducing_field=(50_000.0, 60.0, 20.0))
    )
    scale = 0.1 if method == "gravity" else 0.01
    return operator, np.full(operator.n_param, scale)


def measure(method: str) -> dict:
    records = []
    for count in (4, 6, 8):
        operator, model = build(count, method)
        tracemalloc.start()
        started = time.perf_counter()
        prediction = operator.predict(model)
        direction = np.linspace(-1.0, 1.0, operator.n_param)
        jvp = operator.jvp(direction, model)
        jtp = operator.jtp(np.ones(operator.n_data), model)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        records.append(
            {
                "mesh_cells": int(operator.n_param),
                "data": int(operator.n_data),
                "wall_time_seconds": elapsed,
                "peak_python_memory_bytes": peak,
                "finite": bool(
                    np.all(np.isfinite(prediction))
                    and np.all(np.isfinite(jvp))
                    and np.all(np.isfinite(jtp))
                ),
            }
        )
    max_wall = max(row["wall_time_seconds"] for row in records)
    max_memory = max(row["peak_python_memory_bytes"] for row in records)
    timeout = max(5.0, 10.0 * max_wall)
    memory_limit = max(64 * 1024 * 1024, 4 * max_memory)
    enforce_resource_budget(
        wall_time_seconds=max_wall,
        peak_memory_bytes=max_memory,
        timeout_seconds=timeout,
        memory_limit_bytes=memory_limit,
    )
    return {
        "kind": "representative 3-D development meshes; not formal WP8-1 field-scale evidence",
        "records": records,
        "timeout_seconds": timeout,
        "memory_limit_bytes": memory_limit,
        "abort_policy": "reject when measured wall time or peak memory exceeds its frozen limit",
        "negative_test": "tests/validation/test_wp8_resource_abort.py",
        "negative_test_source_sha256": sha(ROOT / "tests/validation/test_wp8_resource_abort.py"),
        "passed": all(row["finite"] for row in records),
    }


def main() -> None:
    reference_path = ROOT / "tests/forward/test_potential_independent_reference.py"
    derivative_paths = (
        ROOT / "tests/forward/test_adjoint_dot.py",
        ROOT / "tests/forward/test_taylor_remainder.py",
        ROOT / "tests/forward/test_finite_difference.py",
    )
    test_nodes = [
        f"{reference_path}::test_gravity_matches_independent_geoana_prism",
        f"{reference_path}::test_magnetic_tmi_matches_independent_geoana_prism",
        f"{derivative_paths[0]}::test_gravity_adjoint_dot",
        f"{derivative_paths[0]}::test_magnetic_adjoint_dot",
        f"{derivative_paths[1]}::test_gravity_taylor_second_order",
        f"{derivative_paths[1]}::test_magnetic_taylor_second_order",
        f"{derivative_paths[2]}::test_gravity_finite_difference",
        f"{derivative_paths[2]}::test_magnetic_finite_difference",
    ]
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *test_nodes],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    versions = {
        name: importlib.metadata.version(name)
        for name in ("simpeg", "discretize", "geoana", "numpy", "scipy")
    }
    common_reference = {
        "kind": "independent Geoana analytic rectangular-prism implementation",
        "test_path": str(reference_path.relative_to(ROOT)).replace("\\", "/"),
        "test_source_sha256": sha(reference_path),
        "pytest_exit_code": test.returncode,
        "pytest_stdout": test.stdout,
        "passed": test.returncode == 0,
    }
    payload = {
        "schema_version": "wp8-potential-path-readiness-v1",
        "formal_wp8_1_evidence": False,
        "scope": "WP8-0 path feasibility only",
        "methods": {
            "gravity": {
                "implementation": {
                    "entrypoint": "geodeepbayes.forward.gravity.GravityOperator",
                    "dependency_versions": versions,
                    "applicable_dimension": "3-D rectangular-prism volume integration",
                    "limitations": ["scalar isotropic density contrast", "research-scale in-memory sensitivity"],
                },
                "independent_reference": {
                    **common_reference,
                    "quantity": "gz for a finite rectangular prism with explicit SI-to-mGal conversion",
                },
                "resource_measurement": measure("gravity"),
            },
            "magnetic": {
                "implementation": {
                    "entrypoint": "geodeepbayes.forward.magnetic.MagneticOperator",
                    "dependency_versions": versions,
                    "applicable_dimension": "3-D rectangular-prism induced-magnetization integration",
                    "limitations": [
                        "scalar isotropic susceptibility",
                        "remanence requires MagneticVectorOperator and a provenance-backed prior",
                        "research-scale in-memory sensitivity",
                    ],
                },
                "independent_reference": {
                    **common_reference,
                    "quantity": "TMI projection of an independently magnetized finite rectangular prism",
                },
                "resource_measurement": measure("magnetic"),
            },
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pytest": test.returncode, "methods": list(payload["methods"])}))


if __name__ == "__main__":
    main()
