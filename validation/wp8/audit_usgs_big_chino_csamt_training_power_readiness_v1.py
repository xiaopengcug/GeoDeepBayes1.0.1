#!/usr/bin/env python
"""Authoritative central-directory-only Big Chino CSAMT power readiness audit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "usgs-big-chino-csamt-design-v1.json"
TRAINING = EVIDENCE / "usgs-big-chino-csamt-training-audit-v1.json"
RAW = ROOT / "validation/wp8/data/usgs-big-chino-raw.zip"
INVERSION = ROOT / "validation/wp8/data/usgs-big-chino-inversion.zip"
REGISTRY = EVIDENCE / "usgs-big-chino-csamt-paired-score-registry-v1.json"
OUTPUT = EVIDENCE / "usgs-big-chino-csamt-training-power-readiness-v1.json"
APPROVED_SHA256 = {
    "design": "e0b560c5213ec38aebe5e20559977303f58e0381201a79f463d6a8c968893599",
    "training_audit": "40588ecd032f5a47c3825c81c6bdf9aca75b76d91a181a2de7eb54d4f1e8f303",
    "raw": "828ab1bcc745fb10abcb32e66785117bfc877dfefd2407a4be2e8444b42b801a",
    "inversion": "325fc3d3d9884eb3fa48a7fc1a906f48665ef2d3b82337f13a0574421be37373",
}
APPROVED_LINES = {
    "AX", "CG", "CH", "EW1", "EW2", "EW3", "FM", "FME", "FMW", "GS16", "GS6",
    "GS8", "K1", "NS1", "NS2", "NS3", "NS4", "NS5", "WC", "WCN", "WR",
}
AUTHORIZED_TRAINING_LINES = {"CG", "CH", "EW2", "FMW", "NS1", "NS3"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def central_directory(path: Path) -> list[str]:
    """Read names from the ZIP central directory; never open member content."""
    with ZipFile(path) as archive:
        return archive.namelist()


def canonical_raw_line(name: str) -> str:
    stem = Path(name).stem
    return "FM" if stem == "FM1" else stem


def canonical_inversion_line(name: str) -> str:
    stem = Path(name).stem
    return "AX" if stem in {"AXnw", "AXse"} else stem


def load_registry(path: Path) -> tuple[dict[str, object] | None, list[str]]:
    if not path.exists():
        return None, []
    registry = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    artifact_path = registry.get("artifact_path")
    artifact = ROOT / artifact_path if isinstance(artifact_path, str) else None
    if (
        registry.get("schema_version") != "usgs-big-chino-csamt-paired-score-registry-v1"
        or registry.get("dataset_doi") != "10.5066/P9KGKWNL"
        or not isinstance(registry.get("method_versions"), list)
        or len(registry.get("method_versions", [])) != 2
        or set(registry.get("line_coverage", [])) != AUTHORIZED_TRAINING_LINES
        or not isinstance(registry.get("artifact_sha256"), str)
        or artifact is None
        or not artifact.resolve().is_relative_to(ROOT.resolve())
        or not artifact.is_file()
        or sha256(artifact) != registry.get("artifact_sha256")
    ):
        errors.append("paired_registry_contract")
    return registry, errors


def _build_audit(
    directory_reader: Callable[[Path], list[str]], *, production_access_claim: bool
) -> dict[str, object]:
    errors = []
    anchors = {
        "design": sha256(DESIGN), "training_audit": sha256(TRAINING),
        "raw": sha256(RAW), "inversion": sha256(INVERSION),
    }
    if anchors != APPROVED_SHA256:
        errors.append("approved_anchor_drift")
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    training = json.loads(TRAINING.read_text(encoding="utf-8"))
    train = design.get("split", {}).get("training_lines", [])
    sealed = design.get("split", {}).get("sealed_test_lines", [])
    train_set, sealed_set = set(train), set(sealed)
    if (
        len(train) != len(train_set)
        or len(sealed) != len(sealed_set)
        or train_set != AUTHORIZED_TRAINING_LINES
        or train_set & sealed_set
        or train_set | sealed_set != APPROVED_LINES
    ):
        errors.append("partition_contract")
    partition = training.get("partition", {})
    if (
        set(partition.get("training_lines", [])) != train_set
        or set(partition.get("sealed_test_lines", [])) != sealed_set
        or training.get("design_sha256") != APPROVED_SHA256["design"]
        or training.get("sources", {}).get("raw_sha256") != APPROVED_SHA256["raw"]
        or training.get("sources", {}).get("inversion_sha256") != APPROVED_SHA256["inversion"]
    ):
        errors.append("training_audit_consistency")
    raw_names = directory_reader(RAW)
    inversion_names = directory_reader(INVERSION)
    raw_lines = {canonical_raw_line(name) for name in raw_names if name.endswith(".raw")}
    inversion_lines = {
        canonical_inversion_line(name) for name in inversion_names if name.endswith(".mtm")
    }
    if raw_lines != APPROVED_LINES or inversion_lines != APPROVED_LINES:
        errors.append("archive_line_inventory")
    missing_training_members = sorted(
        (train_set - raw_lines) | (train_set - inversion_lines)
    )
    if missing_training_members:
        errors.append("training_member_missing")
    response_access_log: list[str] = []
    leakage = sorted(set(response_access_log) - train_set)
    registry, registry_errors = load_registry(REGISTRY)
    errors.extend(registry_errors)
    registry_count = 0 if registry is None else 1
    conditions = {
        "cluster_and_correlation_model_frozen": False,
        "required_independent_cluster_count_derived_by_frozen_power_method": False,
        "two_frozen_methods_named_and_versioned": registry is not None and not registry_errors,
        "same_information_and_compute_budget": False,
        "paired_out_of_sample_predictions_cover_all_training_lines": registry is not None
        and not registry_errors,
        "paired_crps_artifact_hash_registered": registry is not None and not registry_errors,
    }
    return {
        "schema_version": "usgs-big-chino-csamt-training-power-readiness-v1",
        "scope": "training-only",
        "status": "blocked",
        "approved_sha256": APPROVED_SHA256,
        "partition": {
            "approved_line_count": 21,
            "authorized_training_lines": sorted(train_set),
            "sealed_lines": sorted(sealed_set),
            "train_sealed_unique_disjoint_complete": not any(
                error == "partition_contract" for error in errors
            ),
            **({
                "response_content_members_opened_by_this_audit": response_access_log,
                "archive_member_leakage_by_this_audit": leakage,
            } if production_access_claim else {}),
            "missing_training_members": missing_training_members,
        },
        "inference_hierarchy": {
            "observation": "frequency/component/repeat row; not an independent cluster",
            "station": "receiver observation; independence unproven",
            "line": "archive packaging unit; independence unproven",
            "site": "Big Chino field site; only proven independent cluster upper bound",
            "training_observations_reported": 342,
            "training_lines": 6,
            "training_sites": 1,
        },
        "design_reconciliation": {
            "claimed_257_station_clusters": 257,
            "claim_status": "superseded_for_formal_gate",
            "formal_independent_cluster_proven_upper_bound": 1,
            "sealed_packaged_line_upper_bound_not_independence_evidence": 15,
            "formal_cluster_gate_passes": False,
        },
        "paired_power_inputs": {
            "registry_path": REGISTRY.relative_to(ROOT).as_posix(),
            "registry_present": registry is not None,
            "validated_registry_count": registry_count if not registry_errors else 0,
            "minimum_computable_conditions": conditions,
        },
        "formal_power_status": "blocked",
        "formal_power_gate_passes": False,
        "paired_crps_computed": False,
        "exact_unblockers": [
            "freeze a defensible line/site cluster and response-correlation model using training data only",
            "freeze the paired-power method; derive required independent N from its alpha, target power, effect and training dispersion",
            "register two versioned information/compute-matched methods and hashed out-of-sample paired scores covering every authorized training line",
            "freeze a buffered untouched test partition with at least the derived independent N",
        ],
        "field_validation_eligible": False,
        "errors": sorted(errors),
        "structure_audit_passed": not errors,
    }


def build_audit() -> dict[str, object]:
    """Production entry: fixed controlled central-directory reader."""
    return _build_audit(central_directory, production_access_claim=True)


def _build_audit_from_test_inventories(
    raw_names: list[str], inversion_names: list[str]
) -> dict[str, object]:
    inventories = {RAW: raw_names, INVERSION: inversion_names}
    return _build_audit(
        lambda path: inventories[path], production_access_claim=False
    )


def write_immutable(path: Path, value: dict[str, object]) -> None:
    body = (json.dumps(value, indent=2) + "\n").encode()
    if path.exists() and path.read_bytes() != body:
        raise RuntimeError("immutable Big Chino power readiness drift")
    if not path.exists():
        temporary = path.with_suffix(".json.tmp")
        temporary.write_bytes(body)
        os.replace(temporary, path)


def main() -> None:
    result = build_audit()
    if not result["structure_audit_passed"]:
        raise SystemExit(json.dumps(result))
    write_immutable(OUTPUT, result)
    print(json.dumps({"status": "blocked", "proven_cluster_upper_bound": 1}))


if __name__ == "__main__":
    main()
