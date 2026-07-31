#!/usr/bin/env python
"""Acquire only the preregistered USGS AEM training payloads."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-aem-training-expansion-design-v1.json"
)
OUT = ROOT / "validation/wp8/data/usgs-aem-training-expansion-v1"
FILES = OUT / "files"
MANIFEST = OUT / "raw-manifest.json"
WORKERS = 2
ATTEMPTS = 5
BLOCK = 8 * 1024 * 1024
USER_AGENT = "GeoDeepBayes-WP8 USGS-AEM-training/1.0"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def acquire(survey: dict) -> dict:
    payload = survey["payload"]
    expected = int(payload["size"])
    target = FILES / f"{survey['sciencebase_id']}__{payload['name']}"
    part = target.with_suffix(target.suffix + ".part")
    fallback = (
        "https://www.sciencebase.gov/catalog/file/get/"
        f"{survey['sciencebase_id']}?"
        + urllib.parse.urlencode({"name": payload["name"]})
    )
    if target.exists() and target.stat().st_size == expected:
        return {
            "sciencebase_id": survey["sciencebase_id"],
            "systems": survey["systems"],
            "name": payload["name"],
            "path": target.relative_to(OUT).as_posix(),
            "bytes": expected,
            "sha256": sha(target),
            "source_url": payload["downloadUri"],
            "resumed": True,
        }
    error: Exception | None = None
    for url in (payload["downloadUri"], fallback):
        for attempt in range(ATTEMPTS):
            try:
                offset = part.stat().st_size if part.exists() else 0
                headers = {"User-Agent": USER_AGENT}
                if offset:
                    headers["Range"] = f"bytes={offset}-"
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=300) as response:
                    status = getattr(response, "status", 200)
                    mode = "ab" if offset and status == 206 else "wb"
                    with part.open(mode) as stream:
                        first = True
                        while True:
                            block = response.read(BLOCK)
                            if not block:
                                break
                            if first and mode == "wb" and block.lstrip().lower().startswith(
                                (b"<!doctype", b"<html")
                            ):
                                raise RuntimeError(
                                    f"HTML payload returned for {payload['name']}"
                                )
                            first = False
                            stream.write(block)
                size = part.stat().st_size
                if size != expected:
                    raise RuntimeError(
                        f"length mismatch for {payload['name']}: "
                        f"{size} != {expected}"
                    )
                os.replace(part, target)
                return {
                    "sciencebase_id": survey["sciencebase_id"],
                    "systems": survey["systems"],
                    "name": payload["name"],
                    "path": target.relative_to(OUT).as_posix(),
                    "bytes": expected,
                    "sha256": sha(target),
                    "source_url": url,
                    "resumed": offset > 0,
                }
            except Exception as caught:
                error = caught
                # A small HTML/error payload cannot be resumed as observation
                # data. Exact-path cleanup is safe and leaves completed files.
                if part.exists() and part.stat().st_size < 1024 * 1024:
                    part.unlink()
                if attempt + 1 < ATTEMPTS:
                    time.sleep(min(30, 2**attempt))
    raise RuntimeError(
        f"training acquisition failed: {survey['sciencebase_id']}"
    ) from error


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        not design["selection_frozen_before_payload_access"]
        or design["test_unseal_count"] != 0
        or design["test_responses_interpreted"] != 0
    ):
        raise RuntimeError("USGS AEM training design is not sealed")
    FILES.mkdir(parents=True, exist_ok=True)
    members = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(acquire, survey): survey
            for survey in design["training_surveys"]
        }
        for index, future in enumerate(as_completed(futures), 1):
            member = future.result()
            members.append(member)
            print(
                json.dumps(
                    {
                        "completed": index,
                        "total": len(futures),
                        "id": member["sciencebase_id"],
                        "bytes": member["bytes"],
                    }
                ),
                flush=True,
            )
    members.sort(key=lambda value: value["sciencebase_id"])
    result = {
        "schema_version": "wp8-usgs-aem-training-expansion-raw-manifest-v1",
        "design_sha256": sha(DESIGN),
        "training_survey_count": len(members),
        "members": members,
        "bytes": sum(member["bytes"] for member in members),
        "covered_design_roles": ["training"],
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_surveys": len(members),
                "bytes": result["bytes"],
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
