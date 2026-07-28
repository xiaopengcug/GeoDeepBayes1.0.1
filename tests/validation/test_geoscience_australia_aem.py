from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "validation/wp8/data/geoscience-australia-aem-catalog-v1"
PROBE = ROOT / "validation/wp8/data/geoscience-australia-aem-training-probe-v1"
MULTISYSTEM = ROOT / "validation/wp8/data/geoscience-australia-aem-multisystem-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_ga_aem_catalogue_and_design_are_response_blind() -> None:
    manifest_path = CATALOG / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = json.loads(
        (EVIDENCE / "geoscience-australia-aem-design.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["feature_count"] == 72
    assert manifest["aem_response_values_interpreted"] == 0
    for member in manifest["members"]:
        path = CATALOG / member["path"]
        assert path.stat().st_size == member["bytes"]
        assert sha(path) == member["sha256"]
    assert design["catalogue_manifest_sha256"] == sha(manifest_path)
    assert design["eligible_open_license_product_count"] == 71
    assert design["unique_survey_count"] == 40
    assert design["partition_counts"] == {
        "train": 726,
        "buffer": 259,
        "calibration": 243,
        "test": 394,
    }
    assert design["design_power_gate_possible"] is True
    assert design["aem_response_values_interpreted"] == 0
    assert design["test_unseal_count"] == 0


def test_ga_aem_training_probe_is_integral_and_train_only() -> None:
    manifest_path = PROBE / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = json.loads(
        (
            EVIDENCE / "geoscience-australia-aem-training-probe-inventory.json"
        ).read_text(encoding="utf-8")
    )
    contract = json.loads(
        (
            EVIDENCE / "geoscience-australia-aem-training-probe-contract.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["covered_design_roles"] == ["train"]
    assert manifest["test_unseal_count"] == 0
    for member in manifest["members"]:
        path = PROBE / member["path"]
        assert path.stat().st_size == member["bytes"]
        assert sha(path) == member["sha256"]
    assert inventory["raw_manifest_sha256"] == sha(manifest_path)
    assert inventory["member_count"] == 48
    assert inventory["member_payloads_read"] == 0
    assert contract["raw_manifest_sha256"] == sha(manifest_path)
    assert contract["located_data"]["row_count"] == 442_601
    assert contract["located_data"]["unique_line_count"] == 269
    assert contract["located_data"]["unique_flight_count"] == 14
    assert contract["maximum_training_range_km"] == 1.536
    assert contract["exact_gate_center_times_present"] is True
    assert contract["exact_gate_center_times_ms"] == [
        0.013, 0.04, 0.067, 0.107, 0.173, 0.28, 0.453, 0.72,
        1.12, 1.733, 2.693, 4.2, 6.56, 10.2, 16.2,
    ]
    assert contract["national_55_km_centers_exceed_probe_range"] is True
    assert contract["formal_contract_ready"] is False
    assert contract["calibration_responses_interpreted"] == 0
    assert contract["test_responses_interpreted"] == 0
    assert contract["test_unseal_count"] == 0


def test_ga_aem_multisystem_schema_audit_is_response_blind() -> None:
    manifest_path = MULTISYSTEM / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory_path = EVIDENCE / "geoscience-australia-aem-multisystem-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    contract = json.loads(
        (EVIDENCE / "geoscience-australia-aem-multisystem-contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["total_bytes"] == 921_757_368
    assert manifest["selection_was_response_blind"] is True
    for member in manifest["members"]:
        path = MULTISYSTEM / member["path"]
        assert path.stat().st_size == member["bytes"]
        assert sha(path) == member["sha256"]
    assert inventory["observation_payload_members_opened"] == 0
    assert inventory["response_values_interpreted"] == 0
    assert inventory["test_unseal_count"] == 0
    assert contract["inventory_sha256"] == sha(inventory_path)
    assert contract["skytem_contract_ready"] is True
    assert contract["vtem_contract_ready"] is False
    assert contract["response_values_interpreted"] == 0
    assert contract["test_unseal_count"] == 0


def test_ga_aem_multisystem_training_parse_is_spatially_sealed() -> None:
    split_path = EVIDENCE / "geoscience-australia-aem-multisystem-spatial-split.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    diagnostics = json.loads(
        (
            EVIDENCE
            / "geoscience-australia-aem-multisystem-train-diagnostics.json"
        ).read_text(encoding="utf-8")
    )
    assert split["partition_counts"] == {
        "train": 523,
        "buffer": 511,
        "calibration": 170,
        "test": 418,
    }
    assert split["minimum_nonbuffer_cross_role_center_distance_km"] == 87.61
    assert split["design_power_gate_possible"] is True
    assert diagnostics["split_sha256"] == sha(split_path)
    assert diagnostics["coordinate_first_role_assignment"] is True
    assert diagnostics["sealed_response_rows_interpreted"] == {
        "buffer": 0,
        "calibration": 0,
        "test": 0,
    }
    products = {item["dataset_number"]: item for item in diagnostics["products"]}
    assert products[22131]["role_row_counts"]["test"] == 199_210
    assert products[22131]["training_response_rows_interpreted"] == 0
    assert products[22122]["training_response_rows_interpreted"] == 259_008
    assert products[22122]["training_uncertainty_rows_interpreted"] == 0
    assert products[22130]["training_response_rows_interpreted"] == 248_928
    assert products[22130]["training_uncertainty_rows_interpreted"] == 248_928
    assert products[22130]["sample_median_relative_uncertainty"] == 0.00868
    assert diagnostics["test_unseal_count"] == 0
    assert diagnostics["formal_national_correlation_gate_passes"] is False
