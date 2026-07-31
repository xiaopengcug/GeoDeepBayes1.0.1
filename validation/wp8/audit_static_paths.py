#!/usr/bin/env python
"""Freeze DC and SIP/FDIP WP8-0 solver/reference/resource evidence."""
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

from geodeepbayes.forward import ColeCole2DOperator, DCOperator, DipoleDipoleSurvey
from geodeepbayes.validation.feasibility import enforce_resource_budget

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/static-path-readiness.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def survey() -> DipoleDipoleSurvey:
    return DipoleDipoleSurvey(
        a=np.array([[-20.0, 0.0, 0.0], [-15.0, 0.0, 0.0]]),
        b=np.array([[-15.0, 0.0, 0.0], [-10.0, 0.0, 0.0]]),
        m=np.array([[-5.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
        n=np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]]),
        current=np.array([1.0, 0.5]),
    )


def build(method: str, count: int):
    geometry = survey()
    if method == "dc":
        mesh = TensorMesh(
            [[10.0] * count, [10.0] * count, [10.0] * max(3, count - 1)],
            origin=[-5.0 * count, -5.0 * count, -10.0 * max(3, count - 1)],
        )
        operator = DCOperator(mesh, geometry)
        model = np.full(operator.n_param, np.log(0.02))
    else:
        mesh = TensorMesh(
            [[80.0 / count] * count, [60.0 / 3] * 3],
            origin=[-40.0, -60.0],
        )
        operator = ColeCole2DOperator(
            mesh,
            geometry,
            np.geomspace(0.1, 1000.0, max(2, count - 2)),
            nky=7,
        )
        block = np.array([np.log(0.02), -1.2, np.log(0.1), 0.3])
        model = np.concatenate(
            [np.full(mesh.n_cells, value) for value in block]
        )
    return operator, model


def measure(method: str) -> dict:
    records = []
    for count in (4, 5, 6):
        operator, model = build(method, count)
        tracemalloc.start()
        started = time.perf_counter()
        prediction = operator.predict(model)
        jvp = operator.jvp(np.linspace(-0.1, 0.1, operator.n_param), model)
        jtp = operator.jtp(np.ones(operator.n_data), model)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        records.append(
            {
                "scale": count,
                "parameters": int(operator.n_param),
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
        "kind": "representative WP8-0 development scales; not formal WP8-1 field scale",
        "records": records,
        "timeout_seconds": timeout,
        "memory_limit_bytes": memory_limit,
        "abort_policy": "reject when measured wall time or peak memory exceeds its frozen limit",
        "negative_test": "tests/validation/test_wp8_resource_abort.py",
        "negative_test_source_sha256": sha(ROOT / "tests/validation/test_wp8_resource_abort.py"),
        "passed": all(row["finite"] for row in records),
    }


def main() -> None:
    test_path = ROOT / "tests/forward/test_static_operators.py"
    nodes = [
        f"{test_path}::test_dc_forward_derivatives_and_halfspace_reference",
        f"{test_path}::test_dc_three_level_mesh_convergence",
        f"{test_path}::test_cole_cole_complex_reference_derivatives_and_limits",
        f"{test_path}::test_cole_cole_three_level_frequency_qoi_convergence",
        f"{test_path}::test_cole_cole_2d_complex_limit_derivatives_and_geometry",
        f"{test_path}::test_cole_cole_2d_three_level_homogeneous_convergence",
    ]
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *nodes],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    versions = {
        name: importlib.metadata.version(name)
        for name in ("simpeg", "discretize", "numpy", "scipy")
    }
    common = {
        "test_path": str(test_path.relative_to(ROOT)).replace("\\", "/"),
        "test_source_sha256": sha(test_path),
        "pytest_exit_code": test.returncode,
        "pytest_stdout": test.stdout,
        "passed": test.returncode == 0,
    }
    payload = {
        "schema_version": "wp8-static-path-readiness-v1",
        "formal_wp8_1_evidence": False,
        "scope": "WP8-0 path feasibility only",
        "methods": {
            "dc": {
                "implementation": {
                    "entrypoint": "geodeepbayes.forward.static.DCOperator",
                    "dependency_versions": versions,
                    "applicable_dimension": "3-D nodal finite-volume galvanic DC",
                },
                "independent_reference": {
                    **common,
                    "kind": "analytic homogeneous-halfspace geometric-factor implementation",
                    "quantity": "signed voltage for explicit ABMN geometry and injected current",
                },
                "resource_measurement": measure("dc"),
            },
            "sip_fdip": {
                "implementation": {
                    "entrypoint": "geodeepbayes.forward.static.ColeCole2DOperator",
                    "dependency_versions": versions,
                    "applicable_dimension": "2-D profile with 2.5-D nodal finite-volume physics",
                    "limitations": [
                        "ABMN electrodes must be coplanar",
                        "explicit finite-difference transpose is limited to WP8-0 scale",
                    ],
                },
                "independent_reference": {
                    **common,
                    "kind": "analytic homogeneous-halfspace complex Cole-Cole reference",
                    "quantity": "complex voltage, zero-IP DC limit, derivatives, and three-level mesh convergence",
                },
                "resource_measurement": measure("sip_fdip"),
            },
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pytest": test.returncode, "methods": list(payload["methods"])}))


if __name__ == "__main__":
    main()
