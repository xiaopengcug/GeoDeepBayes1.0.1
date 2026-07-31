#!/usr/bin/env python
"""Deduplicate and classify explicitly named NTGS IP training candidates."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/ntgs-ip-explicit-candidates-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/ntgs-ip-explicit-candidates.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def observation_members(payload: bytes, prefix: str = "") -> list[dict[str, object]]:
    result = []
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                content = archive.read(item)
                name = f"{prefix}{item.filename}"
                if item.filename.lower().endswith(".zip"):
                    result.extend(observation_members(content, f"{name}::"))
                    continue
                if not item.filename.lower().endswith((".dat", ".gdd", ".txt", ".csv")):
                    continue
                text = content[:20000].decode("latin1", errors="replace")
                result.append(
                    {
                        "path": name,
                        "bytes": len(content),
                        "sha256": sha256_bytes(content),
                        "full_decay_20": (
                            bool(re.search(r"\bIP20\b", text, re.I))
                            or bool(re.search(r"\bM20\b", text, re.I))
                            or "Windows: 20" in text
                        ),
                        "error_field": bool(
                            re.search(r"\b(?:SD|ErrVp|ErrM|IPerr|STD)\b", text, re.I)
                        ),
                        "stack_field": bool(
                            re.search(r"\b(?:Nstack|Stack)\b", text, re.I)
                        ),
                        "electrode_geometry": bool(
                            re.search(r"\b(?:C1|F1)[XY]?\b", text, re.I)
                            and re.search(r"\b(?:P1|M1)[XY]?\b", text, re.I)
                        ),
                        "acquisition_date": next(
                            iter(
                                re.findall(
                                    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text
                                )
                            ),
                            None,
                        ),
                    }
                )
    except zipfile.BadZipFile:
        pass
    return result


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    packages = []
    by_observation_hash: dict[str, list[str]] = defaultdict(list)
    for member in manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            raise RuntimeError(f"NTGS explicit candidate drift: {member['path']}")
        observations = observation_members(path.read_bytes())
        for observation in observations:
            by_observation_hash[str(observation["sha256"])].append(
                f"{member['path']}::{observation['path']}"
            )
        packages.append(
            {
                "path": member["path"],
                "handle_url": member["handle_url"],
                "observation_like_member_count": len(observations),
                "full_decay_member_count": sum(
                    bool(item["full_decay_20"]) for item in observations
                ),
                "contract_rich_member_count": sum(
                    bool(
                        item["full_decay_20"]
                        and item["error_field"]
                        and item["stack_field"]
                        and item["electrode_geometry"]
                    )
                    for item in observations
                ),
                "observations": observations,
            }
        )
    duplicate_groups = [
        paths for paths in by_observation_hash.values() if len(paths) > 1
    ]
    useful = [item for item in packages if item["contract_rich_member_count"] > 0]
    unique_useful_handles = sorted({item["handle_url"] for item in useful})
    result = {
        "schema_version": "wp8-ntgs-ip-explicit-candidates-audit-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "package_count": len(packages),
        "packages_with_contract_rich_full_decay": len(useful),
        "unique_report_handles_with_contract_rich_full_decay": len(
            unique_useful_handles
        ),
        "duplicate_observation_hash_group_count": len(duplicate_groups),
        "duplicate_observation_hash_groups": duplicate_groups,
        "packages": packages,
        "repository_access": {
            "publicly_downloadable": True,
            "explicit_reuse_license_on_item_pages": False,
            "formal_license_gate_passes": False,
        },
        "formal_independent_campaign_count": 0,
        "minimum_required_independent_clusters": 223,
        "formal_cluster_power_gate_passes": False,
        "selection_role": "training_candidates_only",
        "formal_test_endpoints_inspected": False,
        "test_unseal_count": 0,
        "conclusion": (
            "Deep attachment inspection confirms several full-decay payloads, but "
            "also byte-identical re-deposits, integrated-IP files, GPS-only files, "
            "PDF-only packages, grids and unrelated drilling surveys. Report handles "
            "are not independent campaigns. With no explicit reuse licence or frozen "
            "campaign/correlation audit, the formal contribution remains zero."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "packages": len(packages),
                "useful_packages": len(useful),
                "duplicate_groups": len(duplicate_groups),
                "formal_campaigns": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
