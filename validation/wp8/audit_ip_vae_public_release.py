#!/usr/bin/env python
"""Audit whether IP-VAE publishes its 1.6M-curve field compilation."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/ip-vae-public-release-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/ip-vae-public-release.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for member in manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            raise RuntimeError(f"IP-VAE frozen member drift: {member['path']}")
    record = json.loads((RAW / "zenodo-record-v0.0.2.json").read_text("utf-8"))
    with zipfile.ZipFile(RAW / "ip-vae-v0.0.2.zip") as archive:
        names = archive.namelist()
        weight_names = [name for name in names if name.endswith(".pt")]
        likely_observation_names = [
            name
            for name in names
            if Path(name).suffix.lower()
            in {".csv", ".dat", ".data", ".npy", ".npz", ".h5", ".hdf5", ".txt"}
            and "license" not in name.lower()
        ]
    source_bytes = (RAW / "arxiv-2107.14796-source.tar").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(source_bytes), mode="r:*") as archive:
        text = "\n".join(
            archive.extractfile(member).read().decode("utf-8", errors="ignore")
            for member in archive.getmembers()
            if member.isfile() and member.name.endswith(".tex")
        )
    result = {
        "schema_version": "wp8-ip-vae-public-release-audit-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "paper_doi": manifest["paper_doi"],
        "software_doi": record["doi"],
        "software_resource_type": record["metadata"]["resource_type"]["type"],
        "software_version": record["metadata"]["version"],
        "zenodo_archive_bytes": next(
            item["bytes"] for item in manifest["members"] if item["path"].endswith(".zip")
        ),
        "archive_member_count": len(names),
        "pretrained_weight_file_count": len(weight_names),
        "likely_field_observation_file_count": len(likely_observation_names),
        "paper_compilation": {
            "field_decay_curve_count": 1_600_319,
            "field_survey_count": 110,
            "countries": ["Canada", "United States", "Kazakhstan"],
            "curve_count_statement_present": "1\\,600\\,319" in text,
            "survey_count_statement_present": "110 field surveys" in text,
        },
        "license": {
            "zenodo_declared": record["metadata"]["license"]["id"],
            "repository_license": "MIT",
            "field_compilation_license_declared": False,
        },
        "field_response_payloads_downloaded": 0,
        "raw_field_compilation_publicly_released": False,
        "formal_observation_contract_ready": False,
        "formal_cluster_power_gate_passes": False,
        "reference_value": (
            "The paper proves a 110-survey, 1,600,319-curve TDIP compilation "
            "exists and the archival software release provides four pretrained "
            "weight files, but the 124,445-byte archive contains no likely field "
            "observation files. It therefore supports scale/model provenance only."
        ),
        "formal_test_endpoints_inspected": False,
        "test_unseal_count": 0,
    }
    if (
        result["software_doi"] != "10.5281/zenodo.5165398"
        or result["software_resource_type"] != "software"
        or result["zenodo_archive_bytes"] != 124445
        or result["pretrained_weight_file_count"] != 4
        or result["likely_field_observation_file_count"] != 0
        or not result["paper_compilation"]["curve_count_statement_present"]
        or not result["paper_compilation"]["survey_count_statement_present"]
    ):
        raise RuntimeError("IP-VAE archival release or paper-source drift")
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"weights": len(weight_names), "field_files": 0, "surveys": 110}))


if __name__ == "__main__":
    main()
