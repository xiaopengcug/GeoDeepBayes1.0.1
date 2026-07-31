#!/usr/bin/env python
"""Audit full EMTF covariance using training XML only."""
from __future__ import annotations

import hashlib
import json
import stat
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from geodeepbayes.data.mt_xml import MTXMLAdapter, _matrix

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usarray-ta-emtf-v1"
MANIFEST = RAW / "xml-raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/mt-xml-covariance-readiness.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != "wp8-usarray-ta-xml-raw-manifest-v1"
        or manifest.get("member_count") != 1104
        or manifest.get("sealed_payloads_interpreted") is not False
    ):
        raise RuntimeError("incomplete or invalid EMTF XML raw manifest")
    roles = {"train": 0, "buffer": 0, "calibration": 0, "test": 0}
    train_members = []
    for member in manifest["members"]:
        path = RAW / member["path"]
        if not path.is_file() or sha(path) != member["sha256"]:
            raise RuntimeError(f"EMTF XML integrity drift: {member['spud_id']}")
        if path.stat().st_mode & stat.S_IWRITE:
            raise RuntimeError(f"EMTF XML member is writable: {member['spud_id']}")
        if member.get("payload_interpreted") is not False:
            raise RuntimeError(f"acquisition interpreted XML payload: {member['spud_id']}")
        roles[member["split"]] += 1
        if member["split"] == "train":
            train_members.append(member)

    periods = 0
    covariance_periods = 0
    variance_identity_max_relative_error = 0.0
    for member in train_members:
        # This is the only XML payload interpretation in this audit.
        root = ET.parse(RAW / member["path"]).getroot()
        for period in root.iter("Period"):
            z_variance_element = period.find("Z.VAR")
            if z_variance_element is None:
                raise RuntimeError(f"Z.VAR missing: {member['spud_id']}")
            z_variance = np.asarray(
                [float(value.text) for value in z_variance_element.findall("value")]
            ).reshape(2, 2)
            inverse_signal = _matrix(period, "Z.INVSIGCOV", ("Hx", "Hy"))
            residual = _matrix(period, "Z.RESIDCOV", ("Ex", "Ey"))
            if not np.allclose(inverse_signal, inverse_signal.T.conj(), rtol=1e-5):
                raise RuntimeError(f"non-Hermitian inverse signal covariance: {member['spud_id']}")
            if not np.allclose(residual, residual.T.conj(), rtol=1e-5):
                raise RuntimeError(f"non-Hermitian residual covariance: {member['spud_id']}")
            reconstructed = np.outer(
                np.diag(residual).real, np.diag(inverse_signal).real
            )
            relative = np.max(
                np.abs(reconstructed - z_variance)
                / np.maximum(np.abs(z_variance), np.finfo(float).tiny)
            )
            variance_identity_max_relative_error = max(
                variance_identity_max_relative_error, float(relative)
            )
            periods += 1
            covariance_periods += 1

    # Exercise the public ObservationSet contract on a deterministic training
    # member.  Dense corpus-wide covariance is deliberately not constructed.
    representative = RAW / train_members[0]["path"]
    observation = MTXMLAdapter([representative]).load()
    covariance = observation.covariance
    off_diagonal_count = int(
        np.count_nonzero(
            np.abs(covariance - np.diag(np.diag(covariance))) > 0
        )
    )
    if off_diagonal_count == 0:
        raise RuntimeError("EMTF full covariance collapsed to diagonal")
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(covariance)))
    passed = (
        len(train_members) == roles["train"]
        and periods > 0
        and covariance_periods == periods
        and variance_identity_max_relative_error < 1e-4
        and minimum_eigenvalue > -1e-12
    )
    evidence = {
        "schema_version": "wp8-mt-xml-covariance-readiness-v1",
        "passed": passed,
        "raw_member_count": manifest["member_count"],
        "xml_manifest_sha256": sha(MANIFEST),
        "role_counts": roles,
        "training_members_interpreted": len(train_members),
        "buffer_members_interpreted": 0,
        "calibration_members_interpreted": 0,
        "test_members_interpreted": 0,
        "training_periods_checked": periods,
        "covariance_periods_checked": covariance_periods,
        "covariance_contract": (
            "Cov(Z_ij,Z_kl)=RESIDCOV(E_i,E_k)*INVSIGCOV(H_j,H_l), "
            "mapped jointly to real_then_imag; cross-period and cross-station terms unavailable"
        ),
        "variance_identity_max_relative_error": variance_identity_max_relative_error,
        "representative_training_member": train_members[0]["spud_id"],
        "representative_real_stack_off_diagonal_count": off_diagonal_count,
        "representative_minimum_covariance_eigenvalue": minimum_eigenvalue,
        "adapter_source": "src/geodeepbayes/data/mt_xml.py",
        "adapter_source_sha256": sha(ROOT / "src/geodeepbayes/data/mt_xml.py"),
        "sealed_payload_values_read": False,
    }
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "roles": roles, "periods": periods}))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
