#!/usr/bin/env python
"""Acquire and audit the Mendeley heavy-metal SIP v2 training-only archive."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[2]
SOURCE_INVENTORY = ROOT / "validation/wp8/data/heavy-metal-sip-mendeley-root-files-v2.json"
DATA = ROOT / "validation/wp8/data/mendeley-heavy-metal-sip-v2/training-only"
ARCHIVE_NAME = "2021_4_06_field_trial_paper_data.zip"
DOI = "10.17632/zz9t2wrvyw.2"
LICENSE = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
DATASET_URL = "https://data.mendeley.com/datasets/zz9t2wrvyw/2"
USER_AGENT = "GeoDeepBayes-WP8-training-audit/1.0"
MANIFEST_SCHEMA = "wp8-mendeley-heavy-metal-sip-permanently-training-manifest-v2"
INVENTORY_SHA256 = "58316f9a2862b22da616463e73f1c37ff5fae99503ec1d8164b6a554d22c2041"
PROVIDER_FILE_ID = "702ffca0-b2c7-4104-8716-e90c763c1172"
PROVIDER_CONTENT_ID = "e98cfb15-97c4-4124-8258-596f4ac73058"
PROVIDER_SIZE = 185002317
PROVIDER_SHA256 = "b4f2eb8187e27f4c58f4e991a5c59d8af5e73f4bd7f5950935d974b8508cd6a4"
MAX_MEMBER_BYTES = 2 * 1024**3
MAX_EXPANDED_BYTES = 8 * 1024**3


def sha256_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(block)
        digest.update(block)
    return digest.hexdigest(), size


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256_stream(stream)[0]


def resolve_source(inventory_path: Path = SOURCE_INVENTORY) -> dict[str, object]:
    if sha256_file(inventory_path) != INVENTORY_SHA256:
        raise RuntimeError("Mendeley v2 provider inventory anchor drift")
    records = json.loads(inventory_path.read_text(encoding="utf-8"))
    matches = [record for record in records if record.get("filename") == ARCHIVE_NAME]
    if len(matches) != 1:
        raise RuntimeError("Mendeley v2 archive is not uniquely resolved")
    record = matches[0]
    details = record.get("content_details", {})
    required = ("download_url", "sha256_hash", "size")
    if any(not details.get(field) for field in required):
        raise RuntimeError("Mendeley v2 source inventory is incomplete")
    if int(details["size"]) != int(record.get("size", -1)):
        raise RuntimeError("Mendeley v2 source inventory has inconsistent sizes")
    if (
        record.get("id") != PROVIDER_FILE_ID
        or details.get("id") != PROVIDER_CONTENT_ID
        or int(details["size"]) != PROVIDER_SIZE
        or details.get("sha256_hash") != PROVIDER_SHA256
    ):
        raise RuntimeError("Mendeley v2 provider source anchor drift")
    return record


def download_verified(url: str, target: Path, expected_size: int, expected_sha256: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        if target.stat().st_size != expected_size or sha256_file(target) != expected_sha256:
            raise RuntimeError("existing Mendeley archive does not match the frozen source")
        return "preexisting_verified"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{target.name}.", suffix=".part", dir=target.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(request, timeout=300) as response:
                digest, size = _copy_and_hash(response, output)
        if size != expected_size or digest != expected_sha256:
            raise RuntimeError("downloaded Mendeley archive does not match the frozen source")
        if target.exists():
            if target.stat().st_size != expected_size or sha256_file(target) != expected_sha256:
                raise RuntimeError("concurrent Mendeley archive does not match the frozen source")
            temporary.unlink()
        else:
            os.replace(temporary, target)
        temporary = None
        return datetime.now(timezone.utc).isoformat()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _copy_and_hash(source: BinaryIO, destination: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: source.read(1024 * 1024), b""):
        size += len(block)
        digest.update(block)
        destination.write(block)
    return digest.hexdigest(), size


def _safe_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or (path.parts and ":" in path.parts[0])
    ):
        raise RuntimeError(f"unsafe ZIP member path: {name!r}")
    return path.as_posix()


def audit_archive(path: Path) -> dict[str, object]:
    members: list[dict[str, object]] = []
    names: set[str] = set()
    expanded = 0
    extensions: Counter[str] = Counter()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = _safe_member_name(info.filename)
            if name in names:
                raise RuntimeError(f"duplicate ZIP member: {name}")
            names.add(name)
            if info.flag_bits & 0x1:
                raise RuntimeError(f"encrypted ZIP member: {name}")
            unix_mode = info.external_attr >> 16
            if stat.S_ISLNK(unix_mode):
                raise RuntimeError(f"symbolic-link ZIP member: {name}")
            if info.is_dir():
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                raise RuntimeError(f"ZIP member exceeds audit budget: {name}")
            expanded += info.file_size
            if expanded > MAX_EXPANDED_BYTES:
                raise RuntimeError("ZIP expanded-size budget exceeded")
            with archive.open(info, "r") as stream:
                digest, actual_size = sha256_stream(stream)
            if actual_size != info.file_size:
                raise RuntimeError(f"ZIP member size drift: {name}")
            suffix = PurePosixPath(name).suffix.lower() or "<none>"
            extensions[suffix] += 1
            members.append(
                {
                    "path": name,
                    "bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    "sha256": digest,
                    "extension": suffix,
                }
            )
    return {
        "member_count": len(members),
        "expanded_bytes": expanded,
        "extensions": dict(sorted(extensions.items())),
        "members": members,
    }


def build_manifest(
    source: dict[str, object], archive: Path, audit: dict[str, object],
    *, retrieval_status: str, retrieved_at_utc: str,
) -> dict[str, object]:
    try:
        retrieved_at = datetime.fromisoformat(retrieved_at_utc.replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError("retrieval timestamp must be UTC ISO-8601") from error
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() != timezone.utc.utcoffset(retrieved_at):
        raise RuntimeError("retrieval timestamp must be UTC ISO-8601")
    if retrieval_status not in {"downloaded_verified", "preexisting_verified"}:
        raise RuntimeError("unsupported retrieval status")
    details = source["content_details"]
    return {
        "schema_version": MANIFEST_SCHEMA,
        "scope": "permanently-training-only",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "doi": DOI,
        "dataset_url": DATASET_URL,
        "title": "Survey of a heavy metal polluted field site based on spectrum-induced polarization",
        "license": {
            "spdx": LICENSE,
            "url": LICENSE_URL,
            "attribution_required": True,
            "modification_notice_required": True,
        },
        "source_inventory": {
            "path": SOURCE_INVENTORY.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(SOURCE_INVENTORY),
            "mendeley_file_id": source["id"],
            "content_id": details["id"],
            "download_url": details["download_url"],
            "provider_created_date": details["created_date"],
        },
        "archive": {
            "path": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
            "content_type": details["content_type"],
        },
        "audit": audit,
        "retrieval_provenance": {
            "schema_version": "wp8-retrieval-provenance-v1",
            "status": retrieval_status,
            "retrieved_at_utc": retrieved_at_utc,
            "transport": "https",
            "verification": "provider-size-and-sha256",
        },
    }


def write_immutable_manifest(path: Path, manifest: dict[str, object]) -> None:
    encoded = (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    if path.exists():
        original = path.read_bytes()
        if original != encoded:
            raise RuntimeError("immutable Mendeley training manifest drift")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def validate_inherited_provenance(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError("existing retrieval provenance is missing")
    required = {
        "schema_version": "wp8-retrieval-provenance-v1",
        "transport": "https",
        "verification": "provider-size-and-sha256",
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        raise RuntimeError("existing retrieval provenance drift")
    timestamp = value.get("retrieved_at_utc")
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError("existing retrieval provenance timestamp drift") from error
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
        or value.get("status") not in {"downloaded_verified", "preexisting_verified"}
    ):
        raise RuntimeError("existing retrieval provenance drift")
    return value


def main() -> None:
    source = resolve_source()
    details = source["content_details"]
    archive = DATA / ARCHIVE_NAME
    retrieved = download_verified(
        str(details["download_url"]),
        archive,
        int(details["size"]),
        str(details["sha256_hash"]),
    )
    audit = audit_archive(archive)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    manifest = build_manifest(
        source, archive, audit,
        retrieval_status=(
            "downloaded_verified" if retrieved != "preexisting_verified" else retrieved
        ),
        retrieved_at_utc=retrieved_at,
    )
    output = DATA / "raw-manifest.json"
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        # A verified pre-existing archive retains the original stable retrieval event.
        manifest["retrieval_provenance"] = validate_inherited_provenance(
            existing.get("retrieval_provenance")
        )
    write_immutable_manifest(output, manifest)
    for item in (archive, output):
        os.chmod(item, stat.S_IREAD)
    print(
        json.dumps(
            {
                "doi": DOI,
                "archive_sha256": manifest["archive"]["sha256"],
                "member_count": audit["member_count"],
                "expanded_bytes": audit["expanded_bytes"],
                "scope": "permanently-training-only",
            }
        )
    )


if __name__ == "__main__":
    main()
