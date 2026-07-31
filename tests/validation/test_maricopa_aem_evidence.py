import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_maricopa_contract_and_outcome_blind_split_are_frozen() -> None:
    manifest = json.loads(
        (
            ROOT / "validation/wp8/data/maricopa-aem-v1/raw-manifest.json"
        ).read_text(encoding="utf-8")
    )
    split = load("maricopa-aem-design-split.json")
    contract = load("maricopa-aem-contract-readiness.json")

    assert manifest["member_count"] == 3
    assert manifest["total_bytes"] == 711_321_496
    assert manifest["observation_response_interpreted"] is False
    assert split["design_rows"] == 24_103
    assert split["candidate_500m_cell_counts"]["test"] == 246
    assert split["observation_response_values_parsed"] is False
    assert contract["passed"] is True
    assert contract["processed_observation_rows"] == 24_103
    assert contract["low_moment"]["gate_count"] == 28
    assert contract["high_moment"]["gate_count"] == 37
    assert contract["per_observation_standard_deviation"] is True
    assert contract["observation_response_values_parsed"] is False


def test_maricopa_training_audit_keeps_held_out_responses_sealed() -> None:
    diagnostic = load("maricopa-aem-train-diagnostics.json")

    assert diagnostic["training_rows_interpreted"] == 10_446
    assert diagnostic["sealed_response_rows_interpreted"] == {
        "buffer": 0,
        "calibration": 0,
        "test": 0,
    }
    assert diagnostic["conservative_spatial_correlation_range_m"] == 8_750.0
    assert diagnostic["design_test_cells"] == 246
    assert diagnostic["correlation_adjusted_test_cluster_upper_bound"] == 1
    assert diagnostic["cluster_gate_passed"] is False
    assert diagnostic["power_gate_passed"] is False
