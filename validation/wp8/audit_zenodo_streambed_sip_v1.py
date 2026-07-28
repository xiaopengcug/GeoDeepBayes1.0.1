"""Audit the public two-site streambed SIP release without promoting it to test data."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/zenodo-streambed-sip-v1"
EVIDENCE = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "zenodo-streambed-sip-audit-v1.json"
)
RECORD_URL = "https://zenodo.org/api/records/3627361"
FILES = {
    "1Ho.zip": {
        "url": "https://zenodo.org/api/records/3627361/files/1Ho.zip/content",
        "bytes": 2_237_523,
        "md5": "1e752ea89483aecf506b45ecc41c8fd6",
    },
    "2He.zip": {
        "url": "https://zenodo.org/api/records/3627361/files/2He.zip/content",
        "bytes": 2_470_924,
        "md5": "da6f927437d592ee5046b4215a076bf2",
    },
}


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8-public-SIP-audit/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(get_bytes(RECORD_URL))
    if metadata["metadata"]["license"]["id"] != "cc-by-4.0":
        raise ValueError("Zenodo licence drift")

    sites: list[dict[str, object]] = []
    for archive_name, expected in FILES.items():
        payload = get_bytes(expected["url"])
        if len(payload) != expected["bytes"]:
            raise ValueError(f"byte-count drift for {archive_name}")
        if hashlib.md5(payload).hexdigest() != expected["md5"]:  # noqa: S324
            raise ValueError(f"checksum drift for {archive_name}")
        archive_path = DATA / archive_name
        archive_path.write_bytes(payload)

        site = archive_path.stem
        prefix = f"{site}/"
        with zipfile.ZipFile(archive_path) as archive:
            coordinate_lines = (
                archive.read(prefix + "coordinates.txt")
                .decode("utf-8-sig")
                .strip()
                .splitlines()
            )
            if coordinate_lines[0] != "locationTag;x;y;z":
                raise ValueError(f"coordinate header drift for {site}")
            recording_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith(prefix + "SIPRecordings/")
                and name.endswith(".dat")
            )
            line_ids: set[str] = set()
            frequency_codes: set[int] = set()
            abmn: set[tuple[int, int, int, int]] = set()
            response_rows = 0
            uncertainty_columns_present = True
            for name in recording_names:
                stem = Path(name).stem
                _, line_id, frequency_code = stem.split("_")
                line_ids.add(line_id)
                frequency_codes.add(int(frequency_code))
                lines = (
                    archive.read(name).decode("utf-8-sig").strip().splitlines()
                )
                uncertainty_columns_present &= (
                    lines[0].split()
                    == ["A", "B", "M", "N", "R", "Y", "I", "stdR", "stdY"]
                )
                response_rows += len(lines) - 1
                for line in lines[1:]:
                    values = line.split()
                    abmn.add(tuple(int(value) for value in values[:4]))

        sites.append(
            {
                "site": site,
                "archive_path": archive_path.relative_to(ROOT).as_posix(),
                "archive_bytes": len(payload),
                "archive_md5": hashlib.md5(payload).hexdigest(),  # noqa: S324
                "archive_sha256": hashlib.sha256(payload).hexdigest(),
                "coordinate_count": len(coordinate_lines) - 1,
                "coordinate_columns": ["locationTag", "x", "y", "z"],
                "profile_ids": sorted(line_ids),
                "profile_count": len(line_ids),
                "frequency_codes_millihz": sorted(frequency_codes),
                "frequency_range_hz": [
                    min(frequency_codes) / 1000,
                    max(frequency_codes) / 1000,
                ],
                "sip_recording_files": len(recording_names),
                "response_rows": response_rows,
                "unique_abmn_quadrupoles": len(abmn),
                "complex_response_columns": ["R", "Y"],
                "source_current_column": "I",
                "uncertainty_columns": ["stdR", "stdY"],
                "uncertainty_columns_present": uncertainty_columns_present,
            }
        )

    evidence = {
        "schema_version": "wp8-zenodo-streambed-sip-audit-v1",
        "record_id": 3627361,
        "doi": "10.5281/zenodo.3627361",
        "landing_page": "https://zenodo.org/records/3627361",
        "license": "cc-by-4.0",
        "audit_role": "diagnostic_candidate_not_formal_test",
        "formal_test_responses_opened": 0,
        "test_unseal_count": 0,
        "sites": sites,
        "totals": {
            "spatial_sites": 2,
            "profiles": sum(int(row["profile_count"]) for row in sites),
            "coordinates": sum(int(row["coordinate_count"]) for row in sites),
            "sip_recording_files": sum(
                int(row["sip_recording_files"]) for row in sites
            ),
            "response_rows": sum(int(row["response_rows"]) for row in sites),
            "unique_site_profile_clusters_upper_bound": 10,
            "independent_spatial_cluster_upper_bound": 2,
        },
        "gate_assessment": {
            "observation_contract": "strong",
            "cluster_gate_passes": False,
            "power_gate_passes": False,
            "formal_gate_change": False,
            "reason": (
                "The release provides raw frequency-keyed complex responses, "
                "ABMN geometry, current, repeat uncertainties and 3-D electrode "
                "coordinates, but only five profiles at each of two field sites. "
                "Even the non-independent profile upper bound is 10 versus 223."
            ),
        },
    }
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
