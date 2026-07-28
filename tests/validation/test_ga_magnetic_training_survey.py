from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-survey-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ga_training_survey_preserves_heldout_responses() -> None:
    manifest_path = DATA / "raw-manifest.json"
    design_path = EVIDENCE / "geoscience-australia-magnetic-design.json"
    audit = json.loads(
        (EVIDENCE / "geoscience-australia-magnetic-training-survey.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["design_sha256"] == sha(design_path)
    assert manifest["acquisition_interpreted_response_values"] == 0
    assert audit["raw_manifest_sha256"] == sha(manifest_path)
    assert audit["selection_policy"]["geometry_classified_before_response_access"] is True
    assert audit["selection_policy"]["response_access_used_train_only_contiguous_runs"] is True
    assert audit["response_rows_interpreted"]["train"] == 2_076_119
    assert audit["response_rows_interpreted"]["buffer"] == 0
    assert audit["response_rows_interpreted"]["calibration"] == 0
    assert audit["response_rows_interpreted"]["test"] == 0
    assert audit["geometry_rows_by_role"]["test"] == 1_141_327
    assert audit["test_unseal_count"] == 0


def test_ga_training_crossover_noise_path_is_evidenced() -> None:
    audit = json.loads(
        (EVIDENCE / "geoscience-australia-magnetic-training-survey.json").read_text(
            encoding="utf-8"
        )
    )
    crossover = audit["training_crossover_error"]
    assert crossover["bins_with_main_and_tie"] == 1479
    assert crossover["rmse_nt"] == 3.4440007268802693
    assert crossover["method_ready"] is True
    assert audit["national_correlation_ready"] is False
    assert audit["formal_contract_ready"] is False
