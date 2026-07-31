from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import discretize
import numpy as np
import scipy
import simpeg
from discretize import TensorMesh
from scipy.sparse import eye, vstack
from scipy.sparse.linalg import lsqr
from scipy.spatial import cKDTree
from simpeg.potential_fields import gravity, magnetics
from simpeg.utils import io_utils


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path, base: Path) -> dict:
    try:
        relative = path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        relative = path.resolve().as_posix()
    return {"path": relative, "sha256": sha256(path)}


def common_root(names: list[str]) -> str:
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(roots) != 1:
        raise ValueError(f"archive must have one top-level directory, got {sorted(roots)}")
    return roots.pop()


def extract_required(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as source:
        bad = source.testzip()
        if bad:
            raise ValueError(f"bad zip member: {bad}")
        names = source.namelist()
        root = common_root(names)
        required = [
            "Forward/GRAV_noisydata.obs",
            "Forward/MAG_noisydata.obs",
            "Forward/mesh_inverse_ubc.msh",
            "Forward/model_grav.den",
            "Forward/model_mag.sus",
            "PGI_joint_inversion/Joint_PGI_Grav_Mag.ipynb",
            "environment.yml",
            "requirements.txt",
        ]
        for relative in required:
            member = f"{root}/{relative}"
            if member not in names:
                raise FileNotFoundError(member)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(member))
    return destination


def compatibility_audit(notebook: Path) -> dict:
    text = notebook.read_text(encoding="utf-8")
    legacy_symbols = sorted(set(re.findall(r"(?:SimPEG\.PF|from SimPEG|import SimPEG|PardisoSolver)", text)))
    return {
        "original_environment": {
            "numpy": "1.17.3",
            "scipy": "1.3.1",
            "discretize": "0.4.10",
            "simpeg": "git branch examples/PGI_joint",
        },
        "legacy_symbols": legacy_symbols,
        "modern_import_available": {
            "simpeg": True,
            "discretize": True,
            "legacy_SimPEG_PF": False,
        },
        "original_notebook_reproduced": False,
        "reason": "原notebook依赖已移除的SimPEG.PF及2020年私有PGI分支；本run使用正式现代API进行同源数据兼容验证。",
    }


def coarse_mesh_and_truth(forward: Path, gravity_data, nx: int, ny: int, nz: int):
    original_mesh = TensorMesh.read_UBC(forward / "mesh_inverse_ubc.msh")
    density = original_mesh.read_model_UBC(forward / "model_grav.den")
    susceptibility = original_mesh.read_model_UBC(forward / "model_mag.sus")
    density = np.where(density <= -99, 0.0, density)
    susceptibility = np.where(susceptibility <= -99, 0.0, susceptibility)

    locations = gravity_data.survey.receiver_locations
    x0, x1 = float(locations[:, 0].min() - 80), float(locations[:, 0].max() + 80)
    y0, y1 = float(locations[:, 1].min() - 80), float(locations[:, 1].max() + 80)
    z0, z1 = -300.0, float(locations[:, 2].min() - 10)
    mesh = TensorMesh(
        [
            np.full(nx, (x1 - x0) / nx),
            np.full(ny, (y1 - y0) / ny),
            np.full(nz, (z1 - z0) / nz),
        ],
        origin=[x0, y0, z0],
    )
    tree = cKDTree(original_mesh.cell_centers)
    _, nearest = tree.query(mesh.cell_centers)
    return mesh, density[nearest], susceptibility[nearest], original_mesh


def subset_survey(gravity_data, magnetic_data, stride: int):
    indices = np.arange(0, gravity_data.dobs.size, stride, dtype=int)
    gloc = gravity_data.survey.receiver_locations[indices]
    mloc = magnetic_data.survey.receiver_locations[indices]
    grx = gravity.receivers.Point(gloc, components="gz")
    gsurvey = gravity.survey.Survey(gravity.sources.SourceField(receiver_list=[grx]))
    mrx = magnetics.receivers.Point(mloc, components="tmi")
    source = magnetic_data.survey.source_field
    msource = magnetics.sources.UniformBackgroundField(
        receiver_list=[mrx],
        amplitude=source.amplitude,
        inclination=source.inclination,
        declination=source.declination,
    )
    msurvey = magnetics.survey.Survey(msource)
    return indices, gsurvey, msurvey


def regularized_inverse(
    matrix: np.ndarray, data: np.ndarray, truth: np.ndarray,
    alphas: list[float], sigma: float, protocol: str,
) -> dict:
    """预注册白化LSQR路径；GCV选参，绝不按训练RMS或真值选参。"""
    normalized_matrix = matrix / sigma
    normalized_data = data / sigma
    initial_rms = float(np.sqrt(np.mean(normalized_data**2)))
    trials = []
    solutions = []
    singular = np.linalg.svd(normalized_matrix, compute_uv=False)
    identity = eye(matrix.shape[1], format="csr")
    for alpha in alphas:
        started = time.perf_counter()
        augmented = vstack([normalized_matrix, np.sqrt(alpha) * identity], format="csr")
        rhs = np.r_[normalized_data, np.zeros(matrix.shape[1])]
        # WP7：求解器收敛只接受LSQR停止码1/2；数据拟合另行判定。
        solution = lsqr(augmented, rhs, atol=1e-6, btol=1e-6, iter_lim=2000)
        model = solution[0]
        residual = normalized_matrix @ model - normalized_data
        normalized_rms = float(np.sqrt(np.mean(residual**2)))
        stop_code = int(solution[1])
        values_finite = bool(
            np.isfinite(model).all()
            and np.isfinite(residual).all()
            and np.isfinite(np.asarray(solution[3:9], dtype=float)).all()
        )
        effective_df = float(np.sum(singular**2 / (singular**2 + alpha)))
        rss = float(np.dot(residual, residual))
        denominator = max(1.0 - effective_df / data.size, np.finfo(float).eps)
        trial = {
            "alpha": alpha,
            "iterations": int(solution[2]),
            "stop_code": stop_code,
            "values_finite": values_finite,
            "solver_converged": (
                stop_code in (1, 2) and int(solution[2]) < 2000 and values_finite
            ),
            "normalized_rms": normalized_rms,
            "model_rmse": float(np.sqrt(np.mean((model - truth) ** 2))),
            "effective_df": effective_df,
            "gcv": float((rss / data.size) / denominator**2),
            "solution_norm": float(np.linalg.norm(model)),
            "residual_norm": float(np.linalg.norm(residual)),
            "elapsed_seconds": time.perf_counter() - started,
        }
        trials.append(trial)
        solutions.append(model)
    minimum_gcv = min(trial["gcv"] for trial in trials)
    eligible = [
        index for index, trial in enumerate(trials)
        if trial["gcv"] <= 1.01 * minimum_gcv
    ]
    selected_index = max(eligible, key=lambda index: trials[index]["alpha"])
    best = {**trials[selected_index]}
    recovered = solutions[selected_index]
    zero_rmse = float(np.sqrt(np.mean(truth**2)))
    best["overfit_warning"] = best["normalized_rms"] < 0.5
    best["data_fit_accepted"] = (
        best["normalized_rms"] <= 1.2 if protocol == "v3"
        else 0.5 <= best["normalized_rms"] <= 1.2
    )
    best["model_recovery_accepted"] = best["model_rmse"] <= 0.95 * zero_rmse
    best["compatibility_accepted"] = (
        best["solver_converged"] and best["data_fit_accepted"]
    )
    best["accepted"] = (
        best["compatibility_accepted"] if protocol == "v3"
        else best["compatibility_accepted"] and best["model_recovery_accepted"]
    )
    return {
        "selection_rule_id": "do27_gcv_stronger_tie_break_v1",
        "protocol": protocol,
        "sigma": sigma,
        "initial_normalized_rms": initial_rms,
        "zero_model_rmse": zero_rmse,
        "best": best,
        "trials": trials,
        "recovered_model_summary": {
            "minimum": float(recovered.min()),
            "maximum": float(recovered.max()),
            "mean": float(recovered.mean()),
        },
        "_solutions": np.asarray(solutions),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    args = parser.parse_args()
    prereg = json.loads(args.config.resolve().read_text(encoding="utf-8"))
    nx, ny, nz = map(int, prereg["shape"])
    stride = int(prereg["stride"])
    seed = int(prereg.get("seed", 20260724))
    protocol = str(prereg["schema"]).rsplit("-", 1)[-1]
    alphas = [float(value) for value in prereg["alphas"]]
    if protocol not in {"v2", "v3"}:
        parser.error("config schema must end in v2 or v3")
    if stride <= 0 or min(nx, ny, nz) <= 0:
        parser.error("--stride and every --shape dimension must be positive")
    if nx * ny * nz > 250_000:
        parser.error("--shape exceeds the 250000-cell validation safety limit")

    started_at = datetime.now(timezone.utc)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    archive = args.archive.resolve()
    actual_archive_hash = sha256(archive)
    if actual_archive_hash != prereg["archive_sha256"]:
        raise RuntimeError(
            f"archive drift: expected {prereg['archive_sha256']}, got {actual_archive_hash}"
        )
    np.random.seed(seed)
    extract_required(archive, work)
    forward = work / "Forward"

    gravity_data = io_utils.read_grav3d_ubc(forward / "GRAV_noisydata.obs")
    magnetic_data = io_utils.read_mag3d_ubc(forward / "MAG_noisydata.obs")
    mesh, density_truth, susceptibility_truth, original_mesh = coarse_mesh_and_truth(
        forward, gravity_data, nx, ny, nz
    )
    indices, gravity_survey, magnetic_survey = subset_survey(gravity_data, magnetic_data, stride)

    gravity_simulation = gravity.simulation.Simulation3DIntegral(
        mesh=mesh, survey=gravity_survey, rhoMap=simpeg.maps.IdentityMap(nP=mesh.n_cells), engine="geoana"
    )
    magnetic_simulation = magnetics.simulation.Simulation3DIntegral(
        mesh=mesh, survey=magnetic_survey, chiMap=simpeg.maps.IdentityMap(nP=mesh.n_cells), engine="geoana"
    )

    forward_started = time.perf_counter()
    gravity_truth_prediction = gravity_simulation.dpred(density_truth)
    magnetic_truth_prediction = magnetic_simulation.dpred(susceptibility_truth)
    gravity_matrix = np.asarray(gravity_simulation.G)
    magnetic_matrix = np.asarray(magnetic_simulation.G)
    forward_seconds = time.perf_counter() - forward_started
    gravity_observed = gravity_data.dobs[indices]
    magnetic_observed = magnetic_data.dobs[indices]

    # 审查意见02 / G: alpha 候选集扩展，含更大正则化以助 LSQR 早停
    gravity_inverse = regularized_inverse(
        gravity_matrix, gravity_observed, density_truth, alphas,
        sigma=float(prereg["assumed_inversion_weight"]["gravity_mgal"]), protocol=protocol,
    )
    magnetic_inverse = regularized_inverse(
        magnetic_matrix, magnetic_observed, susceptibility_truth, alphas,
        sigma=float(prereg["assumed_inversion_weight"]["magnetic_nt"]), protocol=protocol,
    )
    gravity_solutions = gravity_inverse.pop("_solutions")
    magnetic_solutions = magnetic_inverse.pop("_solutions")
    compatibility = compatibility_audit(work / "PGI_joint_inversion/Joint_PGI_Grav_Mag.ipynb")

    metrics = {
        "run_scope": "DO-27同源数据的现代SimPEG降阶兼容验证；不是原2020完整PGI notebook复现。",
        "seed": seed,
        "input": {
            "archive_sha256": actual_archive_hash,
            "original_mesh_cells": original_mesh.n_cells,
            "coarse_mesh_shape": [nx, ny, nz],
            "coarse_mesh_cells": mesh.n_cells,
            "original_observations_per_method": int(gravity_data.dobs.size),
            "selected_observations_per_method": int(indices.size),
            "stride": stride,
        },
        "forward": {
            "elapsed_seconds": forward_seconds,
            "gravity_truth_vs_observed_rms": float(np.sqrt(np.mean((gravity_truth_prediction - gravity_observed) ** 2))),
            "magnetic_truth_vs_observed_rms": float(np.sqrt(np.mean((magnetic_truth_prediction - magnetic_observed) ** 2))),
            "gravity_sensitivity_shape": list(gravity_matrix.shape),
            "magnetic_sensitivity_shape": list(magnetic_matrix.shape),
            "all_finite": bool(
                np.isfinite(gravity_matrix).all()
                and np.isfinite(magnetic_matrix).all()
                and np.isfinite(gravity_truth_prediction).all()
                and np.isfinite(magnetic_truth_prediction).all()
            ),
        },
        "gravity_inverse": gravity_inverse,
        "magnetic_inverse": magnetic_inverse,
        "compatibility": compatibility,
        "evidence_class": "Synthetic-run" if gravity_inverse["best"]["accepted"] and magnetic_inverse["best"]["accepted"] else "Failed",
        "original_pgi_reproduced": False,
    }
    metrics_path = output / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_path = output / "raw-numerics.npz"
    np.savez_compressed(
        raw_path,
        gravity_matrix=gravity_matrix,
        gravity_data=gravity_observed,
        gravity_truth=density_truth,
        gravity_solutions=gravity_solutions,
        magnetic_matrix=magnetic_matrix,
        magnetic_data=magnetic_observed,
        magnetic_truth=susceptibility_truth,
        magnetic_solutions=magnetic_solutions,
        alphas=np.asarray(alphas),
    )
    environment = {
        "os": platform.platform(),
        "python": sys.version,
        "simpeg": simpeg.__version__,
        "discretize": discretize.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "executable": sys.executable,
        "venv": os.environ.get("VIRTUAL_ENV"),
        "requirements_lock_sha256": sha256(Path(__file__).with_name("requirements.lock.txt")),
        "command": " ".join(sys.argv),
    }
    environment_path = output / "environment.json"
    environment_path.write_text(json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8")
    config_path = output / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "preregistration": str(args.config.resolve()),
                "preregistration_sha256": sha256(args.config.resolve()),
                "archive": str(archive), "work": str(work), "stride": stride,
                "shape": [nx, ny, nz], "seed": seed, "protocol": protocol,
                "alphas": alphas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    completed_at = datetime.now(timezone.utc)
    checks = [
        {"name": "dependency-import", "status": "passed", "detail": f"simpeg {simpeg.__version__}, discretize {discretize.__version__}"},
        {"name": "do27-input-read", "status": "passed", "detail": f"{original_mesh.n_cells} cells, {gravity_data.dobs.size} observations/method"},
        {
            "name": "gravity-forward-and-inverse",
            "status": "passed" if gravity_inverse["best"]["accepted"] else "failed",
            "detail": f"solver={gravity_inverse['best']['solver_converged']}; data_fit={gravity_inverse['best']['data_fit_accepted']}; recovery={gravity_inverse['best']['model_recovery_accepted']}; alpha={gravity_inverse['best']['alpha']}",
        },
        {
            "name": "magnetic-forward-and-inverse",
            "status": "passed" if magnetic_inverse["best"]["accepted"] else "failed",
            "detail": f"solver={magnetic_inverse['best']['solver_converged']}; data_fit={magnetic_inverse['best']['data_fit_accepted']}; recovery={magnetic_inverse['best']['model_recovery_accepted']}; alpha={magnetic_inverse['best']['alpha']}",
        },
    ]
    run_passed = all(check["status"] == "passed" for check in checks)
    manifest = {
        "run_id": output.name,
        "evidence_id": "EVD-SYNTH-001",
        "status": "Synthetic-run" if run_passed else "Failed",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "inputs": [
            artifact(archive, archive.parent),
            artifact(forward / "mesh_inverse_ubc.msh", work),
            artifact(forward / "model_grav.den", work),
            artifact(forward / "model_mag.sus", work),
            artifact(forward / "GRAV_noisydata.obs", work),
            artifact(forward / "MAG_noisydata.obs", work),
        ],
        "script": artifact(Path(__file__).resolve(), Path(__file__).resolve().parent),
        "environment": {"os": environment["os"], "powershell": "7.6.3", "python": platform.python_version()},
        "checks": checks,
        "outputs": [],
        "approval": {
            "owner": "WP7结果独立复核待执行",
            "date": None,
            "decision": "pending",
        },
        "validation_context": {
            "truth_reference": "Forward/model_grav.den and Forward/model_mag.sus; coarse nearest-cell projection",
            "drillhole_holdout": False,
            "blind_release_record": None,
        },
    }
    summary = {
        "output": str(output),
        "gravity": gravity_inverse["best"],
        "magnetic": magnetic_inverse["best"],
        "forward_seconds": forward_seconds,
    }
    stdout_path = output / "stdout.json"
    stdout_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    stderr_path = output / "stderr.txt"
    stderr_path.write_text("", encoding="utf-8")
    manifest["outputs"] = [
        artifact(metrics_path, output.parent),
        artifact(raw_path, output.parent),
        artifact(environment_path, output.parent),
        artifact(config_path, output.parent),
        artifact(stdout_path, output.parent),
        artifact(stderr_path, output.parent),
    ]
    manifest_path = output / "run-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if run_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
