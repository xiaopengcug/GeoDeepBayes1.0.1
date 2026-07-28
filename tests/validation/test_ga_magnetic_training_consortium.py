from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def test_ga_training_consortium_is_leakage_safe_and_geographically_dispersed() -> None:
    audit = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-training-consortium.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["states"] == ["NSW", "NT", "SA", "TAS", "VIC", "WA"]
    assert len(audit["members"]) == 6
    assert audit["total_training_rows_interpreted"] == 650_783
    assert audit["response_rows_interpreted"] == {
        "buffer": 0,
        "calibration": 0,
        "test": 0,
    }
    assert all(
        member["heldout_response_rows_interpreted"]
        == {"buffer": 0, "calibration": 0, "test": 0}
        for member in audit["members"]
    )
    assert audit["test_unseal_count"] == 0


def test_ga_training_consortium_pilot_does_not_overclaim_national_readiness() -> None:
    audit = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-training-consortium.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["conservative_pilot_correlation_range_m"] == 17_500.0
    assert audit["censored_member_count"] == 0
    assert audit["total_crossover_bins"] == 1565
    assert audit["pilot_geometry_response_test_clusters"] == 305
    assert audit["pilot_range_is_below_design_spacing"] is True
    assert audit["pilot_power_count_possible"] is True
    assert audit["national_correlation_ready"] is False
    assert audit["formal_contract_ready"] is False
