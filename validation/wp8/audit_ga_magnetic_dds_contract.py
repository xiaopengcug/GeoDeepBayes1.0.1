#!/usr/bin/env python
"""Audit GA magnetic OPeNDAP declarations without requesting values or attributes."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DDS = ROOT / "validation/wp8/data/geoscience-australia-magnetic-dds-v1"
MANIFEST = DDS / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-dds-contract.json"
DECLARATION = re.compile(
    r"\s*(?:Byte|Int\d+|UInt\d+|Float\d+|String)\s+([A-Za-z_][A-Za-z0-9_]*)"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def variables(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = DECLARATION.match(line)
        if match:
            names.add(match.group(1).lower())
    return names


def flags(names: set[str]) -> dict[str, bool]:
    return {
        "latitude": bool({"latitude", "lat"} & names),
        "longitude": bool({"longitude", "lon", "long"} & names),
        "point_altitude_or_height": any(
            token in name for name in names for token in ("alt", "height", "radar")
        ),
        "line_identity": "line" in names or any(
            "line_index" in name for name in names
        ),
        "magnetic_response": any(name.startswith("mag") for name in names),
        "uncertainty": any(
            token in name
            for name in names
            for token in ("error", "sigma", "std", "uncert")
        ),
        "explicit_correction_channel": any(
            token in name
            for name in names
            for token in ("igrf", "diurnal", "base")
        ),
    }


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["design_sha256"] != sha(DESIGN)
        or manifest["successful_products"] != design["eligible_product_count"]
        or manifest["failed_products"]
        or manifest["dds_contains_declarations_only"] is not True
        or manifest["variable_attributes_requested"] is not False
        or manifest["magnetic_response_values_interpreted"] != 0
    ):
        raise RuntimeError("GA DDS freeze drift")
    products = {}
    signatures = Counter()
    geometry_response = set()
    explicit_corrections = set()
    uncertainty = set()
    for member in manifest["members"]:
        path = DDS / member["path"]
        if (
            path.stat().st_size != member["bytes"]
            or sha(path) != member["sha256"]
        ):
            raise RuntimeError(f"GA DDS integrity drift: {member['dataset_no']}")
        names = variables(path)
        product_flags = flags(names)
        dataset_no = int(member["dataset_no"])
        products[str(dataset_no)] = {
            "variables": sorted(names),
            "flags": product_flags,
        }
        signatures[tuple(sorted(names))] += 1
        base = all(
            product_flags[name]
            for name in (
                "latitude",
                "longitude",
                "point_altitude_or_height",
                "line_identity",
                "magnetic_response",
            )
        )
        if base:
            geometry_response.add(dataset_no)
        if base and product_flags["explicit_correction_channel"]:
            explicit_corrections.add(dataset_no)
        if base and product_flags["uncertainty"]:
            uncertainty.add(dataset_no)

    coverage = {}
    for label, dataset_numbers in (
        ("geometry_response", geometry_response),
        ("plus_explicit_corrections", explicit_corrections),
        ("plus_uncertainty", uncertainty),
    ):
        counts = {
            assigned: sum(
                cell["role"] == assigned
                and bool(dataset_numbers & set(cell["covering_dataset_numbers"]))
                for cell in design["cells"]
            )
            for assigned in ("train", "buffer", "calibration", "test")
        }
        coverage[label] = {
            "product_count": len(dataset_numbers),
            "partition_cell_counts": counts,
            "test_count_meets_223": counts["test"] >= 223,
        }
    result = {
        "schema_version": "wp8-geoscience-australia-magnetic-dds-contract-v1",
        "design_sha256": sha(DESIGN),
        "dds_manifest_sha256": sha(MANIFEST),
        "products_audited": len(products),
        "schema_signature_count": len(signatures),
        "dds_declarations_only": True,
        "variable_attributes_requested": False,
        "magnetic_response_values_interpreted": 0,
        "coverage": coverage,
        "standardized_processing_contract": (
            "AWAGS/tie/micro-levelled response names are common, but DDS "
            "declarations alone do not prove survey-specific correction provenance"
        ),
        "uncertainty_contract": (
            "no design-eligible product declares a per-observation uncertainty "
            "variable; training-only tie-line crossover evidence is required"
        ),
        "formal_contract_ready": False,
        "products": products,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "products": len(products),
                "geometry_response": coverage["geometry_response"],
                "explicit_corrections": coverage["plus_explicit_corrections"],
                "uncertainty": coverage["plus_uncertainty"],
            }
        )
    )


if __name__ == "__main__":
    main()
