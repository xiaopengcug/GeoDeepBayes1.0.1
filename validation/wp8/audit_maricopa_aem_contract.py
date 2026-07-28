#!/usr/bin/env python
"""Audit the frozen Maricopa 2018 survey-specific AEM observation contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from netCDF4 import Dataset
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/maricopa-aem-v1"
MANIFEST = RAW / "raw-manifest.json"
SOURCE = RAW / "MaricopaCA2018.nc"
REPORT = RAW / "MaricopaCA2018_SkyTEMApS_DataReport.pdf"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/maricopa-aem-contract-readiness.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["observation_response_interpreted"] is not False:
        raise RuntimeError("Maricopa response interpreted before contract audit")
    reader = PdfReader(REPORT)
    pages = {
        page: reader.pages[page - 1].extract_text() or ""
        for page in (13, 14, 15, 20, 21, 22, 33, 39, 40, 41)
    }
    phrases = {
        13: ("dual moment configuration", "Gate times"),
        14: ("Gate times",),
        15: ("Gate times",),
        20: ("waveforms applied in the forward modelling",),
        21: ("Base frequency 210 Hz", "Current range 6 Amp"),
        22: ("Base frequency 30 Hz", "Current range 110 Amp"),
        33: ("resulting data uncertainty",),
        39: ("Transmitter area 342 m", "Peak current 6 Amp", "Peak current 110 Amp"),
        40: ("null-position", "Z coil", "X coil"),
        41: ("Receiver gate times", "transmitter current turn-off"),
    }
    missing = {
        page: [phrase for phrase in expected if phrase.lower() not in pages[page].lower()]
        for page, expected in phrases.items()
    }
    missing = {page: values for page, values in missing.items() if values}
    if missing:
        raise RuntimeError(f"Maricopa report phrases missing: {missing}")
    with Dataset(SOURCE) as dataset:
        table = dataset.groups["survey"].groups["tabular"].groups["1"]
        required = {
            "X",
            "Y",
            "LINE",
            "LM_gate_times",
            "HM_gate_times",
            "LM_DATA_dBdt",
            "LM_DATA_STD",
            "HM_DATA_dBdt",
            "HM_DATA_STD",
            "TX_ALT",
            "TX_ALT_STD",
            "RX_ALT",
            "RX_ALT_STD",
        }
        missing_variables = sorted(required - table.variables.keys())
        if missing_variables:
            raise RuntimeError(f"Maricopa netCDF contract drift: {missing_variables}")
        rows = len(table.dimensions["index"])
        lm_gates = len(table.dimensions["LM_gate_times"])
        hm_gates = len(table.dimensions["HM_gate_times"])
    result = {
        "schema_version": "wp8-maricopa-aem-contract-readiness-v1",
        "passed": True,
        "doi": "10.5066/P9R1XBPG",
        "raw_manifest_sha256": sha(MANIFEST),
        "source_sha256": sha(SOURCE),
        "report_sha256": sha(REPORT),
        "report_pages_checked": sorted(pages),
        "system": "SkyTEM 312 dual moment",
        "processed_observation_rows": rows,
        "low_moment": {
            "frequency_hz": 210,
            "current_a": 6,
            "turns": 2,
            "gate_count": lm_gates,
        },
        "high_moment": {
            "frequency_hz": 30,
            "current_a": 110,
            "turns": 12,
            "gate_count": hm_gates,
        },
        "transmitter_area_m2": 342,
        "receiver_components": ["Z", "X"],
        "receiver_geometry": "survey-specific null-position coordinates documented",
        "normalized_current_waveform_tables": True,
        "per_observation_standard_deviation": True,
        "transmitter_receiver_altitude_standard_deviation": True,
        "observation_response_values_parsed": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "rows": rows, "gates": [lm_gates, hm_gates]}))


if __name__ == "__main__":
    main()
