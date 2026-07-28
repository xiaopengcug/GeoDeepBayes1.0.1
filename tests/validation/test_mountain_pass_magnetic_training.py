import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def test_mountain_pass_training_diagnostics_keep_held_out_response_sealed() -> None:
    payload = json.loads(
        (EVIDENCE / "mountain-pass-magnetic-train-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["training_rows_interpreted"] == 23_661
    assert payload["sealed_response_rows_interpreted"] == {
        "buffer": 0,
        "calibration": 0,
        "test": 0,
    }
    assert payload["training_cells_1km"] == 113
    assert payload["conservative_spatial_correlation_range_m"] == 1_500.0
    assert payload["design_test_cells"] == 43
    assert payload["correlation_adjusted_test_cluster_upper_bound"] == 15
    assert payload["flight_line_spectrum"]["eligible_training_lines"] == 124
    assert payload["flight_line_spectrum"]["passed"] is True
    assert payload["remanence_sensitivity"]["complete_untreated_vectors"] == 5_905
    assert payload["remanence_sensitivity"]["passed"] is True
    assert payload["dimensionality"] == {
        "selected": "3-D vector magnetization",
        "passed": True,
        "reason": (
            "training residual correlation exceeds the 1-km sounding cell, "
            "multiple flight orientations are present, and the provenance-backed "
            "remanence prior requires vector magnetization sensitivity"
        ),
    }
