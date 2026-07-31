#!/usr/bin/env python
"""Freeze explicitly named NTGS IP/raw attachments as training candidates."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
CATALOGUE = EVIDENCE / "ntgs-ip-open-search-catalogue.json"
DATA = ROOT / "validation/wp8/data/ntgs-ip-explicit-candidates-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    DATA.mkdir(parents=True, exist_ok=True)
    jobs = []
    for candidate in catalogue["explicit_candidates"]:
        handle = candidate["handle_url"].rsplit("/", 1)[-1]
        for attachment in candidate["ip_or_raw_named_attachments"]:
            jobs.append(
                {
                    "path": f"{handle}-{attachment['name']}",
                    "source_url": attachment["url"],
                    "handle_url": candidate["handle_url"],
                    "title": candidate["title"],
                }
            )

    def acquire(job: dict[str, str]) -> dict[str, object]:
        path = DATA / job["path"]
        request = urllib.request.Request(
            job["source_url"],
            headers={"User-Agent": "GeoDeepBayes-WP8 NTGS IP explicit audit"},
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read()
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(payload)
        return {
            **job,
            "bytes": len(payload),
            "sha256": sha256(path),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        members = list(executor.map(acquire, jobs))
    manifest = {
        "schema_version": "wp8-ntgs-ip-explicit-candidates-v1",
        "catalogue_sha256": sha256(CATALOGUE),
        "members": members,
        "member_count": len(members),
        "total_bytes": sum(member["bytes"] for member in members),
        "selection_role": "training_candidates_only",
        "formal_test_endpoints_inspected": False,
        "test_unseal_count": 0,
    }
    manifest_path = DATA / "raw-manifest.json"
    if manifest_path.exists():
        os.chmod(manifest_path, 0o644)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in [manifest_path, *(DATA / member["path"] for member in members)]:
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(members), "bytes": manifest["total_bytes"]}))


if __name__ == "__main__":
    main()
