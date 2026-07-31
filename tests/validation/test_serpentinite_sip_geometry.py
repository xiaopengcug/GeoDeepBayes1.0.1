import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def test_serpentinite_geometry_selects_2d_and_rejects_1d_solver() -> None:
    payload = json.loads(
        (EVIDENCE / "serpentinite-sip-geometry.json").read_text(encoding="utf-8")
    )

    assert (
        payload["apparent_resistivity_chargeability_or_spectral_values_parsed"]
        is False
    )
    assert len(payload["profiles"]) == 2
    assert all(profile["electrodes"] == 64 for profile in payload["profiles"].values())
    assert all(profile["two_d_eligible"] for profile in payload["profiles"].values())
    assert payload["dimensionality"]["selected"] == "2-D profile"
    assert payload["dimensionality"]["passed"] is True
    assert payload["available_solver_compatible"] is True
    assert "ColeCole2DOperator" in payload["available_solver_limitation"]
