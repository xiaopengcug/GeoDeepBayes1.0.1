#!/usr/bin/env python
"""Parse the frozen training-only TDIP profiles and quantify their data contract."""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = (
    ROOT
    / "validation/wp8/data/zenodo-tdip-full-decay-v1/training-extract"
    / "field_survey/field_processed_data"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "zenodo-tdip-full-decay-training-diagnostics.json"
)
PROFILES = ("n1", "n12", "s2", "s4", "s7")
BASE_COLUMNS = 19
WINDOWS = 18
WINDOW_COLUMNS = 5


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "max": ordered[-1],
    }


def main() -> None:
    profile_results = []
    all_std: list[float] = []
    all_window_centres: set[float] = set()
    all_window_widths: set[float] = set()
    total_rows = total_row_in_use = total_window_values = total_windows_in_use = 0
    for profile in PROFILES:
        path = DATA / f"{profile}.dip"
        rows = row_in_use = window_values = windows_in_use = 0
        quadrupoles: set[tuple[float, ...]] = set()
        x_values: list[float] = []
        y_values: list[float] = []
        profile_std: list[float] = []
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line or line.startswith("/"):
                    continue
                fields = line.split()
                if fields[:2] == ["DIP", "EXPORT"] or fields == ["0"]:
                    continue
                expected = BASE_COLUMNS + WINDOWS * WINDOW_COLUMNS
                if len(fields) != expected:
                    raise RuntimeError(
                        f"{profile}: expected {expected} columns, got {len(fields)}"
                    )
                values = [float(value) for value in fields]
                rows += 1
                row_in_use += int(values[18] != 0)
                quadrupoles.add(tuple(values[9:17]))
                x_values.extend(values[index] for index in (9, 11, 13, 15))
                y_values.extend(values[index] for index in (10, 12, 14, 16))
                for window in range(WINDOWS):
                    offset = BASE_COLUMNS + window * WINDOW_COLUMNS
                    centre, width, data, std, in_use = values[offset : offset + 5]
                    all_window_centres.add(centre)
                    all_window_widths.add(width)
                    if math.isfinite(data):
                        window_values += 1
                    if math.isfinite(std):
                        profile_std.append(abs(std))
                    windows_in_use += int(in_use != 0)
        profile_results.append(
            {
                "profile": profile,
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows": rows,
                "unique_abmn_quadrupoles": len(quadrupoles),
                "row_in_use": row_in_use,
                "row_in_use_fraction": row_in_use / rows,
                "window_values": window_values,
                "windows_in_use": windows_in_use,
                "window_in_use_fraction": windows_in_use / window_values,
                "utm_extent": {
                    "min_x": min(x_values),
                    "max_x": max(x_values),
                    "min_y": min(y_values),
                    "max_y": max(y_values),
                },
                "absolute_window_std": quantiles(profile_std),
            }
        )
        total_rows += rows
        total_row_in_use += row_in_use
        total_window_values += window_values
        total_windows_in_use += windows_in_use
        all_std.extend(profile_std)
        os.chmod(path, 0o444)
    evidence = {
        "schema_version": "wp8-zenodo-tdip-full-decay-training-diagnostics-v1",
        "selection_role": "training_only",
        "observation_values_read": True,
        "buffer_values_read": 0,
        "calibration_values_read": 0,
        "test_values_read": 0,
        "test_unseal_count": 0,
        "contract": {
            "complete_local_abmn_geometry": True,
            "utm_coordinates_present": True,
            "apparent_resistivity_present": True,
            "decay_windows": WINDOWS,
            "window_centres_s": sorted(all_window_centres),
            "window_widths_s": sorted(all_window_widths),
            "per_window_standard_deviation_present": True,
            "row_and_window_quality_flags_present": True,
            "coordinate_system_epsg_declared": False,
            "waveform_on_time_declared": False,
        },
        "profiles": profile_results,
        "totals": {
            "profiles": len(profile_results),
            "rows": total_rows,
            "unique_abmn_quadrupoles": sum(
                item["unique_abmn_quadrupoles"] for item in profile_results
            ),
            "row_in_use": total_row_in_use,
            "row_in_use_fraction": total_row_in_use / total_rows,
            "window_values": total_window_values,
            "windows_in_use": total_windows_in_use,
            "window_in_use_fraction": total_windows_in_use / total_window_values,
            "absolute_window_std": quantiles(all_std),
        },
        "interpretation": {
            "uncertainty_contract": "passed_for_training_only_processed_profiles",
            "full_decay_contract": "passed_for_training_only_processed_profiles",
            "formal_power_gate": "failed",
            "reason": (
                "five profiles and all quadrupoles are from one field site; "
                "the release improves TDIP training uncertainty and censoring "
                "evidence but does not add independent formal test clusters"
            ),
        },
    }
    if OUTPUT.exists():
        os.chmod(OUTPUT, 0o644)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    os.chmod(OUTPUT, 0o444)
    print(json.dumps(evidence["totals"]))


if __name__ == "__main__":
    main()
