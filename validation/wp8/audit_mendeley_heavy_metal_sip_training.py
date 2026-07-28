#!/usr/bin/env python
"""Verify and summarize the training-only Mendeley heavy-metal SIP package."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from acquire_mendeley_heavy_metal_sip import (
    ARCHIVE_NAME,
    DATA,
    DOI,
    INVENTORY_SHA256,
    LICENSE,
    MANIFEST_SCHEMA,
    PROVIDER_CONTENT_ID,
    PROVIDER_FILE_ID,
    PROVIDER_SHA256,
    PROVIDER_SIZE,
    audit_archive,
    sha256_stream,
    sha256_file,
)

MANIFEST = DATA / "raw-manifest.json"
OUTPUT = DATA / "contract-audit.json"
SITE_METADATA = (
    DATA.parents[2]
    / "evidence/feasibility-v1/mendeley-heavy-metal-sip-metadata-audit-v1.json"
)
SITE_METADATA_SHA256 = "78f234a6ef3f1d8124306188cbf3b8b73a9738e73f311bf3543950223a677dd4"
FREQUENCY = re.compile(r"^(?P<frequency>[0-9]+(?:\.[0-9]+)?)Hz$", re.IGNORECASE)


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _valid_retrieval_provenance(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    timestamp = value.get("retrieved_at_utc")
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
        and value.get("schema_version") == "wp8-retrieval-provenance-v1"
        and value.get("status") in {"downloaded_verified", "preexisting_verified"}
        and value.get("transport") == "https"
        and value.get("verification") == "provider-size-and-sha256"
    )


def build_contract_audit(
    data: Path = DATA, *, require_real_contract: bool = True
) -> dict[str, object]:
    manifest_path = data / MANIFEST.name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive_path = data / ARCHIVE_NAME
    errors: list[str] = []
    if require_real_contract and data.resolve() != DATA.resolve():
        errors.append("real_data_path")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        errors.append("manifest_schema")
    if manifest.get("scope") != "permanently-training-only":
        errors.append("scope")
    if manifest.get("field_validation_eligible") is not False:
        errors.append("field_validation_eligible")
    if manifest.get("sealed_test_accessed") is not False:
        errors.append("sealed_test_boundary")
    if manifest.get("doi") != DOI or manifest.get("license", {}).get("spdx") != LICENSE:
        errors.append("source_or_license")
    expected_archive = manifest.get("archive", {})
    source = manifest.get("source_inventory", {})
    if require_real_contract and (
        source.get("sha256") != INVENTORY_SHA256
        or source.get("mendeley_file_id") != PROVIDER_FILE_ID
        or source.get("content_id") != PROVIDER_CONTENT_ID
        or expected_archive.get("bytes") != PROVIDER_SIZE
        or expected_archive.get("sha256") != PROVIDER_SHA256
    ):
        errors.append("provider_anchor")
    if (
        not archive_path.is_file()
        or archive_path.stat().st_size != expected_archive.get("bytes")
        or sha256_file(archive_path) != expected_archive.get("sha256")
    ):
        errors.append("archive_integrity")
        return _result(
            errors, {}, [], 0, False, require_real_contract=require_real_contract
        )

    try:
        actual_audit = audit_archive(archive_path)
    except (RuntimeError, zipfile.BadZipFile) as error:
        errors.append(f"archive_safety:{error}")
        return _result(
            errors, {}, [], 0, False, require_real_contract=require_real_contract
        )
    if actual_audit != manifest.get("audit"):
        errors.append("archive_audit_drift")

    expected_members = {
        item["path"]: item for item in manifest.get("audit", {}).get("members", [])
    }
    acquisitions: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"frequencies": set(), "channels": set()}
    )
    metadata_tables: list[dict[str, object]] = []
    dat_member_count = 0
    actual_names: set[str] = set()
    top_level_names: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename.replace("\\", "/")).as_posix()
            actual_names.add(name)
            top_level_names.add(PurePosixPath(name).parts[0])
            expected = expected_members.get(name)
            if expected is None:
                errors.append(f"unregistered_member:{name}")
                continue
            is_metadata = name.lower().endswith(".xls")
            with archive.open(info) as stream:
                if is_metadata:
                    body = stream.read()
                    actual_digest, actual_size = _digest(body), len(body)
                else:
                    body = b""
                    actual_digest, actual_size = sha256_stream(stream)
            if actual_size != expected.get("bytes") or actual_digest != expected.get("sha256"):
                errors.append(f"member_integrity:{name}")
                continue
            parts = PurePosixPath(name).parts
            if name.lower().endswith(".dat"):
                dat_member_count += 1
                if len(parts) < 4:
                    errors.append(f"dat_layout:{name}")
                    continue
                match = FREQUENCY.match(parts[-3])
                if match is None:
                    errors.append(f"frequency_layout:{name}")
                    continue
                acquisition = parts[-4]
                acquisitions[acquisition]["frequencies"].add(match.group("frequency"))
                acquisitions[acquisition]["channels"].add(PurePosixPath(name).stem)
            elif name.lower().endswith(".xls"):
                try:
                    text = body.decode("gb18030")
                except UnicodeDecodeError:
                    errors.append(f"metadata_encoding:{name}")
                    continue
                rows = [row for row in text.splitlines() if row.strip()]
                metadata_tables.append(
                    {
                        "path": name,
                        "encoding": "gb18030",
                        "nonempty_row_count": len(rows),
                        "maximum_tab_column_count": max(
                            (len(row.split("\t")) for row in rows), default=0
                        ),
                        "content_sha256": _digest(body),
                    }
                )
    missing = sorted(set(expected_members) - actual_names)
    errors.extend(f"missing_member:{name}" for name in missing)
    acquisition_summary = {
        key: {
            "frequency_count": len(value["frequencies"]),
            "frequencies_hz": sorted(float(item) for item in value["frequencies"]),
            "channel_count": len(value["channels"]),
        }
        for key, value in sorted(acquisitions.items())
    }
    real_shape = (
        actual_audit.get("member_count") == 84
        and actual_audit.get("extensions") == {".dat": 81, ".xls": 3}
        and dat_member_count == 81
        and len(metadata_tables) == 3
        and len(acquisition_summary) == 3
        and all(
            item["frequency_count"] == 3 and item["channel_count"] == 9
            for item in acquisition_summary.values()
        )
    )
    if require_real_contract and not real_shape:
        errors.append("real_structure_contract")
    if not _valid_retrieval_provenance(manifest.get("retrieval_provenance")):
        errors.append("retrieval_provenance")
    site_identity = {
        "basis": "unique-top-level-archive-identity-plus-single-site-provider-metadata",
        "top_level_names": sorted(top_level_names),
        "provider_declared_site_count": 1,
        "metadata_evidence_path": SITE_METADATA.relative_to(DATA.parents[2]).as_posix(),
        "metadata_evidence_sha256": SITE_METADATA_SHA256,
    }
    if require_real_contract:
        metadata = json.loads(SITE_METADATA.read_text(encoding="utf-8"))
        if (
            len(top_level_names) != 1
            or sha256_file(SITE_METADATA) != SITE_METADATA_SHA256
            or metadata.get("doi") != DOI
            or metadata.get("site_count") != 1
        ):
            errors.append("site_identity")
    return _result(
        errors, acquisition_summary, metadata_tables, dat_member_count,
        not errors and (real_shape or not require_real_contract),
        require_real_contract=require_real_contract,
        site_identity_evidence=site_identity,
    )


def _result(
    errors: list[str],
    acquisitions: dict[str, object],
    metadata_tables: list[dict[str, object]],
    dat_member_count: int,
    archive_contract_integrity_passed: bool,
    *,
    require_real_contract: bool = True,
    site_identity_evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "wp8-mendeley-heavy-metal-sip-training-contract-audit-v1",
        "scope": "permanently-training-only",
        "doi": DOI,
        "license": LICENSE,
        "provider_inventory_sha256": INVENTORY_SHA256,
        "audit_mode": (
            "real-provider-contract" if require_real_contract else "test-structure-only"
        ),
        "sealed_test_accessed": False if require_real_contract else "not_assessed",
        "response_selection_evidence": "not_assessed_by_structure_only_audit",
        "archive_contract_integrity_passed": archive_contract_integrity_passed,
        "acquisition_group_count": len(acquisitions),
        "acquisitions": acquisitions,
        "dat_member_count": dat_member_count,
        "metadata_table_count": len(metadata_tables),
        "metadata_tables": metadata_tables,
        "site_identity_evidence": site_identity_evidence or {},
        "site_count": 1 if require_real_contract else "not_assessed",
        "independent_cluster_upper_bound": 1 if require_real_contract else "not_assessed",
        "cluster_unit": "field_site",
        "frequency_channel_and_repeat_are_within_cluster": True,
        "formal_field_gate_passes": False,
        "field_validation_eligible": False,
        "formal_status": "blocked",
        "decision": "permanently_training_only_contract_audited_formal_gate_blocked",
        "errors": sorted(errors),
        "structure_audit_passed": not errors,
    }


def write_immutable_result(path: Path, result: dict[str, object]) -> None:
    if (
        result.get("audit_mode") != "real-provider-contract"
        or result.get("sealed_test_accessed") is not False
    ):
        raise RuntimeError("test-structure audit cannot be written as a formal artifact")
    encoded = (
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    if path.exists():
        original = path.read_bytes()
        if original != encoded:
            raise RuntimeError("immutable Mendeley training contract audit drift")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)
    os.chmod(path, stat.S_IREAD)


def main() -> None:
    result = build_contract_audit()
    if not result["structure_audit_passed"]:
        raise SystemExit(json.dumps(result, ensure_ascii=False))
    write_immutable_result(OUTPUT, result)
    print(
        json.dumps(
            {
                "structure_audit_passed": result["structure_audit_passed"],
                "acquisition_groups": result["acquisition_group_count"],
                "dat_members": result["dat_member_count"],
                "independent_cluster_upper_bound": result["independent_cluster_upper_bound"],
                "formal_field_gate_passes": result["formal_field_gate_passes"],
            }
        )
    )


if __name__ == "__main__":
    main()
