#!/usr/bin/env python
"""Freeze MT 3-D WP8-0 solver/reference/resource evidence."""
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

from geodeepbayes.forward import MT3DOperator
from geodeepbayes.validation.feasibility import enforce_resource_budget

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/mt3d-path-readiness.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(mesh_count: int, station_count: int, frequency_count: int):
    extent = 1200.0
    width = extent / mesh_count
    mesh = TensorMesh(
        [[width] * mesh_count] * 3,
        origin=[-extent / 2, -extent / 2, -extent],
    )
    side = int(np.ceil(np.sqrt(station_count)))
    axis = np.linspace(-0.4 * extent, 0.4 * extent, side)
    x, y = np.meshgrid(axis, axis)
    locations = np.c_[
        x.ravel()[:station_count],
        y.ravel()[:station_count],
        np.zeros(station_count),
    ]
    frequencies = np.geomspace(0.01, 1.0, frequency_count)
    conductivity = 0.01
    operator = MT3DOperator(
        mesh,
        locations,
        frequencies,
        primary_conductivity=conductivity,
        include_tipper=True,
    )
    return operator, np.full(mesh.n_cells, np.log(conductivity))


def measure() -> dict:
    records = []
    for mesh_count, station_count, frequency_count in (
        (4, 16, 1),
        (6, 64, 2),
        (8, 336, 3),
    ):
        operator, model = build(mesh_count, station_count, frequency_count)
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
                "stations": station_count,
                "frequencies": frequency_count,
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
    timeout = max(30.0, 10.0 * max_wall)
    memory_limit = max(256 * 1024 * 1024, 4 * max_memory)
    enforce_resource_budget(
        wall_time_seconds=max_wall,
        peak_memory_bytes=max_memory,
        timeout_seconds=timeout,
        memory_limit_bytes=memory_limit,
    )
    return {
        "kind": (
            "WP8-0 path scales ending at 336 stations, 3 frequencies and 512 cells; "
            "not a formal WP8-1 30-frequency production mesh"
        ),
        "records": records,
        "timeout_seconds": timeout,
        "memory_limit_bytes": memory_limit,
        "abort_policy": "reject when measured wall time or peak memory exceeds its frozen limit",
        "negative_test": "tests/validation/test_wp8_resource_abort.py",
        "negative_test_source_sha256": sha(ROOT / "tests/validation/test_wp8_resource_abort.py"),
        "passed": all(row["finite"] for row in records),
    }


def main() -> None:
    test_path = ROOT / "tests/forward/test_mt3d.py"
    nodes = [
        f"{test_path}::test_mt3d_homogeneous_halfspace_independent_analytic_reference",
        f"{test_path}::test_mt3d_derivative_adjoint_and_finite_difference",
        f"{test_path}::test_mt3d_three_level_boundary_convergence",
    ]
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *nodes],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    payload = {
        "schema_version": "wp8-mt3d-path-readiness-v1",
        "formal_wp8_1_evidence": False,
        "scope": "WP8-0 selected 3-D path feasibility",
        "implementation": {
            "entrypoint": "geodeepbayes.forward.mt3d.MT3DOperator",
            "dependency_versions": {
                name: importlib.metadata.version(name)
                for name in ("simpeg", "discretize", "numpy", "scipy", "pymatsolver")
            },
            "applicable_dimension": "3-D primary-secondary natural-source Maxwell",
            "outputs": ["Zxx", "Zxy", "Zyx", "Zyy", "Tx", "Ty"],
        },
        "independent_reference": {
            "kind": "analytic homogeneous-halfspace impedance and zero-tipper reference",
            "quantity": "full complex impedance tensor and tipper",
            "test_path": str(test_path.relative_to(ROOT)).replace("\\", "/"),
            "test_source_sha256": sha(test_path),
            "pytest_exit_code": test.returncode,
            "pytest_stdout": test.stdout,
            "passed": test.returncode == 0,
        },
        "resource_measurement": measure(),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pytest": test.returncode, "method": "mt_amt"}))


if __name__ == "__main__":
    main()
