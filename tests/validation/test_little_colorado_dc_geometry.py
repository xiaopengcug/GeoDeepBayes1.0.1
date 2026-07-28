import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def test_little_colorado_geometry_selects_3d_without_reading_responses() -> None:
    payload = json.loads(
        (EVIDENCE / "little-colorado-dc-geometry.json").read_text(encoding="utf-8")
    )

    assert payload["resistance_or_apparent_resistivity_values_parsed"] is False
    assert set(payload["profiles"]) == {"MB2.5", "MB2.5B", "MB4", "MB4B"}
    assert payload["profiles_requiring_3d"] == ["MB4"]
    assert payload["profiles"]["MB4"]["crossline_maximum_spacing_ratio"] > 100
    assert payload["dimensionality"]["selected"] == "3-D"
    assert payload["dimensionality"]["passed"] is True
