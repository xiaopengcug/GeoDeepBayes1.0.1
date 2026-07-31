"""Freeze a response-blind training/test discovery split for BC ARIS IP files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = (
    ROOT
    / "validation"
    / "wp8"
    / "evidence"
    / "feasibility-v1"
    / "bc-aris-ip-digital-catalogue-v1.json"
)
OUTPUT = (
    ROOT
    / "validation"
    / "wp8"
    / "evidence"
    / "feasibility-v1"
    / "bc-aris-ip-discovery-split-v1.json"
)
SALT = "wp8-bc-aris-ip-discovery-v1"
TRAINING_REPORTS = 30


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rank(report_number: str) -> str:
    return hashlib.sha256(f"{SALT}:{report_number}".encode("ascii")).hexdigest()


def main() -> int:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    if catalogue["query"]["response_payloads_opened"] is not False:
        raise RuntimeError("catalogue is not response blind")
    records = sorted(catalogue["records"], key=lambda row: rank(row["report_number"]))
    assignments = []
    for index, record in enumerate(records):
        role = "training-discovery" if index < TRAINING_REPORTS else "sealed-candidate-test"
        assignments.append(
            {
                "report_number": record["report_number"],
                "rank_sha256": rank(record["report_number"]),
                "role": role,
                "property_name": record["property_name"],
                "catalogue_location_dms": record["catalogue_location_dms"],
                "detail_url": record["detail_url"],
                "pdf_urls": record["pdf_urls"],
                "archives": record["archives"],
                "response_opened": False,
                "archive_members_listed": False,
            }
        )
    role_counts = {
        role: sum(row["role"] == role for row in assignments)
        for role in ("training-discovery", "sealed-candidate-test")
    }
    payload = {
        "schema_version": "wp8-bc-aris-ip-discovery-split-v1",
        "catalogue_path": str(CATALOGUE.relative_to(ROOT)).replace("\\", "/"),
        "catalogue_sha256": sha256_file(CATALOGUE),
        "ranking": {
            "algorithm": "sha256",
            "salt": SALT,
            "key": "report_number",
            "training_prefix_count": TRAINING_REPORTS,
        },
        "role_counts": role_counts,
        "formal_status": {
            "this_is_not_yet_a_formal_test_design": True,
            "reason": (
                "Catalogue metadata does not classify TDIP versus FDIP/SIP or "
                "publish independent line counts. Only training-discovery files "
                "may be opened until those contracts are measured."
            ),
            "sealed_candidate_test_responses_opened": 0,
            "formal_clusters_added": 0,
            "formal_gate_changed": False,
        },
        "assignments": assignments,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(role_counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
