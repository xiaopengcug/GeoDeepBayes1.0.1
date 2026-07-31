from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DATA = ROOT / "validation/wp8/data"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ga_magnetic_catalogue_design_is_response_blind() -> None:
    manifest_path = (
        DATA / "geoscience-australia-magnetic-catalog-v1/raw-manifest.json"
    )
    design_path = EVIDENCE / "geoscience-australia-magnetic-design.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = json.loads(design_path.read_text(encoding="utf-8"))
    assert manifest["feature_count"] == 1454
    assert manifest["catalogue_is_design_metadata_only"] is True
    assert manifest["magnetic_response_values_interpreted"] == 0
    assert design["catalogue_manifest_sha256"] == sha(manifest_path)
    assert design["formal_excluded_dataset_numbers"] == [17638]
    assert design["partition_counts"] == {
        "train": 1123,
        "buffer": 404,
        "calibration": 400,
        "test": 645,
    }
    assert design["test_responses_interpreted"] == 0
    assert design["test_unseal_count"] == 0


def test_ga_dds_audit_distinguishes_geometry_from_full_contract() -> None:
    manifest_path = DATA / "geoscience-australia-magnetic-dds-v1/raw-manifest.json"
    design_path = EVIDENCE / "geoscience-australia-magnetic-design.json"
    contract = json.loads(
        (EVIDENCE / "geoscience-australia-magnetic-dds-contract.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["design_sha256"] == sha(design_path)
    assert manifest["successful_products"] == 598
    assert manifest["failed_products"] == []
    assert manifest["dds_contains_declarations_only"] is True
    assert manifest["variable_attributes_requested"] is False
    assert contract["coverage"]["geometry_response"]["partition_cell_counts"]["test"] == 305
    assert contract["coverage"]["geometry_response"]["test_count_meets_223"] is True
    assert (
        contract["coverage"]["plus_explicit_corrections"]["partition_cell_counts"][
            "test"
        ]
        == 7
    )
    assert contract["coverage"]["plus_uncertainty"]["product_count"] == 0
    assert contract["formal_contract_ready"] is False
    assert contract["test_unseal_count"] == 0
