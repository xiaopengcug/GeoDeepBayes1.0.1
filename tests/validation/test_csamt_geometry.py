import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1/csamt-geometry.json"


def test_csamt_geometry_is_outcome_blind_and_solver_compatible():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    source = ROOT / payload["input_path"]
    assert payload["schema_version"] == "wp8-csamt-geometry-v1"
    assert payload["observation_or_inversion_values_parsed"] is False
    assert hashlib.sha256(source.read_bytes()).hexdigest() == payload["input_sha256"]
    assert payload["release_count"] == 3
    assert payload["line_count"] == 32
    assert payload["maximum_axial_line_azimuth_difference_degrees"] > 20
    assert payload["dimensionality"]["selected"] == "3-D finite-source"
    assert payload["dimensionality"]["passed"] is True
    assert payload["available_solver_compatible"] is True
    assert "CSAMTOperator" in payload["available_solver"]
    assert "does not repair" in payload["contract_boundary"]
