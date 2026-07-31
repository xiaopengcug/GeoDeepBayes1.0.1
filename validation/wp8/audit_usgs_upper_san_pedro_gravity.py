#!/usr/bin/env python
"""Parse and contract-audit USGS OFR 00-138 Appendix 4."""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-upper-san-pedro-gravity-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-upper-san-pedro-gravity.json"


def parse() -> tuple[list[dict[str, float | str]], list[str]]:
    source = (DATA / "appendix-4.html").read_text(encoding="windows-1252")
    paragraphs = re.findall(r"<p>(.*?)</p>", source, flags=re.I | re.S)
    records, rejected = [], []
    for paragraph in paragraphs:
        text = html.unescape(re.sub(r"<[^>]+>", " ", paragraph))
        tokens = text.split()
        match = None
        for id_length in range(1, min(6, len(tokens))):
            if len(tokens) == 14 + 2 * id_length and tokens[:id_length] == tokens[-id_length:]:
                match = id_length
                break
        if match is None:
            if tokens and re.search(r"\d", " ".join(tokens)):
                rejected.append(" ".join(tokens))
            continue
        middle = tokens[match:-match]
        try:
            lat = float(middle[0]) + float(middle[1]) / 60.0
            lon = -(abs(float(middle[2])) + float(middle[3]) / 60.0)
            values = [float(value.rstrip("mMfF")) for value in middle[4:]]
            records.append(
                {
                    "id": " ".join(tokens[:match]),
                    "latitude": lat,
                    "longitude": lon,
                    "altitude_m": values[0],
                    "observed_gravity_mgal": values[1],
                    "theoretical_gravity_mgal": values[2],
                    "free_air_anomaly_mgal": values[3],
                    "simple_bouguer_anomaly_mgal": values[4],
                    "hand_terrain_correction_mgal": values[5],
                    "total_terrain_correction_mgal": values[6],
                    "curvature_correction_mgal": values[7],
                    "complete_bouguer_anomaly_mgal": values[8],
                    "complete_bouguer_sd_mgal": values[9],
                }
            )
        except (ValueError, IndexError):
            rejected.append(" ".join(tokens))
    return records, rejected


def main() -> None:
    records, rejected = parse()
    ids = [str(row["id"]) for row in records]
    sigmas = [float(row["complete_bouguer_sd_mgal"]) for row in records]
    latitudes = [float(row["latitude"]) for row in records]
    longitudes = [float(row["longitude"]) for row in records]
    # Geometry-only nominal cell counts; response values are not used for this screen.
    cells = {}
    for spacing_km in (5, 10, 15, 25, 50):
        cell_set = set()
        mean_lat = sum(latitudes) / len(latitudes)
        for lat, lon in zip(latitudes, longitudes):
            x = lon * 111.32 * math.cos(math.radians(mean_lat))
            y = lat * 111.32
            cell_set.add((math.floor(x / spacing_km), math.floor(y / spacing_km)))
        cells[str(spacing_km)] = len(cell_set)
    result = {
        "dataset": "USGS OFR 00-138 Appendix 4",
        "declared_station_count": 1521,
        "parsed_station_count": len(records),
        "unique_station_ids": len(set(ids)),
        "duplicate_station_ids": len(ids) - len(set(ids)),
        "positive_finite_complete_bouguer_sd": sum(
            math.isfinite(value) and value > 0 for value in sigmas
        ),
        "complete_bouguer_sd_range_mgal": [min(sigmas), max(sigmas)],
        "coordinate_bounds": {
            "latitude": [min(latitudes), max(latitudes)],
            "longitude": [min(longitudes), max(longitudes)],
        },
        "geometry_only_unique_cells_by_spacing_km": cells,
        "rejected_numeric_paragraph_count": len(rejected),
        "observation_contract": (
            "pass"
            if len(records) >= 1500
            and all(math.isfinite(value) and value > 0 for value in sigmas)
            else "fail"
        ),
        "cluster_gate": "not_assessed",
        "power_gate": "not_assessed",
        "notes": (
            "The source explicitly supplies complete Bouguer anomaly, total terrain "
            "correction, and standard deviation of complete Bouguer anomaly. One of the "
            "1,521 published HTML records is not machine-parseable because adjacent numeric "
            "fields lack separators; it is excluded. Geometry-only cell counts are nominal "
            "upper bounds, not correlation-adjusted clusters."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["observation_contract"] != "pass":
        raise RuntimeError(f"Appendix contract did not pass; rejected={rejected[:3]}")


if __name__ == "__main__":
    main()
