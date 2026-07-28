#!/usr/bin/env python
"""Training-only correlation audit for Yellowstone and Hualapai AEM candidates."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from audit_east_river_aem_training import empirical_range

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/tem-aem-consortium-v1"
MANIFEST = RAW / "raw-manifest.json"
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/tem-aem-consortium-design-split.json"
EAST = ROOT / "validation/wp8/evidence/feasibility-v1/east-river-aem-train-diagnostics.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/tem-aem-consortium-train-diagnostics.json"
CELL_M = 500.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def role(easting: float) -> str:
    stripe = math.floor(easting / 1000.0) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def summarize(
    survey: str,
    cell_values: dict[tuple[int, int], dict[str, list[float]]],
    fixed_channels: tuple[str, ...],
    test_cells: int,
) -> dict[str, object]:
    channel_diagnostics = {}
    ranges = []
    for channel in fixed_channels:
        populated = [
            (cell, float(np.median(values[channel])))
            for cell, values in cell_values.items()
            if values[channel]
        ]
        centers = np.asarray(
            [[(cell[0] + 0.5) * CELL_M, (cell[1] + 0.5) * CELL_M] for cell, _ in populated]
        )
        values = np.asarray([value for _, value in populated])
        selected_range, variogram = empirical_range(centers, values)
        conservative = 10_000.0 if selected_range is None else selected_range
        ranges.append(conservative)
        channel_diagnostics[channel] = {
            "training_cells": len(populated),
            "range_m": selected_range,
            "range_censored_above_m": 10_000.0 if selected_range is None else None,
            "sill": float(np.var(values, ddof=1)),
            "variogram": variogram,
        }
    selected = max(ranges)
    merge = max(1, math.ceil((selected / CELL_M) ** 2))
    return {
        "survey": survey,
        "fixed_channels": list(fixed_channels),
        "channel_diagnostics": channel_diagnostics,
        "conservative_spatial_correlation_range_m": selected,
        "merge_factor": merge,
        "design_test_cells": test_cells,
        "correlation_adjusted_test_cluster_upper_bound": math.ceil(test_cells / merge),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    east = json.loads(EAST.read_text(encoding="utf-8"))
    if (
        manifest["observation_response_interpreted"] is not False
        or split["observation_response_values_parsed"] is not False
        or split["raw_manifest_sha256"] != sha(MANIFEST)
    ):
        raise RuntimeError("AEM consortium preregistration drift")
    results = {}

    # Yellowstone: response interpretation begins only after the fixed
    # coordinate-stripe role is known to be training.
    yellowstone_cells: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(
        lambda: {name: [] for name in ("LM8", "LM16", "LM24", "HM8", "HM17", "HM25")}
    )
    yellowstone_rows = 0
    yellowstone_skipped = defaultdict(int)
    for path in sorted((RAW / "yellowstone").glob("*_ProcessedData_Models.csv")):
        if "DataDictionary" in path.name:
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            header = stream.readline().rstrip("\r\n").split(",")
            index = {name: position for position, name in enumerate(header)}
            channels = {
                "LM8": ("LM_Data[8]", "LM_DataSTD[8]"),
                "LM16": ("LM_Data[16]", "LM_DataSTD[16]"),
                "LM24": ("LM_Data[24]", "LM_DataSTD[24]"),
                "HM8": ("HM_Data[8]", "HM_DataSTD[8]"),
                "HM17": ("HM_Data[17]", "HM_DataSTD[17]"),
                "HM25": ("HM_Data[25]", "HM_DataSTD[25]"),
            }
            if any(name not in index for pair in channels.values() for name in pair):
                raise RuntimeError(f"Yellowstone response schema drift: {path.name}")
            for raw_line in stream:
                prefix = raw_line.rstrip("\r\n").split(",", 9)
                east_value = float(prefix[3])
                assigned = role(east_value)
                if assigned != "train":
                    yellowstone_skipped[assigned] += 1
                    continue
                values = prefix[:9] + prefix[9].split(",")
                if len(values) != len(header):
                    raise RuntimeError(f"Yellowstone training width drift: {path.name}")
                north_value = float(values[4])
                cell = (math.floor(east_value / CELL_M), math.floor(north_value / CELL_M))
                for label, (data_name, std_name) in channels.items():
                    data = float(values[index[data_name]])
                    standard = float(values[index[std_name]])
                    if (
                        data != -9999
                        and standard != -9999
                        and np.isfinite(data)
                        and np.isfinite(standard)
                        and standard > 0
                    ):
                        yellowstone_cells[cell][label].append(
                            math.copysign(math.log1p(abs(data) / standard), data)
                        )
                yellowstone_rows += 1
    results["yellowstone"] = {
        **summarize(
            "yellowstone",
            yellowstone_cells,
            ("LM8", "LM16", "LM24", "HM8", "HM17", "HM25"),
            split["surveys"]["yellowstone"]["candidate_500m_cell_counts"]["test"],
        ),
        "training_rows_interpreted": yellowstone_rows,
        "held_out_rows_skipped_without_response_parsing": dict(yellowstone_skipped),
    }

    hualapai_cells: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(
        lambda: {name: [] for name in ("G10", "G25", "G40")}
    )
    hualapai_rows = 0
    hualapai_skipped = defaultdict(int)
    path = RAW / "hualapai/GrandCanyonWest2018_ProcessedAEMdata.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        header = stream.readline().rstrip("\r\n").split(",")
        index = {name: position for position, name in enumerate(header)}
        channels = {
            "G10": ("DATA_dBdt_10", "DATASTD_10"),
            "G25": ("DATA_dBdt_25", "DATASTD_25"),
            "G40": ("DATA_dBdt_40", "DATASTD_40"),
        }
        for raw_line in stream:
            prefix = raw_line.rstrip("\r\n").split(",", 6)
            east_value = float(prefix[2])
            assigned = role(east_value)
            if assigned != "train":
                hualapai_skipped[assigned] += 1
                continue
            values = prefix[:6] + prefix[6].split(",")
            if len(values) != len(header):
                raise RuntimeError("Hualapai training width drift")
            north_value = float(values[3])
            cell = (math.floor(east_value / CELL_M), math.floor(north_value / CELL_M))
            for label, (data_name, std_name) in channels.items():
                data = float(values[index[data_name]])
                standard = float(values[index[std_name]])
                if (
                    data != -9999
                    and standard != -9999
                    and np.isfinite(data)
                    and np.isfinite(standard)
                    and standard > 0
                ):
                    hualapai_cells[cell][label].append(
                        math.copysign(math.log1p(abs(data) / standard), data)
                    )
            hualapai_rows += 1
    results["hualapai"] = {
        **summarize(
            "hualapai",
            hualapai_cells,
            ("G10", "G25", "G40"),
            split["surveys"]["hualapai"]["candidate_500m_cell_counts"]["test"],
        ),
        "training_rows_interpreted": hualapai_rows,
        "held_out_rows_skipped_without_response_parsing": dict(hualapai_skipped),
    }
    combined_upper_bound = (
        east["correlation_adjusted_test_cluster_upper_bound"]
        + sum(
            result["correlation_adjusted_test_cluster_upper_bound"]
            for result in results.values()
        )
    )
    output = {
        "schema_version": "wp8-tem-aem-consortium-train-diagnostics-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "split_sha256": sha(SPLIT),
        "east_river_diagnostics_sha256": sha(EAST),
        "transform": "fixed-channel signed log1p(abs(DATA)/DATASTD)",
        "surveys": results,
        "sealed_response_rows_interpreted": {
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "combined_with_east_river_correlation_adjusted_test_cluster_upper_bound": combined_upper_bound,
        "coverage_required_clusters": 223,
        "cluster_gate_passed": combined_upper_bound >= 223,
        "power_gate_passed": False,
        "power_reason": "training-only paired-CRPS effect size unavailable",
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                survey: {
                    "range_m": result["conservative_spatial_correlation_range_m"],
                    "test_upper_bound": result[
                        "correlation_adjusted_test_cluster_upper_bound"
                    ],
                }
                for survey, result in results.items()
            }
            | {"combined_with_east": combined_upper_bound}
        )
    )


if __name__ == "__main__":
    main()
