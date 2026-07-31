from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/magic-contributions-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_magic_raw_archive_is_sealed_and_complete() -> None:
    manifest = json.loads((RAW / "raw-manifest.json").read_text(encoding="utf-8"))
    archive = RAW / manifest["archive"]["name"]
    assert archive.stat().st_size == manifest["archive"]["bytes"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive"]["sha256"]
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.infolist()) == 100
    assert manifest["excluded_contribution_ids"] == [20710]
    assert manifest["response_values_interpreted"] is False


def test_magic_split_is_contribution_level_and_outcome_blind() -> None:
    split = load("magic-contribution-design-split.json")
    assert split["counts"] == {
        "buffer": 10,
        "calibration": 16,
        "test": 9,
        "train": 64,
    }
    ids = [row["contribution_id"] for row in split["contributions"]]
    assert len(ids) == len(set(ids)) == 99
    assert 20710 not in ids
    assert split["contribution_overlap"] is False
    assert split["response_tables_read"] == []
    assert split["response_values_interpreted"] is False


def test_magic_prior_reads_training_measurements_only() -> None:
    split_path = EVIDENCE / "magic-contribution-design-split.json"
    prior = load("magic-training-remanence-prior.json")
    assert prior["design_split_sha256"] == hashlib.sha256(split_path.read_bytes()).hexdigest()
    assert prior["training_contributions_interpreted"] == 64
    assert prior["buffer_contributions_interpreted"] == 0
    assert prior["calibration_contributions_interpreted"] == 0
    assert prior["test_contributions_interpreted"] == 0
    assert prior["excluded_contribution_ids"] == [20710]
    assert prior["complete_vector_rows"] == 5905
    assert prior["complete_vector_contributions"] == 21
    assert prior["prior_gate_passed"] is True
    assert prior["held_out_response_values_read"] is False
    assert prior["magnitude_distributions"]["magn_volume"]["unit"] == "A/m"
    assert prior["magnitude_distributions"]["magn_mass"]["unit"] == "A m^2/kg"
    assert prior["magnitude_distributions"]["magn_moment"]["unit"] == "A m^2"


def test_validator_accepts_completed_magnetic_gate_chain() -> None:
    import importlib.util

    script = ROOT / "validation/wp8/validate_wp8.py"
    spec = importlib.util.spec_from_file_location("validate_wp8_magic", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    audit = module.audit_selected_magnetic()
    assert audit["errors"] == []
    assert audit["gates"]["observation_contract"]["status"] == "passed"
    assert audit["gates"]["clusters"]["status"] == "passed"
    assert audit["gates"]["power"]["status"] == "passed"
