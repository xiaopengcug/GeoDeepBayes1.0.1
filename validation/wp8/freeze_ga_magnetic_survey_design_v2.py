#!/usr/bin/env python
"""Freeze a clean provider-survey-level GA magnetic design (v2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN_V1 = EVIDENCE / "geoscience-australia-magnetic-design.json"
DDS = EVIDENCE / "geoscience-australia-magnetic-dds-contract.json"
CATALOGUE = (
    DATA
    / "geoscience-australia-magnetic-catalog-v1/magnetic-catalog.geojson"
)
OUT = EVIDENCE / "geoscience-australia-magnetic-survey-design-v2.json"
EXPOSURE_MANIFESTS = (
    DATA / "geoscience-australia-magnetic-training-probe-v1/raw-manifest.json",
    DATA / "geoscience-australia-magnetic-training-survey-v1/raw-manifest.json",
    DATA / "geoscience-australia-magnetic-training-consortium-v1/raw-manifest.json",
    DATA / "geoscience-australia-magnetic-training-expansion-v1/raw-manifest.json",
    DATA / "geoscience-australia-magnetic-probability-sample-v1/raw-manifest.json",
)


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def role(survey_id: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-ga-mag-survey-v2|{survey_id}".encode()).hexdigest()[:8],
        16,
    ) % 100
    if bucket < 20:
        return "train"
    if bucket < 30:
        return "buffer"
    if bucket < 40:
        return "calibration"
    return "test"


def exposed_dataset_numbers() -> set[int]:
    result = set()
    for path in EXPOSURE_MANIFESTS:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if "dataset_no" in manifest:
            result.add(int(manifest["dataset_no"]))
        result.update(map(int, manifest.get("dataset_numbers", [])))
        result.update(
            int(member["dataset_no"])
            for member in manifest.get("members", [])
            if "dataset_no" in member
        )
    return result


def main() -> None:
    design = json.loads(DESIGN_V1.read_text(encoding="utf-8"))
    dds = json.loads(DDS.read_text(encoding="utf-8"))
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    catalogue_properties = {
        int(feature["properties"]["DATASET_NO"]): feature["properties"]
        for feature in catalogue["features"]
    }
    exposed = exposed_dataset_numbers()
    products = {int(item["DATASET_NO"]): item for item in design["products"]}
    eligible = []
    for dataset_no, declaration in dds["products"].items():
        number = int(dataset_no)
        flags = declaration["flags"]
        if number in exposed:
            continue
        if not all(
            flags.get(field)
            for field in (
                "latitude",
                "longitude",
                "line_identity",
                "magnetic_response",
            )
        ):
            continue
        product = products[number]
        if product["FLIGHT_HEIGHT_AGL"] is None:
            continue
        eligible.append(product)
    by_survey: dict[str, list[dict]] = {}
    for product in eligible:
        by_survey.setdefault(str(product["SURVEY_ID"]), []).append(product)
    selected = []
    for survey_id, candidates in sorted(by_survey.items()):
        product = min(
            candidates,
            key=lambda item: hashlib.sha256(
                (
                    f"wp8-ga-mag-survey-product-v2|{survey_id}|"
                    f"{item['DATASET_NO']}"
                ).encode()
            ).hexdigest(),
        )
        source = catalogue_properties[int(product["DATASET_NO"])]
        latitude = (source["MIN_LAT_WGS84"] + source["MAX_LAT_WGS84"]) / 2.0
        longitude = (source["MIN_LONG_WGS84"] + source["MAX_LONG_WGS84"]) / 2.0
        selected.append(
            {
                "survey_id": survey_id,
                "dataset_no": int(product["DATASET_NO"]),
                "survey_name": product["SURVEY_NAME"],
                "state": product["STATE"],
                "survey_start_date": product["SURVEY_START_DATE"],
                "flight_height_agl_m": product["FLIGHT_HEIGHT_AGL"],
                "line_spacing_min_m": product["MIN_LINE_SPACING_M"],
                "line_spacing_max_m": product["MAX_LINE_SPACING_M"],
                "line_azimuth_deg": product["LINE_AZIMUTH"],
                "license": product["LICENCE"],
                "file_download": product["FILE_DOWNLOAD"],
                "catalogue_file_size": product["FILE_SIZE"],
                "bbox": [
                    source["MIN_LONG_WGS84"],
                    source["MIN_LAT_WGS84"],
                    source["MAX_LONG_WGS84"],
                    source["MAX_LAT_WGS84"],
                ],
                "centroid_latitude": latitude,
                "centroid_longitude": longitude,
                "role": role(survey_id),
            }
        )
    roles = ("train", "buffer", "calibration", "test")
    counts = {
        assigned: sum(item["role"] == assigned for item in selected)
        for assigned in roles
    }
    result = {
        "schema_version": "wp8-ga-magnetic-survey-design-v2",
        "parent_design_sha256": sha(DESIGN_V1),
        "dds_contract_sha256": sha(DDS),
        "exposure_manifest_sha256": {
            path.parent.name: sha(path) for path in EXPOSURE_MANIFESTS
        },
        "formal_excluded_dataset_numbers": sorted(exposed),
        "exclusion_reason": (
            "Every product whose magnetic training response or response-range metadata "
            "was previously interpreted is excluded from the v2 pool."
        ),
        "selection_is_metadata_and_dds_only": True,
        "response_values_interpreted": 0,
        "selection_contract": {
            "required_dds_flags": [
                "latitude",
                "longitude",
                "line_identity",
                "magnetic_response",
            ],
            "required_catalogue_fields": [
                "FLIGHT_HEIGHT_AGL",
                "LICENCE",
                "LINE_AZIMUTH",
                "MIN_LINE_SPACING_M",
                "MAX_LINE_SPACING_M",
                "FILE_DOWNLOAD",
            ],
            "provider_unit": "unique SURVEY_ID",
            "product_choice": (
                "minimum SHA-256 wp8-ga-mag-survey-product-v2|survey_id|dataset_no"
            ),
        },
        "role_assignment": (
            "SHA-256 wp8-ga-mag-survey-v2|survey_id; "
            "20% train, 10% buffer, 10% calibration, 60% test"
        ),
        "eligible_unexposed_product_count": len(eligible),
        "unique_provider_survey_count": len(selected),
        "partition_survey_counts": counts,
        "nominal_test_survey_upper_bound": counts["test"],
        "nominal_power_gate_possible": counts["test"] >= 223,
        "post_training_separation_rule": (
            "Choose the observed station nearest each survey footprint centroid; "
            "after estimating training-only correlation range, exclude test "
            "representatives nearer than that range to train/calibration or another "
            "accepted test representative, using frozen hash packing order."
        ),
        "records": selected,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "eligible_products": len(eligible),
            "surveys": len(selected),
            "partitions": counts,
            "nominal_power": result["nominal_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
