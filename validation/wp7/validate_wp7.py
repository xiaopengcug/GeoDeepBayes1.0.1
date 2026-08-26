from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
import re
import shutil
import tempfile
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker
from scipy.sparse import eye, vstack
from scipy.sparse.linalg import lsqr

from geodeepbayes.diagnostics import (
    bulk_ess, monte_carlo_standard_error, rank_normalized_split_rhat, tail_ess,
)
from geodeepbayes.benchmarks.synthetic_block_v2 import (
    _coverage, _predictive_interval, _wilson,
)
from geodeepbayes.sampling import PODReducer


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# 2026-08-02 文档治理：治理复合体自 research/贝叶斯思想与重磁电电磁深度融合技术体系/
# 迁移至 research/贝叶斯思想与重磁电电磁深度融合技术体系-治理与验证档案/。签名证据
# （evidence-run-v2.json 等）中记录的仓库级路径保持原样不改写；本映射仅用于把
# 记录路径解析到当前物理位置，不参与任何哈希计算。
_FROZEN_PATH_MIGRATIONS = (
    (
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/",
        "_bmad-output/planning-artifacts/research/"
        "贝叶斯思想与重磁电电磁深度融合技术体系-治理与验证档案/",
    ),
    # 2026-08-02 继续归档：论文验证代码 src/ 自仓库根迁入治理档案。
    (
        "src/",
        "_bmad-output/planning-artifacts/research/"
        "贝叶斯思想与重磁电电磁深度融合技术体系-治理与验证档案/src/",
    ),
)


def _resolve_recorded_path(path: str) -> str:
    for old, new in _FROZEN_PATH_MIGRATIONS:
        if path.startswith(old):
            return new + path[len(old):]
    return path


LSQR_SOLVER_TOLERANCE = 1e-6
TRIAL_METRIC_RTOL = 1e-8
TRIAL_METRIC_ATOL = 1e-10


def validate_synthetic(run: Path) -> list[str]:
    errors = []
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "evidence-run-v2.json").read_text(encoding="utf-8"))
    config_paths = {Path(item["path"]).name for item in manifest["configs"]}
    if "synthetic-v6-config.json" in config_paths:
        config_name = "synthetic-v6-config.json"
    elif "synthetic-v5-config.json" in config_paths:
        config_name = "synthetic-v5-config.json"
    elif "synthetic-v4-config.json" in config_paths:
        config_name = "synthetic-v4-config.json"
    elif "synthetic-v3-config.json" in config_paths:
        config_name = "synthetic-v3-config.json"
    elif "synthetic-config.json" in config_paths:
        config_name = "synthetic-config.json"
    else:
        return ["synthetic signed config is not recognized"]
    config = json.loads((HERE / config_name).read_text(encoding="utf-8"))
    with np.load(run / "raw-chains.npz") as raw:
        draws = raw["draws"]
        warmup = raw["warmup"]
        sources = raw["snapshot_sources"].astype(str)
        if draws.shape != (config["chains"], config["draws_per_chain"], config["dimension"]):
            errors.append("draw shape mismatch")
        if warmup.shape != (config["chains"], config["warmup_per_chain"], config["dimension"]):
            errors.append("warmup shape mismatch")
        expected_sources = {key: value for key, value in config["snapshots"].items()}
        actual_sources = {key: int(np.count_nonzero(sources == key)) for key in expected_sources}
        if actual_sources != expected_sources:
            errors.append("snapshot source counts mismatch")
        regenerated_pod = PODReducer(
            raw["snapshots"][:, :72], energy=0.99, max_rank=config["pod_rank_cap"]
        )
        stored_projector = raw["pod_basis"] @ raw["pod_basis"].T
        regenerated_projector = regenerated_pod.basis @ regenerated_pod.basis.T
        if not np.allclose(stored_projector, regenerated_projector, atol=1e-12):
            errors.append("stored POD basis differs from frozen snapshots")
        if not np.allclose(raw["pod_mean"], regenerated_pod.mean_model, atol=1e-12):
            errors.append("stored POD mean differs from frozen snapshots")
        recomputed = {
            "max_rhat": float(np.max(rank_normalized_split_rhat(draws))),
            "min_bulk_ess": float(np.min(bulk_ess(draws))),
            "min_tail_ess": float(np.min(tail_ess(draws))),
        }
        mcse = np.asarray(monte_carlo_standard_error(draws))
        sd = draws.reshape(-1, draws.shape[-1]).std(axis=0, ddof=1)
        recomputed["max_relative_mcse"] = float(np.max(mcse / np.maximum(sd, 1e-12)))
        recomputed["mode_visits_per_chain"] = [
            int(np.count_nonzero(np.signbit(chain[1:, 0]) != np.signbit(chain[:-1, 0])))
            for chain in draws
        ]
        recomputed["standardized_mean_rmse"] = float(
            np.sqrt(np.mean(draws.mean(axis=(0, 1)) ** 2))
        )
        if "coverage_replicates" in config:
            if raw["coverage_truth"].shape != (
                config["coverage_replicates"], config["dimension"]
            ):
                errors.append("coverage replicate count mismatch")
            _, regenerated_coverage = _coverage(
                config["seed"] + 5000,
                regenerated_pod,
                config["dimension"],
                config["coverage_replicates"],
            )
            for key, stored_key in (
                ("truth", "coverage_truth"),
                ("observed", "coverage_observed"),
                ("future", "coverage_future"),
            ):
                if not np.array_equal(raw[stored_key], regenerated_coverage[key]):
                    errors.append(f"{stored_key} differs from preregistered seed")
            observed = raw["coverage_observed"]
            future = raw["coverage_future"]
            basis, mean = raw["pod_basis"], raw["pod_mean"]
            projector = basis @ basis.T
            mode_means = np.zeros((2, config["dimension"]))
            mode_means[:, 0] = (-3.0, 3.0)
            projected_means = (
                mean[:, None] + projector @ (mode_means.T - mean[:, None])
            ).T[:, 0]
            projected_variance = max(float(projector[0, 0]), 1e-12)
            methods = {
                "full": (mode_means[:, 0], 1.0),
                "naive_pod": (projected_means, projected_variance),
                "error_inflated_pod": (projected_means, 1.0),
            }
            for name, (prior_means, latent_variance) in methods.items():
                for level in (0.9, 0.95):
                    covered = sum(
                        _predictive_interval(
                            float(obs), level, prior_means=prior_means,
                            latent_variance=latent_variance,
                        )[0]
                        <= float(pred)
                        <= _predictive_interval(
                            float(obs), level, prior_means=prior_means,
                            latent_variance=latent_variance,
                        )[1]
                        for obs, pred in zip(observed, future, strict=True)
                    )
                    node = metrics["predictive_coverage"][name][str(level)]
                    expected = {
                        "covered": covered,
                        "total": int(future.size),
                        "rate": covered / future.size,
                        "wilson95": _wilson(covered, int(future.size)),
                    }
                    for key, value in expected.items():
                        if not np.allclose(node[key], value, rtol=1e-12, atol=1e-12):
                            errors.append(f"{name} coverage {level} {key} mismatch")
    for key, value in recomputed.items():
        if not np.allclose(metrics[key], value, rtol=1e-10, atol=1e-12):
            errors.append(f"{key} aggregate mismatch")
    if metrics["failed_replicate_rate"] != 0.0:
        errors.append("analytic coverage run cannot report failed replicates")
    if manifest["execution"]["outcome"] != "succeeded" or not manifest["claims"]:
        errors.append("synthetic evidence is not a successful claimed run")
    producer_path = run / "run-manifest.json"
    if producer_path.is_file():
        producer = json.loads(producer_path.read_text(encoding="utf-8"))
        code_by_name = {
            Path(item["path"]).name: item["sha256"]
            for item in manifest["code"]["manifest"]
        }
        if producer.get("script", {}).get("sha256") != code_by_name.get(
            "synthetic_block_v2.py"
        ):
            errors.append("synthetic producer/evidence code hash mismatch")
        if producer.get("run_id") != config["run_id"] or manifest["run_id"] != config["run_id"]:
            errors.append("synthetic run_id mismatch")
        if producer.get("status") != "Synthetic-run" or producer.get("exit_code") != 0:
            errors.append("synthetic producer outcome mismatch")
        if (
            producer.get("started_at") != manifest["execution"]["started_at"]
            or producer.get("completed_at") != manifest["execution"]["ended_at"]
            or datetime.fromisoformat(producer["completed_at"])
            <= datetime.fromisoformat(producer["started_at"])
        ):
            errors.append("synthetic producer timing mismatch")
        command = producer.get("command", [])
        expected_cli = {
            "--seed": str(config["seed"]),
            "--warmup": str(config["warmup_per_chain"]),
            "--draws": str(config["draws_per_chain"]),
        }
        for option, expected in expected_cli.items():
            if option not in command or command[command.index(option) + 1] != expected:
                errors.append(f"synthetic producer command mismatch: {option}")
        with np.load(run / "raw-chains.npz") as raw:
            if not np.array_equal(
                raw["seeds"], config["seed"] + 100 + np.arange(config["chains"])
            ):
                errors.append("synthetic chain seeds mismatch")
    else:
        errors.append("synthetic producer manifest missing")
    thresholds = config["thresholds"]
    gates = [
        metrics["max_rhat"] <= thresholds["max_rhat"],
        metrics["min_bulk_ess"] >= thresholds["min_bulk_ess"],
        metrics["min_tail_ess"] >= thresholds["min_tail_ess"],
        metrics["max_relative_mcse"] <= thresholds["max_relative_mcse"],
        min(metrics["mode_visits_per_chain"]) >= thresholds["min_mode_visits_per_chain"],
        metrics["failed_replicate_rate"] <= thresholds["max_failed_replicate_rate"],
        metrics["standardized_mean_rmse"] <= thresholds["max_standardized_mean_rmse"],
    ]
    if not all(gates):
        errors.append("synthetic preregistered gate failed")
    if "coverage_replicates" in config:
        for level in ("0.9", "0.95"):
            node = metrics["predictive_coverage"]["full"][level]
            if node["total"] != config["coverage_replicates"]:
                errors.append(f"coverage {level} total mismatch")
            nominal = float(level)
            if not node["wilson95"][0] <= nominal <= node["wilson95"][1]:
                errors.append(f"coverage {level} Wilson gate failed")
    return errors


def validate_manifest(run: Path) -> list[str]:
    schema = json.loads((ROOT / "contracts/evidence-run.schema.json").read_text(encoding="utf-8"))
    value = json.loads((run / "evidence-run-v2.json").read_text(encoding="utf-8"))
    errors = [
        f"manifest:{'/'.join(map(str, error.path))}:{error.message}"
        for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)
    ]
    project = ROOT
    while project.parent != project and not (project / "pyproject.toml").exists():
        project = project.parent
    for group in ("inputs", "configs", "outputs"):
        for item in value[group]:
            path = project / _resolve_recorded_path(item["path"])
            if group == "outputs" and path.resolve().parent != run.resolve():
                errors.append(f"outputs:{item['path']}:not bound to supplied run")
                continue
            if not path.is_file():
                errors.append(f"{group}:{item['path']}:missing")
                continue
            if path.stat().st_size != item["bytes"]:
                errors.append(f"{group}:{item['path']}:size mismatch")
            if sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                errors.append(f"{group}:{item['path']}:hash mismatch")
    code_manifest = value["code"]["manifest"]
    for item in code_manifest:
        path = project / _resolve_recorded_path(item["path"])
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(f"code:{item['path']}:hash mismatch")
    canonical = json.dumps(
        code_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if sha256(canonical).hexdigest() != value["code"]["sha256"]:
        errors.append("code root mismatch")
    if value["execution"]["outcome"] != "succeeded" and value["claims"]:
        errors.append("failed/blocked run has claims")
    return errors


def validate_do27(run: Path) -> list[str]:
    errors = validate_manifest(run)
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "evidence-run-v2.json").read_text(encoding="utf-8"))
    signed_configs = [
        item for item in manifest["configs"] if Path(item["path"]).name.startswith("do27-")
    ]
    if len(signed_configs) != 1:
        return errors + ["DO27 must bind exactly one preregistration config"]
    config_path = ROOT.parents[3] / _resolve_recorded_path(signed_configs[0]["path"])
    prereg = json.loads(config_path.read_text(encoding="utf-8"))
    executed = json.loads((run / "config.json").read_text(encoding="utf-8"))
    expected_execution = {
        "preregistration_sha256": signed_configs[0]["sha256"],
        "stride": prereg["stride"],
        "shape": prereg["shape"],
        "seed": prereg.get("seed", 20260724),
        "protocol": prereg["schema"].rsplit("-", 1)[-1],
        "alphas": prereg["alphas"],
    }
    for key, value in expected_execution.items():
        if executed.get(key) != value:
            errors.append(f"DO27 executed config mismatch: {key}")
    if metrics["input"]["archive_sha256"] != prereg["archive_sha256"]:
        errors.append("DO27 archive hash differs from preregistration")
    producer = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
    code_by_name = {
        Path(item["path"]).name: item["sha256"] for item in manifest["code"]["manifest"]
    }
    if producer["script"]["sha256"] != code_by_name.get("run_do27_validation.py"):
        errors.append("DO27 producer/evidence code hash mismatch")
    protocol = metrics["gravity_inverse"].get("protocol", "v2")
    with np.load(run / "raw-numerics.npz") as raw:
      for method, prefix in (
          ("gravity_inverse", "gravity"), ("magnetic_inverse", "magnetic")
      ):
        result = metrics[method]
        matrix = raw[f"{prefix}_matrix"]
        data = raw[f"{prefix}_data"]
        truth = raw[f"{prefix}_truth"]
        solutions = raw[f"{prefix}_solutions"]
        expected_sigma = float(
            prereg["assumed_inversion_weight"][
                "gravity_mgal" if prefix == "gravity" else "magnetic_nt"
            ]
        )
        if not np.isclose(result["sigma"], expected_sigma):
            errors.append(f"{method}: sigma differs from preregistration")
        sigma = expected_sigma
        normalized_matrix, normalized_data = matrix / sigma, data / sigma
        singular = np.linalg.svd(normalized_matrix, compute_uv=False)
        expected_zero_rmse = float(np.sqrt(np.mean(truth**2)))
        if not np.isclose(result["zero_model_rmse"], expected_zero_rmse):
            errors.append(f"{method}: zero model RMSE mismatch")
        identity = eye(matrix.shape[1], format="csr")
        if not np.allclose(raw["alphas"], prereg["alphas"]):
            errors.append(f"{method}: raw alpha path mismatch")
        if len(result["trials"]) != len(prereg["alphas"]):
            errors.append(f"{method}: incomplete preregistered trial path")
            continue
        if solutions.shape[0] != len(prereg["alphas"]):
            errors.append(f"{method}: incomplete raw solution path")
            continue
        replay_trials = []
        for index, trial in enumerate(result["trials"]):
            alpha = float(trial["alpha"])
            if not np.isclose(alpha, prereg["alphas"][index]):
                errors.append(f"{method}: trial {index} alpha mismatch")
            rerun = lsqr(
                vstack([normalized_matrix, np.sqrt(alpha) * identity], format="csr"),
                np.r_[normalized_data, np.zeros(matrix.shape[1])],
                atol=LSQR_SOLVER_TOLERANCE,
                btol=LSQR_SOLVER_TOLERANCE,
                iter_lim=2000,
            )
            replay_model = rerun[0]
            stored_model = solutions[index]
            replay_residual = normalized_matrix @ replay_model - normalized_data
            stored_residual = normalized_matrix @ stored_model - normalized_data
            df = float(np.sum(singular**2 / (singular**2 + alpha)))
            denominator = max(1.0 - df / data.size, np.finfo(float).eps)
            stored_rss = float(stored_residual @ stored_residual)
            replay_rss = float(replay_residual @ replay_residual)
            stored_values = {
                "normalized_rms": float(np.sqrt(np.mean(stored_residual**2))),
                "model_rmse": float(np.sqrt(np.mean((stored_model - truth) ** 2))),
                "effective_df": df,
                "gcv": float((stored_rss / data.size) / denominator**2),
                "solution_norm": float(np.linalg.norm(stored_model)),
                "residual_norm": float(np.linalg.norm(stored_residual)),
                "values_finite": bool(
                    np.isfinite(stored_model).all()
                    and np.isfinite(stored_residual).all()
                ),
            }
            stored_values["solver_converged"] = bool(
                int(trial["stop_code"]) in (1, 2)
                and int(trial["iterations"]) < 2000
                and stored_values["values_finite"]
            )
            replay_values = {
                "normalized_rms": float(np.sqrt(np.mean(replay_residual**2))),
                "model_rmse": float(np.sqrt(np.mean((replay_model - truth) ** 2))),
                "gcv": float((replay_rss / data.size) / denominator**2),
                "solution_norm": float(np.linalg.norm(replay_model)),
                "residual_norm": float(np.linalg.norm(replay_residual)),
            }
            replay_converged = bool(
                int(rerun[1]) in (1, 2)
                and int(rerun[2]) < 2000
                and np.isfinite(replay_model).all()
                and np.isfinite(replay_residual).all()
                and np.isfinite(np.asarray(rerun[3:9], dtype=float)).all()
            )
            if not replay_converged:
                errors.append(f"{method}: trial {index} replay did not converge")
            replay_trials.append(
                {
                    "alpha": alpha,
                    **replay_values,
                    "solver_converged": replay_converged,
                }
            )
            for key, value in stored_values.items():
                if isinstance(value, bool):
                    matches = trial[key] is value
                else:
                    matches = np.isclose(
                        trial[key],
                        value,
                        rtol=TRIAL_METRIC_RTOL,
                        atol=TRIAL_METRIC_ATOL,
                    )
                if not matches:
                    errors.append(f"{method}: trial {index} {key} mismatch")
        # Iteration counts, stop codes, individual coefficients and floating
        # tails are audit fields, not portable scientific invariants. The
        # frozen manifest protects their exact bytes. Independent replay must
        # instead preserve the preregistered GCV choice and acceptance decision.
        replay_minimum = min(item["gcv"] for item in replay_trials)
        replay_eligible = [
            item
            for item in replay_trials
            if item["gcv"] <= 1.01 * replay_minimum
        ]
        replay_best = max(replay_eligible, key=lambda item: item["alpha"])
        if result["best"]["alpha"] != replay_best["alpha"]:
            errors.append(f"{method}: replay GCV selection mismatch")
        replay_flags = {
            "data_fit_accepted": (
                replay_best["normalized_rms"] <= 1.2 if protocol == "v3"
                else 0.5 <= replay_best["normalized_rms"] <= 1.2
            ),
            "model_recovery_accepted": (
                replay_best["model_rmse"] <= 0.95 * expected_zero_rmse
            ),
            "overfit_warning": replay_best["normalized_rms"] < 0.5,
        }
        replay_flags["compatibility_accepted"] = bool(
            replay_best["solver_converged"]
            and replay_flags["data_fit_accepted"]
        )
        replay_flags["accepted"] = bool(
            replay_flags["compatibility_accepted"]
            if protocol == "v3"
            else replay_flags["compatibility_accepted"]
            and replay_flags["model_recovery_accepted"]
        )
        for key, value in replay_flags.items():
            if result["best"][key] is not value:
                errors.append(f"{method}: replay {key} mismatch")
        minimum = min(item["gcv"] for item in result["trials"])
        eligible = [item for item in result["trials"] if item["gcv"] <= 1.01 * minimum]
        expected = max(eligible, key=lambda item: item["alpha"])
        if result["best"]["alpha"] != expected["alpha"]:
            errors.append(f"{method}: GCV selection mismatch")
        for key, value in expected.items():
            if key == "elapsed_seconds":
                continue
            if isinstance(value, bool):
                matches = result["best"].get(key) is value
            elif isinstance(value, (int, float)):
                matches = np.isclose(
                    result["best"].get(key), value, rtol=1e-8, atol=1e-10
                )
            else:
                matches = result["best"].get(key) == value
            if not matches:
                errors.append(f"{method}: best {key} differs from selected trial")
        expected_flags = {
            "data_fit_accepted": (
                result["best"]["normalized_rms"] <= 1.2 if protocol == "v3"
                else 0.5 <= result["best"]["normalized_rms"] <= 1.2
            ),
            "model_recovery_accepted": (
                result["best"]["model_rmse"] <= 0.95 * expected_zero_rmse
            ),
            "overfit_warning": result["best"]["normalized_rms"] < 0.5,
        }
        expected_flags["compatibility_accepted"] = bool(
            result["best"]["solver_converged"]
            and expected_flags["data_fit_accepted"]
        )
        expected_flags["accepted"] = bool(
            expected_flags["compatibility_accepted"]
            if protocol == "v3"
            else expected_flags["compatibility_accepted"]
            and expected_flags["model_recovery_accepted"]
        )
        for key, value in expected_flags.items():
            if result["best"][key] is not value:
                errors.append(f"{method}: {key} mismatch")
    compatibility = all(
        metrics[name]["best"]["solver_converged"]
        and metrics[name]["best"]["data_fit_accepted"]
        for name in ("gravity_inverse", "magnetic_inverse")
    )
    accepted = all(
        metrics[name]["best"]["accepted"]
        for name in ("gravity_inverse", "magnetic_inverse")
    )
    expected_accepted = compatibility if protocol == "v3" else (
        compatibility and all(
            metrics[name]["best"]["model_recovery_accepted"]
            for name in ("gravity_inverse", "magnetic_inverse")
        )
    )
    if accepted != expected_accepted:
        errors.append("DO27 overall acceptance mismatch")
    if accepted:
        if manifest["execution"]["outcome"] != "succeeded" or not manifest["claims"]:
            errors.append("successful DO27 run lacks positive bounded claim")
    elif manifest["execution"]["outcome"] != "failed" or manifest["claims"]:
        errors.append("failed DO27 run carried a positive claim")
    return errors


def validate_signoff(path: Path, synthetic_run: Path, do27_run: Path) -> list[str]:
    errors = []
    value = json.loads(path.read_text(encoding="utf-8"))
    roles = value.get("roles", [])
    if value.get("status") != "Done":
        errors.append("signoff is not Done")
    if {item.get("role") for item in roles} != {"numerical", "qa", "science"}:
        errors.append("signoff roles mismatch")
    if any(item.get("decision") != "Approved" or item.get("identity_type") != "ai" for item in roles):
        errors.append("a signoff role is not approved")
    review_hashes = set()
    for item in roles:
        text = item.get("review_text", "")
        actual = sha256(text.encode("utf-8")).hexdigest()
        if item.get("review_sha256") != actual:
            errors.append(f"{item.get('role')}: review hash mismatch")
        if not re.search(
            r"(?mi)^#{1,6}\s+\**Verdict:\s*\**Approved\**\s*$", text
        ):
            errors.append(f"{item.get('role')}: review text is not an approval")
        review_hashes.add(actual)
    if len(review_hashes) != 3:
        errors.append("signoff reviews are not independent")
    for label, run in (("synthetic", synthetic_run), ("do27", do27_run)):
        manifest = run / "evidence-run-v2.json"
        expected = value["manifests"][label]["sha256"]
        if sha256(manifest.read_bytes()).hexdigest() != expected:
            errors.append(f"{label} signoff root mismatch")
        approval = json.loads(manifest.read_text(encoding="utf-8"))["approval"]
        if approval["decision"] != "approved" or approval["identity_type"] != "ai":
            errors.append(f"{label} evidence approval mismatch")
        producer_path = run / "run-manifest.json"
        if producer_path.is_file():
            producer_approval = json.loads(
                producer_path.read_text(encoding="utf-8")
            )["approval"]
            if producer_approval["decision"] != "approved":
                errors.append(f"{label} producer approval mismatch")
    return errors


def self_test(run: Path, do27_run: Path, signoff: Path) -> None:
    if validate_synthetic(run):
        raise RuntimeError("positive fixture failed")
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory) / "run"
        shutil.copytree(run, fixture)
        metrics_path = fixture / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["max_rhat"] = 1.0
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        if not validate_synthetic(fixture):
            raise RuntimeError("aggregate tampering was accepted")
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory) / "run"
        shutil.copytree(run, fixture)
        raw_path = fixture / "raw-chains.npz"
        with np.load(raw_path) as raw:
            arrays = {key: raw[key] for key in raw.files}
        arrays["coverage_future"] = arrays["coverage_future"] + 1000.0
        np.savez_compressed(raw_path, **arrays)
        if not validate_synthetic(fixture):
            raise RuntimeError("coverage raw tampering was accepted")
    if validate_do27(do27_run):
        raise RuntimeError(f"DO27 fixture invalid: {validate_do27(do27_run)}")
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory) / "run"
        shutil.copytree(do27_run, fixture)
        metrics_path = fixture / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["gravity_inverse"]["best"]["normalized_rms"] = 1.1
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        if not validate_do27(fixture):
            raise RuntimeError("DO27 selected-result tampering was accepted")
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory) / "signoff.json"
        shutil.copy2(signoff, fixture)
        value = json.loads(fixture.read_text(encoding="utf-8"))
        value["roles"][0]["review_text"] = "## Verdict: Rejected"
        fixture.write_text(json.dumps(value), encoding="utf-8")
        if not validate_signoff(fixture, run, do27_run):
            raise RuntimeError("signoff review tampering was accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-run", type=Path, required=True)
    parser.add_argument("--do27-run", type=Path, required=True)
    parser.add_argument("--signoff", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    errors = (
        validate_manifest(args.synthetic_run)
        + validate_synthetic(args.synthetic_run)
        + validate_do27(args.do27_run)
        + validate_signoff(args.signoff, args.synthetic_run, args.do27_run)
    )
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False))
        return 1
    if args.self_test:
        self_test(args.synthetic_run, args.do27_run, args.signoff)
    print(json.dumps({"status": "PASS", "self_test": args.self_test}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
