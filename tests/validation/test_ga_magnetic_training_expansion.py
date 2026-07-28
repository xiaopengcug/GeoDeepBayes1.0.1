from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def test_ga_training_expansion_preserves_all_heldout_responses() -> None:
    audit = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-training-expansion.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["states"] == ["NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"]
    assert audit["products_sampled"] == 14
    assert audit["eligible_catalogue_products"] == 598
    assert audit["total_training_rows_interpreted"] == 6_233_124
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


def test_ga_training_expansion_remains_a_pilot_despite_power_capability() -> None:
    audit = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-training-expansion.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["conservative_pilot_correlation_range_m"] == 22_500.0
    assert audit["censored_member_count"] == 0
    assert audit["total_crossover_bins"] == 7210
    assert audit["pilot_geometry_response_test_clusters"] == 305
    assert audit["pilot_range_is_below_design_spacing"] is True
    assert audit["pilot_power_count_possible"] is True
    assert audit["national_correlation_ready"] is False
    assert audit["formal_contract_ready"] is False
