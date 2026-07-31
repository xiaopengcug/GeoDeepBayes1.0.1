#!/usr/bin/env python
"""Freeze a response-blind macroblock split for GA multi-system AEM parsing."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "geoscience-australia-aem-design.json"
SELECTION = EVIDENCE / "geoscience-australia-aem-multisystem-training-sample.json"
OUTPUT = EVIDENCE / "geoscience-australia-aem-multisystem-spatial-split.json"
MACROBLOCK_DEGREES = 4.0
BOUNDARY_BUFFER_KM = 70.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distance_km(left: dict, right: dict) -> float:
    mean_lat = math.radians((left["latitude"] + right["latitude"]) / 2)
    dy = (left["latitude"] - right["latitude"]) * 111.2
    dx = (left["longitude"] - right["longitude"]) * 111.2 * math.cos(mean_lat)
    return math.hypot(dx, dy)


def macroblock(cell: dict) -> str:
    latitude_index = math.floor((cell["latitude"] + 44.0) / MACROBLOCK_DEGREES)
    longitude_index = math.floor((cell["longitude"] - 112.0) / MACROBLOCK_DEGREES)
    return f"{latitude_index}:{longitude_index}"


def core_role(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-ga-aem-spatial-v2|{block}".encode()).hexdigest()[:8],
        16,
    ) % 100
    if bucket < 55:
        return "train"
    if bucket < 75:
        return "calibration"
    return "test"


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    if (
        design["aem_response_values_interpreted"] != 0
        or selection["response_values_interpreted"] != 0
        or selection["test_unseal_count"] != 0
    ):
        raise RuntimeError("response-blind split prerequisites drift")

    cells = []
    preliminary = []
    for source in design["cells"]:
        block = macroblock(source)
        role = core_role(block)
        cells.append(
            {
                "cell": source["cell"],
                "latitude": source["latitude"],
                "longitude": source["longitude"],
                "macroblock": block,
                "core_role": role,
                "role": role,
                "covering_dataset_numbers": source["covering_dataset_numbers"],
            }
        )
        preliminary.append(role)

    for index, cell in enumerate(cells):
        if any(
            preliminary[index] != preliminary[other]
            and distance_km(cell, candidate) <= BOUNDARY_BUFFER_KM
            for other, candidate in enumerate(cells)
        ):
            cell["role"] = "buffer"

    non_buffer = [cell for cell in cells if cell["role"] != "buffer"]
    cross_role_distances = [
        distance_km(left, right)
        for index, left in enumerate(non_buffer)
        for right in non_buffer[index + 1 :]
        if left["role"] != right["role"]
    ]
    counts = {
        role: sum(cell["role"] == role for cell in cells)
        for role in ("train", "buffer", "calibration", "test")
    }
    selected_numbers = {
        choice["dataset_number"] for choice in selection["choices"]
    }
    selected_counts = {
        str(number): {
            role: sum(
                cell["role"] == role
                and number in cell["covering_dataset_numbers"]
                for cell in cells
            )
            for role in ("train", "buffer", "calibration", "test")
        }
        for number in sorted(selected_numbers)
    }
    result = {
        "schema_version": "wp8-geoscience-australia-aem-multisystem-spatial-split-v2",
        "design_sha256": sha256(DESIGN),
        "selection_sha256": sha256(SELECTION),
        "split_is_response_blind": True,
        "macroblock_size_degrees": MACROBLOCK_DEGREES,
        "macroblock_role_rule": "SHA256(salt|lat_block:lon_block), 55% train, 20% calibration, 25% test",
        "boundary_buffer_km": BOUNDARY_BUFFER_KM,
        "minimum_nonbuffer_cross_role_center_distance_km": round(
            min(cross_role_distances), 3
        ),
        "partition_counts": counts,
        "selected_product_partition_counts": selected_counts,
        "design_test_cluster_upper_bound": counts["test"],
        "design_power_gate_possible": counts["test"] >= 223,
        "cells": cells,
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "warning": (
            "This remains a catalogue-cell upper bound. Located observations must "
            "be assigned by nearest frozen product-covered center before any "
            "response token is converted."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "partitions": counts,
        "selected_products": selected_counts,
        "minimum_cross_role_km": result[
            "minimum_nonbuffer_cross_role_center_distance_km"
        ],
    }))


if __name__ == "__main__":
    main()
