#!/usr/bin/env python
"""Acquire and freeze the minimal USArray TA EDI corpus.

The geographic split is frozen from catalog metadata before any EDI response
is requested.  Calibration and test EDI files are written and hashed but are
never parsed by this program.
"""
from __future__ import annotations

import hashlib
import html
import http.client
import json
import os
import re
import stat
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usarray-ta-emtf-v1"
EDI = RAW / "edi"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
IDS_URL = (
    "https://ds.iris.edu/spudservice/emtf/ids?"
    "project=USArray&survey=Transportable%20Array"
)
META_URL = (
    "https://ds.iris.edu/spudservice/emtf?"
    "project=USArray&survey=Transportable%20Array"
)


def request(url: str, attempts: int = 5) -> tuple[bytes, dict[str, str], str]:
    error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                try:
                    body = response.read()
                except http.client.IncompleteRead as incomplete:
                    # The legacy GlassFish service occasionally omits the
                    # terminating chunk even though the payload is complete.
                    body = incomplete.partial
                headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower() in {
                        "content-type", "content-length", "last-modified",
                        "etag", "date", "server",
                    }
                }
                return body, headers, datetime.now(timezone.utc).isoformat()
        except Exception as exc:  # pragma: no cover - network retry
            error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"request failed after {attempts} attempts: {url}") from error


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def merkle(leaves: list[dict[str, object]]) -> str:
    nodes = [
        hashlib.sha256(
            json.dumps(leaf, sort_keys=True, separators=(",", ":")).encode()
        ).digest()
        for leaf in leaves
    ]
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])
        nodes = [
            hashlib.sha256(nodes[i] + nodes[i + 1]).digest()
            for i in range(0, len(nodes), 2)
        ]
    return nodes[0].hex() if nodes else hashlib.sha256(b"").hexdigest()


def field(block: str, name: str) -> str:
    match = re.search(fr"<{name}(?: [^>]*)?>([^<]*)</{name}>", block)
    return html.unescape(match.group(1)).strip() if match else ""


def catalog(body: bytes) -> list[dict[str, object]]:
    text = html.unescape(body.decode("utf-8", errors="strict"))
    records = []
    for match in re.finditer(r'<EM_TF id="(\d+)"[^>]*>(.*?)</EM_TF>', text, re.S):
        block = match.group(2)
        location = re.search(r"<LocationTime[^>]*>(.*?)</LocationTime>", block, re.S)
        location_text = location.group(1) if location else ""
        records.append(
            {
                "spud_id": match.group(1),
                "product_id": field(block, "ProductId"),
                "doi": field(block, "DOI"),
                "latitude": float(field(location_text, "LatMin")),
                "longitude": float(field(location_text, "LonMin")),
                "start_time": field(location_text, "StartTime"),
                "end_time": field(location_text, "EndTime"),
                "release_status": field(block, "ReleaseStatus"),
                "survey_doi": field(block, "SurveyDOI"),
                "tags": field(block, "Tags"),
            }
        )
    return records


def freeze_split(records: list[dict[str, object]]) -> dict[str, object]:
    """Contiguous longitude regions with two one-degree exclusion buffers."""
    # Boundaries were selected from metadata only to keep >=223 sealed test
    # stations while retaining substantial training and calibration regions.
    train_cal_boundary = -104.0
    cal_test_boundary = -90.0
    buffer_degrees = 1.0
    counts = {name: 0 for name in ("train", "buffer", "calibration", "test")}
    members = []
    for record in records:
        lon = float(record["longitude"])
        if abs(lon - train_cal_boundary) < buffer_degrees or abs(lon - cal_test_boundary) < buffer_degrees:
            split = "buffer"
        elif lon < train_cal_boundary:
            split = "train"
        elif lon < cal_test_boundary:
            split = "calibration"
        else:
            split = "test"
        counts[split] += 1
        members.append(
            {
                "spud_id": record["spud_id"],
                "product_id": record["product_id"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "split": split,
            }
        )
    return {
        "schema_version": "wp8-mt-geographic-split-v1",
        "created_before_edi_requests": True,
        "coordinate_source": META_URL,
        "policy": {
            "type": "contiguous_longitude_regions",
            "train_calibration_boundary_degrees_east": train_cal_boundary,
            "calibration_test_boundary_degrees_east": cal_test_boundary,
            "exclusion_buffer_half_width_degrees": buffer_degrees,
            "buffer_members_excluded_from_analysis": True,
        },
        "counts": counts,
        "members": members,
    }


def atomic_json(path: Path, value: object) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    EDI.mkdir(parents=True, exist_ok=True)
    ids_body, ids_headers, ids_time = request(IDS_URL)
    meta_body, meta_headers, meta_time = request(META_URL)
    ids = [line.strip() for line in ids_body.decode().splitlines() if line.strip()]
    records = catalog(meta_body)
    if len(ids) != 1104 or len(records) != 1104:
        raise RuntimeError(f"official catalog drift: ids={len(ids)}, metadata={len(records)}")
    if set(ids) != {str(item["spud_id"]) for item in records}:
        raise RuntimeError("ID and metadata member sets differ")
    if any(item["release_status"] != "Unrestricted Release" for item in records):
        raise RuntimeError("non-unrestricted member in selected survey")

    split = freeze_split(records)
    if split["counts"]["test"] < 223:
        raise RuntimeError("geographic test region is underpowered for coverage")
    atomic_json(RAW / "geographic-split.json", split)
    # The split exists on disk before the first endpoint-bearing EDI request.
    members = []
    split_by_id = {item["spud_id"]: item["split"] for item in split["members"]}

    def acquire_member(spud_id: str) -> dict[str, object]:
        url = f"https://ds.iris.edu/spudservice/emtf/{spud_id}/edi"
        path = EDI / f"{spud_id}.edi"
        if path.is_file():
            body = path.read_bytes()
            headers = {"resume": "local-existing-file"}
            retrieved = None
        else:
            body, headers, retrieved = request(url)
            path.write_bytes(body)
        return {
            "spud_id": spud_id,
            "split": split_by_id[spud_id],
            "request_url": url,
            "retrieved_at_utc": retrieved,
            "http_metadata": headers,
            "bytes": len(body),
            "sha256": sha(body),
            "path": f"edi/{spud_id}.edi",
        }

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(acquire_member, spud_id): spud_id
            for spud_id in sorted(ids, key=int)
        }
        for index, future in enumerate(as_completed(futures), 1):
            members.append(future.result())
            if index % 100 == 0:
                print(f"downloaded/verified {index}/{len(ids)}")
    members.sort(key=lambda item: int(str(item["spud_id"])))
    manifest = {
        "schema_version": "wp8-usarray-ta-raw-manifest-v1",
        "survey_doi": "10.17611/DP/EMTF/USARRAY/TA",
        "outcome_values_interpreted": False,
        "catalog_requests": [
            {"url": IDS_URL, "retrieved_at_utc": ids_time, "headers": ids_headers, "bytes": len(ids_body), "sha256": sha(ids_body)},
            {"url": META_URL, "retrieved_at_utc": meta_time, "headers": meta_headers, "bytes": len(meta_body), "sha256": sha(meta_body)},
        ],
        "member_count": len(members),
        "total_edi_bytes": sum(int(item["bytes"]) for item in members),
        "member_merkle_root": merkle(members),
        "members": members,
    }
    atomic_json(RAW / "raw-manifest.json", manifest)
    atomic_json(
        EVIDENCE / "mt-usarray-raw-freeze.json",
        {
            "schema_version": "wp8-mt-usarray-raw-freeze-v1",
            "raw_root": str(RAW.relative_to(ROOT)).replace("\\", "/"),
            "manifest_sha256": sha((RAW / "raw-manifest.json").read_bytes()),
            "member_count": len(members),
            "total_edi_bytes": manifest["total_edi_bytes"],
            "member_merkle_root": manifest["member_merkle_root"],
            "calibration_and_test_values_interpreted": False,
        },
    )
    for path in EDI.glob("*.edi"):
        os.chmod(path, stat.S_IREAD)
    print(json.dumps({"members": len(members), "bytes": manifest["total_edi_bytes"], "counts": split["counts"]}))


if __name__ == "__main__":
    main()
