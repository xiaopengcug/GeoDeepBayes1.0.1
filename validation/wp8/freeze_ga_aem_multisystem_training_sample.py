#!/usr/bin/env python
"""Freeze response-blind VTEM and SkyTEM training-product choices."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "geoscience-australia-aem-design.json"
OUTPUT = EVIDENCE / "geoscience-australia-aem-multisystem-training-sample.json"

CHOICES = [
    {
        "system": "VTEM",
        "dataset_number": 22122,
        "survey_id": "1279",
        "record_id": 102781,
        "package_id": "490c9485-9943-4b06-9103-9302f0e13341",
        "resource_name": "Point-located electromagnetic subsampled data",
        "url": (
            "https://d28rz98at9flks.cloudfront.net/102781/"
            "ga1279_decimated_point_located_em.zip"
        ),
        "expected_bytes": 613_795_566,
        "provider_etag": '"ce89eb967678e565363f3b1df055e12c-2"',
    },
    {
        "system": "SkyTEM",
        "dataset_number": 22131,
        "survey_id": "1305",
        "record_id": 121613,
        "package_id": "8ff431a5-a5b0-41b2-9474-268a5de2e418",
        "resource_name": "Located observed data",
        "url": (
            "https://d28rz98at9flks.cloudfront.net/121613/"
            "121613_located_data_em.zip"
        ),
        "expected_bytes": 139_294_555,
        "provider_etag": '"27d7b7d1943eaea7022c41596d8c89f3"',
    },
    {
        "system": "SkyTEM",
        "dataset_number": 22130,
        "survey_id": "1304",
        "record_id": 122012,
        "package_id": "f891b73e-88a6-48d9-816f-2131041deea4",
        "resource_name": "Processed electromagnetic data",
        "url": "https://d28rz98at9flks.cloudfront.net/122012/122012_02_0.zip",
        "expected_bytes": 168_667_247,
        "provider_etag": '"a056c961d98f81ef80668e702a9553c8"',
    },
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    products = {item["DATASET_NO"]: item for item in design["products"]}
    choices = []
    for choice in CHOICES:
        product = products[choice["dataset_number"]]
        if (
            product["AEM_SYSTEM"] != choice["system"]
            or str(product["SURVEY_ID"]) != choice["survey_id"]
            or not str(product["LICENCE"]).startswith("CC BY 4.0")
        ):
            raise RuntimeError("GA AEM multisystem product metadata drift")
        roles = sorted(
            {
                cell["role"]
                for cell in design["cells"]
                if choice["dataset_number"] in cell["covering_dataset_numbers"]
            }
        )
        choices.append(
            {
                **choice,
                "covered_design_roles": roles,
                "selection_basis": (
                    "pre-response system stratum and smallest official located "
                    "observation resource identified from catalogue/HTTP metadata"
                ),
                "response_access_rule": (
                    "read coordinates and line identifiers first; interpret response "
                    "only for train cells; skip buffer/calibration/test responses"
                ),
            }
        )
    result = {
        "schema_version": "wp8-geoscience-australia-aem-multisystem-sample-v1",
        "design_sha256": sha(DESIGN),
        "selection_is_response_blind": True,
        "systems": ["SkyTEM", "VTEM"],
        "choices": choices,
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"choices": len(choices), "systems": result["systems"]}))


if __name__ == "__main__":
    main()
