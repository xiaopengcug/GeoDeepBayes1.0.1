#!/usr/bin/env python
"""Freeze consortium AEM roles using coordinates and acquisition identifiers only."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/tem-aem-consortium-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/tem-aem-consortium-design-split.json"


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


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["observation_response_interpreted"] is not False:
        raise RuntimeError("consortium response was interpreted before split")
    counts = {}
    coordinate_hash = hashlib.sha256()
    for survey in ("yellowstone", "hualapai"):
        rows = 0
        cells: dict[str, set[tuple[int, int]]] = defaultdict(set)
        lines: dict[str, set[str]] = defaultdict(set)
        if survey == "yellowstone":
            paths = sorted((RAW / survey).glob("*_ProcessedData_Models.csv"))
            paths = [path for path in paths if "DataDictionary" not in path.name]
            prefix_expected = (
                "Block",
                "Flight",
                "LINE_NO",
                "E_UTM12N",
                "N_UTM12N",
                "Ytopbathv2",
                "TIMESTAMP",
                "FID",
                "ALT",
            )
            limit = 9
            line_index, east_index, north_index = 2, 3, 4
        else:
            paths = [RAW / survey / "GrandCanyonWest2018_ProcessedAEMdata.csv"]
            prefix_expected = ("LINE", "TIME", "X_UTM12N", "Y_UTM12N", "DEM", "ALT")
            limit = 6
            line_index, east_index, north_index = 0, 2, 3
        for path in paths:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                header = stream.readline().rstrip("\r\n").split(",")
                if tuple(header[: len(prefix_expected)]) != prefix_expected:
                    raise RuntimeError(f"{survey} design schema drift: {path.name}")
                for raw_line in stream:
                    fields = raw_line.rstrip("\r\n").split(",", limit)
                    if len(fields) != limit + 1:
                        raise RuntimeError(f"{survey} short row: {path.name}")
                    east = float(fields[east_index])
                    north = float(fields[north_index])
                    assigned = role(east)
                    lines[assigned].add(fields[line_index])
                    cells[assigned].add((math.floor(east / 500), math.floor(north / 500)))
                    coordinate_hash.update(
                        (
                            f"{survey}|{path.name}|{fields[line_index]}|"
                            f"{fields[east_index]}|{fields[north_index]}\n"
                        ).encode()
                    )
                    rows += 1
        counts[survey] = {
            "design_rows": rows,
            "design_line_counts": {
                name: len(lines[name]) for name in ("train", "buffer", "calibration", "test")
            },
            "candidate_500m_cell_counts": {
                name: len(cells[name]) for name in ("train", "buffer", "calibration", "test")
            },
        }
    result = {
        "schema_version": "wp8-tem-aem-consortium-design-split-v1",
        "candidate_status": "design_split_frozen_before_response_interpretation",
        "raw_manifest_sha256": sha(MANIFEST),
        "assignment": {
            "cell_m": 500,
            "period_m": 12000,
            "stripe_width_m": 1000,
            "stripe_roles": {
                "buffer": [0, 6, 9],
                "train": [1, 2, 3, 4, 5],
                "calibration": [7, 8],
                "test": [10, 11],
            },
            "boundary_statement": "held-out stripes are separated from training by 1-km buffers",
        },
        "surveys": counts,
        "combined_candidate_500m_cell_counts": {
            role_name: sum(
                counts[survey]["candidate_500m_cell_counts"][role_name]
                for survey in counts
            )
            for role_name in ("train", "buffer", "calibration", "test")
        },
        "design_coordinate_stream_sha256": coordinate_hash.hexdigest(),
        "observation_response_values_parsed": False,
        "formal_cluster_gate_passed": False,
        "formal_power_gate_passed": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "surveys": counts,
                "combined": result["combined_candidate_500m_cell_counts"],
            }
        )
    )


if __name__ == "__main__":
    main()
