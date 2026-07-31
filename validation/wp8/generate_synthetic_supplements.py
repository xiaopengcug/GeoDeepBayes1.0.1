"""Generate WP8-1 synthetic substitutes and a machine-readable manifest."""
from __future__ import annotations

import json
import io
from hashlib import sha256
from pathlib import Path
import zipfile

import numpy as np

from geodeepbayes.validation.synthetic_supplement import (
    SUPPORTED_METHODS,
    make_synthetic_supplement,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation" / "wp8" / "synthetic" / "supplements-v1"


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def deterministic_savez(path: Path, **arrays: np.ndarray) -> None:
    """Write a cross-platform NPZ with stable bytes and no zlib dependency."""
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            payload = io.BytesIO()
            np.lib.format.write_array(
                payload, np.asanyarray(arrays[name]), allow_pickle=False
            )
            member = zipfile.ZipInfo(
                filename=f"{name}.npy",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            member.compress_type = zipfile.ZIP_STORED
            member.create_system = 3
            member.external_attr = 0o600 << 16
            archive.writestr(
                member,
                payload.getvalue(),
                compress_type=zipfile.ZIP_STORED,
            )


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    members = []
    for index, method in enumerate(SUPPORTED_METHODS):
        cohort = make_synthetic_supplement(method, seed=8101 + index)
        path = OUTPUT / f"{method}.npz"
        deterministic_savez(
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
    with (OUTPUT / "manifest.json").open(
        "w", encoding="utf-8", newline="\r\n"
    ) as stream:
        stream.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
