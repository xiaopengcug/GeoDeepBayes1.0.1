from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1/csamt-candidate-split.json"


def test_csamt_candidate_split_is_outcome_blind_and_sealed() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert payload["status"] == "candidate_assignments_frozen_training_response_not_opened"
    assert payload["observation_values_read"] is False
    assert payload["unique_station_coordinates"] == 1843
    assert payload["exact_coordinate_duplicates_across_full_consortium"] == 0
    assert sum(payload["candidate_partition_counts"].values()) == 1843
    assert payload["candidate_250m_cell_counts"]["test"] >= 223
    assert payload["calibration_responses_interpreted"] == 0
    assert payload["test_responses_interpreted"] == 0
    assert payload["test_unseal_count"] == 0
    granularity = payload["provider_raw_granularity_audit"]
    assert granularity["provider_station_lines"] == 32
    assert granularity["station_lines_mixing_candidate_partitions"] == 32
    assert granularity["safe_training_member_extraction_possible"] is False
    assert granularity["line_level_split_upper_bound"] == 32
    assert granularity["line_level_split_meets_223_test_clusters"] is False


def test_csamt_station_archives_are_hash_verified_and_read_only() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    for release in payload["releases"]:
        archive = ROOT / release["local_archive"]
        assert archive.exists()
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == release["archive_sha256"]
        assert not bool(archive.stat().st_mode & stat.S_IWRITE)
        if release["raw_archive_local"] is not None:
            raw_archive = ROOT / release["raw_archive_local"]
            assert raw_archive.exists()
            assert hashlib.sha256(raw_archive.read_bytes()).hexdigest() == release["raw_archive_sha256"]
            assert not bool(raw_archive.stat().st_mode & stat.S_IWRITE)
            assert release["raw_archive_opened_members"] == 0
