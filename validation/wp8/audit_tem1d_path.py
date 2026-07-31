#!/usr/bin/env python
"""Freeze the conditional TEM 1-D WP8-0 solver/reference/resource evidence."""
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

from geodeepbayes.forward import TEM1DLayeredOperator
from geodeepbayes.validation.feasibility import enforce_resource_budget

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/tem1d-path-readiness.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(count: int):
    operator = TEM1DLayeredOperator(
        [20.0, 40.0],
        np.geomspace(1e-5, 1e-3, count),
        loop_radius=10.0,
        current=2.0,
        dimensionality_diagnostic=[0.03, 0.07],
        time_filter="key_81_2009",
    )
    return operator, np.log([0.01, 0.1, 0.02])


def measure() -> dict:
    records = []
    for count in (9, 33, 129):
        operator, model = build(count)
        tracemalloc.start()
        started = time.perf_counter()
        prediction = operator.predict(model)
        jvp = operator.jvp(np.array([0.1, -0.1, 0.05]), model)
        jtp = operator.jtp(np.ones(operator.n_data), model)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        records.append(
            {
                "time_channels": count,
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
        "kind": "representative layered 1-D time-channel scales; conditional on field dimensionality selecting 1-D",
        "records": records,
        "timeout_seconds": timeout,
        "memory_limit_bytes": memory_limit,
        "abort_policy": "reject when measured wall time or peak memory exceeds its frozen limit",
        "negative_test": "tests/validation/test_wp8_resource_abort.py",
        "negative_test_source_sha256": sha(ROOT / "tests/validation/test_wp8_resource_abort.py"),
        "passed": all(row["finite"] for row in records),
    }


def main() -> None:
    test_path = ROOT / "tests/forward/test_em1d.py"
    nodes = [
        f"{test_path}::test_tem_forward_derivatives_and_independent_filter_reference",
        f"{test_path}::test_tem_three_level_time_resolution_convergence",
        f"{test_path}::test_tem_dimensionality_upgrade_and_3d_path_fail_closed",
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
        "schema_version": "wp8-tem1d-path-readiness-v1",
        "formal_wp8_1_evidence": False,
        "scope": "WP8-0 conditional 1-D path feasibility only",
        "implementation": {
            "entrypoint": "geodeepbayes.forward.em1d.TEM1DLayeredOperator",
            "dependency_versions": {
                name: importlib.metadata.version(name)
                for name in ("simpeg", "discretize", "libdlf", "numpy", "scipy")
            },
            "applicable_dimension": "1-D layered earth only",
            "fail_closed": "DimensionalityUpgradeRequired when diagnostic exceeds 1-D threshold",
        },
        "independent_reference": {
            "kind": "independent Key 81/2009 versus Key 201/2012 digital-filter discretizations",
            "quantity": "signed loop-source TEM transient",
            "test_path": str(test_path.relative_to(ROOT)).replace("\\", "/"),
            "test_source_sha256": sha(test_path),
            "pytest_exit_code": test.returncode,
            "pytest_stdout": test.stdout,
            "passed": test.returncode == 0,
        },
        "resource_measurement": measure(),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pytest": test.returncode, "method": "tem"}))


if __name__ == "__main__":
    main()
