"""Generate WP8-1 synthetic substitutes and a machine-readable manifest."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np

from geodeepbayes.validation.synthetic_supplement import (
    SUPPORTED_METHODS,
    make_synthetic_supplement,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation" / "wp8" / "synthetic" / "supplements-v1"


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    members = []
    for index, method in enumerate(SUPPORTED_METHODS):
        cohort = make_synthetic_supplement(method, seed=8101 + index)
        path = OUTPUT / f"{method}.npz"
        np.savez_compressed(
            path,
            method=np.array(cohort.method),
            provenance=np.array(cohort.provenance),
            field_validation_eligible=np.array(cohort.field_validation_eligible),
            seed=np.array(cohort.seed),
            cluster_id=cohort.cluster_id,
            role=cohort.role,
            frequencies_hz=cohort.frequencies_hz,
            receiver_xyz_m=cohort.receiver_xyz_m,
            source_vertices_xyz_m=cohort.source_vertices_xyz_m,
            source_current_a=cohort.source_current_a,
            response_real=cohort.response.real,
            response_imag=cohort.response.imag,
            standard_error=cohort.standard_error,
        )
        members.append(
            {
                "method": method,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": file_sha256(path),
                "content_digest": cohort.digest(),
                "clusters": cohort.cluster_count,
                "test_clusters": cohort.test_cluster_count,
                "frequencies": int(cohort.frequencies_hz.size),
                "provenance": cohort.provenance,
                "field_validation_eligible": cohort.field_validation_eligible,
            }
        )
    manifest = {
        "schema_version": "wp8-synthetic-supplements-v1",
        "purpose": "development-and-synthetic-validation-only",
        "closes_formal_field_gaps": False,
        "members": members,
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
