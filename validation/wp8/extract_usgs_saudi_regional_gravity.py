# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf==6.6.2"]
# ///
"""Strictly extract only unambiguous OFR 85-254 principal-fact rows."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "validation/wp8/data/usgs-saudi-regional-gravity-v1/report.pdf"
OUT = ROOT / "validation/wp8/data/usgs-saudi-regional-gravity-v1/strict-principal-facts.csv"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-saudi-regional-gravity-extraction.json"
GEOMETRY = re.compile(
    r"^\s*(\d+)\s+(.+?)\s+(1[7-9]|2[0-4])\s+"
    r"([0-9]+(?:[.,]\s*[0-9]+)?)\s+(3[9]|4[0-7])\s+"
    r"([0-9]+(?:[.,]\s*[0-9]+)?)\s+(.*)$"
)
NUMBER = re.compile(r"(?<!\S)[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?!\S)")


def main() -> None:
    reader = PdfReader(PDF)
    accepted: dict[int, list[object]] = {}
    for page_number, page in enumerate(reader.pages[66:], start=67):
        for line in (page.extract_text(extraction_mode="layout") or "").splitlines():
            if not re.match(r"^\s*\d+\s+", line):
                continue
            match = GEOMETRY.match(line)
            if not match:
                continue
            tail = match.group(7).replace(",", ".")
            tail = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", tail)
            values = NUMBER.findall(tail)
            residue = NUMBER.sub(" ", tail)
            if len(values) != 11 or residue.strip():
                continue
            sd = float(values[6])
            if sd <= 0:
                continue
            seq = int(match.group(1))
            latitude = float(match.group(3)) + float(
                match.group(4).replace(",", ".").replace(" ", "")
            ) / 60.0
            longitude = float(match.group(5)) + float(
                match.group(6).replace(",", ".").replace(" ", "")
            ) / 60.0
            record = [
                seq,
                match.group(2).strip(),
                latitude,
                longitude,
                float(values[5]),
                sd,
                page_number,
                line,
            ]
            prior = accepted.get(seq)
            if prior is None:
                accepted[seq] = record
            elif prior[2:6] != record[2:6]:
                # Conflicting duplicate extraction is not silently resolved.
                accepted.pop(seq, None)
    with OUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "sequence",
                "station_id",
                "latitude",
                "longitude",
                "complete_bouguer_anomaly_mgal",
                "complete_bouguer_sd_mgal",
                "pdf_page",
                "verbatim_extracted_line",
            ]
        )
        writer.writerows(accepted[key] for key in sorted(accepted))
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    evidence = {
        "schema_version": "wp8-saudi-regional-gravity-extraction-v1",
        "extractor": "pypdf==6.6.2 layout mode with strict no-residue numeric parser",
        "strict_records": len(accepted),
        "strict_csv_sha256": digest,
        "response_values_interpreted_before_spatial_design": len(accepted),
        "formal_test_endpoint_exposure": len(accepted),
        "formal_confirmatory_contribution": 0,
        "reason": (
            "The PDF response columns were parsed to establish recoverability before "
            "the response-blind spatial design was executed. This version is therefore "
            "training/exploratory evidence only and cannot supply a sealed formal test."
        ),
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print({"strict_records": len(accepted), "output": str(OUT)})


if __name__ == "__main__":
    main()
