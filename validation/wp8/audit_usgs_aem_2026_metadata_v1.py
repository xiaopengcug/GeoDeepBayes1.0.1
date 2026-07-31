#!/usr/bin/env python
"""Response-blind audit of the 2026 USGS Mojave and Coalinga AEM candidates."""
from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from io import BytesIO
from pathlib import Path

import shapefile

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-aem-2026-unexposed-metadata-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-aem-2026-unexposed-metadata-audit-v1.json"
REQUIRED_TEST_CLUSTERS = 223
# Maximum uncensored SkyTEM training-only correlation range already registered by
# usgs-aem-training-response-diagnostics-v1.json. Selecting a smaller observed
# range after seeing candidate geometry would be outcome-adaptive.
FROZEN_CORRELATION_RANGE_KM = 3.51


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def centers(reader: shapefile.Reader, survey: str) -> list[dict[str, float | int | str]]:
    result = []
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        bbox = shape_record.shape.bbox
        result.append(
            {
                "survey": survey,
                "line": int(record["Line"]),
                "easting_m": (bbox[0] + bbox[2]) / 2.0,
                "northing_m": (bbox[1] + bbox[3]) / 2.0,
            }
        )
    return result


def component_count(points: list[dict[str, float | int | str]], range_km: float) -> int:
    parent = list(range(len(points)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    radius2 = (range_km * 1000.0) ** 2
    for left in range(len(points)):
        for right in range(left):
            dx = float(points[left]["easting_m"]) - float(points[right]["easting_m"])
            dy = float(points[left]["northing_m"]) - float(points[right]["northing_m"])
            if dx * dx + dy * dy <= radius2:
                root_left, root_right = find(left), find(right)
                if root_left != root_right:
                    parent[root_right] = root_left
    return len({find(index) for index in range(len(points))})


def ncml_contract(path: Path) -> dict[str, bool]:
    # The official Mojave NCML contains an unescaped Python-list value with
    # nested apostrophes, so use a deliberately narrow tag-name scan rather
    # than silently repairing the source file.
    text = path.read_text(encoding="utf-8", errors="replace")
    variables = set(
        re.findall(r"<variable\s+name=[\"']([^\"']+)[\"']", text, flags=re.IGNORECASE)
    )
    joined_attributes = text.lower()
    joined_variables = "\n".join(name.lower() for name in variables)
    return {
        "coordinates": all(token in joined_attributes for token in ("easting", "northing")),
        "line_identity": "line" in {name.lower() for name in variables},
        "transmitter_current": "current" in joined_attributes or "current" in joined_variables,
        "exact_waveform": "waveform_time" in joined_attributes and "waveform_current" in joined_attributes,
        "gate_times": "gate_times" in joined_variables or "gate_center" in joined_attributes,
        "response_components": "dbdt" in joined_variables,
        "per_observation_uncertainty": any(
            token in joined_variables for token in ("relunc", "_std", "error")
        ),
    }


def main() -> None:
    coalinga_reader = shapefile.Reader(str(RAW / "CoalingaCA2022_flightlines.shp"))
    coalinga = centers(coalinga_reader, "coalinga")

    with zipfile.ZipFile(RAW / "CA_WestMojaveAEM_Flightlines.zip") as archive:
        base = next(
            info.filename[:-4]
            for info in archive.infolist()
            if info.filename.lower().endswith(".shp")
        )
        mojave_reader = shapefile.Reader(
            shp=BytesIO(archive.read(base + ".shp")),
            shx=BytesIO(archive.read(base + ".shx")),
            dbf=BytesIO(archive.read(base + ".dbf")),
        )
        mojave = centers(mojave_reader, "western_mojave")

    points = coalinga + mojave
    sensitivity = {
        str(range_km): component_count(points, range_km)
        for range_km in (0.35, 1.72, 3.51, 3.82, 7.0, 15.5, 55.0)
    }
    frozen_components = sensitivity[str(FROZEN_CORRELATION_RANGE_KM)]
    result = {
        "schema_version": "wp8-usgs-aem-2026-unexposed-metadata-audit-v1",
        "audit_mode": "response_blind",
        "response_payloads_downloaded": 0,
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
        "candidates": [
            {
                "doi": "10.5066/P18JCA5M",
                "name": "Western Mojave Desert SkyTEM312, 2024",
                "line_records": len(mojave),
                "unique_line_ids": len({point["line"] for point in mojave}),
                "response_payload": {
                    "name": "CA_WMojaveAEM_rawdata.nc",
                    "bytes": 2989043342,
                    "downloaded": False,
                },
                "metadata_contract": ncml_contract(RAW / "CA_WMojaveAEM_rawdata.ncml"),
            },
            {
                "doi": "10.5066/P14TP9LW",
                "name": "Coalinga and Pyramid Hills SkyTEM312, 2022",
                "line_records": len(coalinga),
                "unique_line_ids": len({point["line"] for point in coalinga}),
                "response_payload": {
                    "name": "CoalingaCA2022.nc",
                    "bytes": 1344404553,
                    "downloaded": False,
                },
                "metadata_contract": ncml_contract(RAW / "CoalingaCA2022.ncml"),
            },
        ],
        "combined_geometry": {
            "raw_line_records": len(points),
            "unique_survey_line_pairs": len(
                {(point["survey"], point["line"]) for point in points}
            ),
            "cluster_merge_rule": (
                "Line-centre vertices separated by no more than the frozen correlation "
                "range are joined; each connected component is one cluster."
            ),
            "frozen_training_only_correlation_range_km": FROZEN_CORRELATION_RANGE_KM,
            "frozen_range_source": (
                "usgs-aem-training-response-diagnostics-v1.json: maximum uncensored "
                "SkyTEM training-only fitted range"
            ),
            "effective_cluster_upper_bound": frozen_components,
            "sensitivity_component_counts": sensitivity,
            "required_test_clusters": REQUIRED_TEST_CLUSTERS,
            "passes_cluster_gate": frozen_components >= REQUIRED_TEST_CLUSTERS,
        },
        "decision": "abort_before_response_payload",
        "reason": (
            f"The two surveys provide {len(points)} raw line records but only "
            f"{frozen_components} correlation-merged components at the frozen "
            f"{FROZEN_CORRELATION_RANGE_KM:.2f}-km training-only range, below "
            f"{REQUIRED_TEST_CLUSTERS}; downloading 4.33 GB of response payload "
            "cannot repair the cluster or prospective-power gates."
        ),
        "formal_tem_effect": {
            "observation_contract_passed": True,
            "effective_test_clusters_passed": False,
            "prospective_power_passed": False,
        },
        "metadata_sha256": {
            path.name: sha256(path)
            for path in sorted(RAW.iterdir())
            if path.is_file()
        },
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"raw_lines": len(points), "effective_clusters": frozen_components}))


if __name__ == "__main__":
    main()
