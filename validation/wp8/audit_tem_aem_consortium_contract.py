#!/usr/bin/env python
"""Audit survey-specific contracts for the frozen AEM expansion pool."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/tem-aem-consortium-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/tem-aem-consortium-contract-readiness.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    report = RAW / "hualapai/GrandCanyonWest2018_SkyTEM_DataReport.pdf"
    dictionary = RAW / "hualapai/GrandCanyonWest2018_DataDictionary_ProcessedAEMData.csv"
    gate_file = RAW / "hualapai/GrandCanyonWest2018_AEMGateTime.csv"
    reader = PdfReader(report)
    pages = {page: reader.pages[page - 1].extract_text() or "" for page in (13, 14, 17, 21, 22, 23, 39, 40, 41, 42)}
    phrases = {
        13: ("dual moment", "Low"),
        14: ("Gate times",),
        17: ("calibrated",),
        21: ("waveforms applied in the forward modelling",),
        22: ("Base frequency 210 Hz", "Current range 6 Amp"),
        23: ("Base frequency 30 Hz", "Current range 115 Amps"),
        39: ("octagon",),
        40: ("Peak current 6 Amp", "Peak current 115 Amps"),
        41: ("null-position",),
        42: ("Receiver gate times", "transmitter current turn-off"),
    }
    missing = {
        page: [phrase for phrase in expected if phrase.lower() not in pages[page].lower()]
        for page, expected in phrases.items()
    }
    missing = {page: values for page, values in missing.items() if values}
    if missing:
        raise RuntimeError(f"Hualapai contract phrases missing: {missing}")
    with dictionary.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    definitions = {row["Field_Name"]: row for row in rows}
    required = {
        "LINE",
        "TIME",
        "X_UTM12N",
        "Y_UTM12N",
        "ALT",
        "SEGMENT",
        "DATA_dBdt_i",
        "DATASTD_i",
    }
    if not required <= definitions.keys():
        raise RuntimeError("Hualapai processed dictionary incomplete")
    with gate_file.open(encoding="utf-8-sig", newline="") as stream:
        gates = list(csv.DictReader(stream))
    if len(gates) != 44:
        raise RuntimeError("Hualapai gate count drift")
    result = {
        "schema_version": "wp8-tem-aem-consortium-contract-readiness-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "surveys": {
            "hualapai": {
                "passed": True,
                "doi": "10.5066/P91OLJN3",
                "report_path": str(report.relative_to(RAW)).replace("\\", "/"),
                "report_sha256": sha(report),
                "report_pages_checked": sorted(pages),
                "system": "SkyTEM 312M dual moment",
                "low_moment_frequency_hz": 210,
                "low_moment_current_a": 6,
                "high_moment_frequency_hz": 30,
                "high_moment_current_a": 115,
                "transmitter_geometry": "documented octagonal loop",
                "receiver_geometry": "documented null-position coils",
                "gate_count": 44,
                "per_observation_standard_deviation": True,
            },
            "yellowstone": {
                "passed": False,
                "raw_doi": "10.5066/P9MCJ9B6",
                "processed_doi": "10.5066/P9LVAU7W",
                "contractor_report": {
                    "fgdc_name": "20170706_395_Yellowstone_USGS_SkyTEM_Datareport_V2_app.pdf",
                    "sciencebase_display_name": (
                        "20170706_395_Yellowstone_USGS_SkyTEM_Datareport_V2_app-508.pdf"
                    ),
                    "catalogued_size_mb": 17.5,
                    "sciencebase_display_size_mb": 17.39,
                    "sciencebase_item_id": "5d35fe69e4b01d82ce8a61d1",
                    "historical_disk_key": (
                        "__disk__4c/50/a9/4c50a962c6a0c069f7fb009bd06524cd6d313544"
                    ),
                    "fgdc_metadata_url": (
                        "https://data.usgs.gov/datacatalog/metadata/"
                        "USGS.5d35fe69e4b01d82ce8a61d1.xml"
                    ),
                    "current_file_status": "HTTP 404",
                    "internet_archive_status": (
                        "catalog pages captured; no archived PDF payload found"
                    ),
                },
                "reason": (
                    "processed response/time/STD fields are protected locally, but the catalogued "
                    "17.5 MB survey-specific SkyTEM 312M contractor report "
                    "20170706_395_Yellowstone_USGS_SkyTEM_Datareport_V2_app.pdf returns HTTP 404 "
                    "and no archived payload was found; it is absent from the immutable pool, so "
                    "loop/current waveform cannot be reconstructed"
                ),
                "processed_dictionary_sha256": sha(
                    RAW
                    / "yellowstone/YellowstoneNP_2016_DataDictionary_ProcessedData_Models.csv"
                ),
            },
        },
        "sealed_response_values_interpreted": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hualapai": True, "yellowstone": False, "gates": len(gates)}))


if __name__ == "__main__":
    main()
