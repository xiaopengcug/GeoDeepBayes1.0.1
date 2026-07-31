#!/usr/bin/env python
"""Freeze the public EPA PFAS source-zone SIP publication dataset."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/epa-pfas-sip-v1"
DOI = "10.23719/1531789"
BASE = f"https://pasteur.epa.gov/uploads/{DOI}"
FILES = [
    "JHAZ_Sieg_Fig_Data.xlsx",
    "Seigenthaler et al PFAS Source Zone J of Haz Materials meta data.docx",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for name in FILES:
        path = DATA / name
        url = f"{BASE}/{quote(name)}"
        request = urllib.request.Request(
            url, headers={"User-Agent": "GeoDeepBayes-WP8 EPA SIP freeze"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
        path.write_bytes(payload)
        members.append(
            {"path": name, "bytes": len(payload), "sha256": sha256(path), "source_url": url}
        )
    manifest = {
        "schema_version": "wp8-epa-pfas-sip-raw-v1",
        "doi": DOI,
        "publisher": "U.S. EPA Office of Research and Development",
        "access_level": "public",
        "partition_assignment": "training-only",
        "partition_assignment_precedes_response_read": True,
        "selection_is_response_blind": True,
        "members": members,
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (*[DATA / name for name in FILES], manifest_path):
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(members), "bytes": sum(x["bytes"] for x in members)}))


if __name__ == "__main__":
    main()
