#!/usr/bin/env python
# /// script
# dependencies = ["pypdf==5.9.0"]
# ///
"""Audit frozen USGS AEM documents without opening observational response files."""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-sciencebase-aem-contract-docs-v1"
MANIFEST = DATA / "manifest.json"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-sciencebase-aem-contract-audit-v1.json"
)

PATTERNS = {
    "coordinates": re.compile(
        r"\b(latitude|longitude|easting|northing|utm[_ ]?[xy]|gps)\b", re.I
    ),
    "line_identity": re.compile(
        r"\b(line[_ ]?(number|id|name|type)|flight[_ ]?line)\b", re.I
    ),
    "flight_height": re.compile(
        r"\b(height|altitude|terrain clearance|ground clearance)\b", re.I
    ),
    "time_channels": re.compile(
        r"\b(time[_ -]?(gate|channel)|gate[_ -]?time|delay[_ -]?time|"
        r"microseconds?|milliseconds?)\b",
        re.I,
    ),
    "response_channels": re.compile(
        r"\b(db/dt|dBdt|electromagnetic response|em[_ -]?(channel|data)|"
        r"secondary field|voltage)\b",
        re.I,
    ),
    "error_model": re.compile(
        r"\b(standard deviation|uncertainty|noise (level|estimate|floor)|"
        r"relative error|absolute error|error model|data error|"
        r"noise[_ -]?(channel|estimate))\b",
        re.I,
    ),
    "processed": re.compile(
        r"\b(fully processed|processed aem|processed electromagnetic|"
        r"manual processing|data processing)\b",
        re.I,
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_for(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def normalized_evidence(text: str, pattern: re.Pattern[str]) -> list[str]:
    evidence = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line or not pattern.search(line):
            continue
        # Evidence records are short normalized fragments for reproducibility,
        # never substantial source passages.
        fragment = line[:240]
        if fragment not in evidence:
            evidence.append(fragment)
        if len(evidence) == 12:
            break
    return evidence


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["response_values_interpreted"] != 0:
        raise RuntimeError("contract-document population is response exposed")
    by_survey: dict[str, list[dict]] = defaultdict(list)
    documents = []
    for record in manifest["documents"]:
        path = DATA / record["path"]
        text = text_for(path)
        matches = {
            name: normalized_evidence(text, pattern)
            for name, pattern in PATTERNS.items()
        }
        audit = {
            "sciencebase_id": record["sciencebase_id"],
            "name": record["name"],
            "path": record["path"],
            "sha256": sha(path),
            "characters_extracted": len(text),
            "matches": matches,
        }
        documents.append(audit)
        by_survey[record["sciencebase_id"]].append(audit)

    surveys = []
    for survey in manifest["surveys"]:
        docs = by_survey[survey["sciencebase_id"]]
        criteria = {
            name: any(doc["matches"][name] for doc in docs)
            for name in PATTERNS
        }
        surveys.append(
            {
                **survey,
                "document_count": len(docs),
                "criteria": criteria,
                "geometry_contract_ready": all(
                    criteria[name]
                    for name in (
                        "coordinates",
                        "line_identity",
                        "flight_height",
                        "time_channels",
                        "response_channels",
                    )
                ),
                "explicit_error_contract_ready": criteria["error_model"],
                "provisional_observation_contract_ready": all(
                    criteria.values()
                ),
            }
        )
    output = {
        "schema_version": "wp8-usgs-sciencebase-aem-contract-audit-v1",
        "manifest_sha256": sha(MANIFEST),
        "survey_count": len(surveys),
        "surveys": surveys,
        "document_count": len(documents),
        "documents": documents,
        "geometry_contract_ready_count": sum(
            survey["geometry_contract_ready"] for survey in surveys
        ),
        "explicit_error_contract_ready_count": sum(
            survey["explicit_error_contract_ready"] for survey in surveys
        ),
        "provisional_observation_contract_ready_count": sum(
            survey["provisional_observation_contract_ready"]
            for survey in surveys
        ),
        "response_files_opened": 0,
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "surveys": len(surveys),
                "geometry_ready": output["geometry_contract_ready_count"],
                "error_ready": output["explicit_error_contract_ready_count"],
                "provisional_ready": output[
                    "provisional_observation_contract_ready_count"
                ],
                "response_values_interpreted": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
