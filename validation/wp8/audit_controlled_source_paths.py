#!/usr/bin/env python
"""Freeze CSAMT and WFEM WP8-0 solver/reference/resource evidence."""
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

from geodeepbayes.forward import CSAMTOperator, WFEMOperator
from geodeepbayes.validation.feasibility import enforce_resource_budget

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/controlled-source-path-readiness.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(method: str, count: int):
    width = 20.0
    extent = width * count
    mesh = TensorMesh(
        [[width] * count] * 3,
        origin=[-extent / 2, -extent / 2, -extent / 2],
    )
    vertices = np.array([[-20.0, 0.0, -10.0], [20.0, 0.0, -10.0]])
    receivers = np.array([[40.0, 0.0, -10.0]])
    if method == "csamt":
        operator = CSAMTOperator(mesh, vertices, receivers, [5.0], current=1.0)
    else:
        operator = WFEMOperator(
            mesh,
            vertices,
            receivers,
            [5.0],
            current=1.0,
            apparent_resistivity_definition="not_available",
        )
    return operator, np.full(mesh.n_cells, np.log(0.02))


def measure(method: str) -> dict:
    records = []
    for count in (4, 5, 6):
        operator, model = build(method, count)
        direction = np.linspace(-0.1, 0.1, operator.n_param)
        tracemalloc.start()
        started = time.perf_counter()
        prediction = operator.predict(model)
        jvp = operator.jvp(direction, model)
        jtp = operator.jtp(np.ones(operator.n_data, dtype=complex), model)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        records.append(
            {
                "mesh_cells": int(operator.n_param),
                "complex_data": int(operator.n_data),
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
    timeout = max(10.0, 10.0 * max_wall)
    memory_limit = max(128 * 1024 * 1024, 4 * max_memory)
    enforce_resource_budget(
        wall_time_seconds=max_wall,
        peak_memory_bytes=max_memory,
        timeout_seconds=timeout,
        memory_limit_bytes=memory_limit,
    )
    return {
        "kind": "representative 3-D development meshes; not formal WP8-1 field scale",
        "records": records,
        "timeout_seconds": timeout,
        "memory_limit_bytes": memory_limit,
        "abort_policy": "reject when measured wall time or peak memory exceeds its frozen limit",
        "negative_test": "tests/validation/test_wp8_resource_abort.py",
        "negative_test_source_sha256": sha(ROOT / "tests/validation/test_wp8_resource_abort.py"),
        "passed": all(row["finite"] for row in records),
    }


def main() -> None:
    test_path = ROOT / "tests/forward/test_controlled_source.py"
    nodes = [
        f"{test_path}::test_csamt_real_simpeg_path_and_geoana_reference",
        f"{test_path}::test_csamt_derivatives_taylor_and_adjoint",
        f"{test_path}::test_wfem_independent_contract_and_apparent_resistivity",
        f"{test_path}::test_wfem_three_level_discretization_convergence",
        f"{test_path}::test_zones_and_contract_misspecification_fail",
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
        for name in ("simpeg", "discretize", "geoana", "numpy", "scipy", "pymatsolver")
    }
    common = {
        "test_path": str(test_path.relative_to(ROOT)).replace("\\", "/"),
        "test_source_sha256": sha(test_path),
        "pytest_exit_code": test.returncode,
        "pytest_stdout": test.stdout,
        "passed": test.returncode == 0,
    }
    payload = {
        "schema_version": "wp8-controlled-source-path-readiness-v1",
        "formal_wp8_1_evidence": False,
        "scope": "WP8-0 path feasibility only",
        "methods": {
            "csamt": {
                "implementation": {
                    "entrypoint": "geodeepbayes.forward.controlled_source.CSAMTOperator",
                    "dependency_versions": versions,
                    "applicable_dimension": "3-D finite-line grounded-source Maxwell",
                },
                "independent_reference": {
                    **common,
                    "kind": "Geoana whole-space electric-dipole reference plus explicit source-zone contract",
                    "quantity": "complex Ex and CSAMT Ex/Hy apparent resistivity",
                },
                "resource_measurement": measure("csamt"),
            },
            "wfem": {
                "implementation": {
                    "entrypoint": "geodeepbayes.forward.controlled_source.WFEMOperator",
                    "dependency_versions": versions,
                    "applicable_dimension": "3-D finite-line waveform-frequency Maxwell",
                },
                "independent_reference": {
                    **common,
                    "kind": "Geoana whole-space electric-dipole reference, explicit geometric-factor identity, and three-level discretization convergence",
                    "quantity": "complex Ex/Ey and explicitly defined apparent resistivity",
                },
                "resource_measurement": measure("wfem"),
            },
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pytest": test.returncode, "methods": list(payload["methods"])}))


if __name__ == "__main__":
    main()
