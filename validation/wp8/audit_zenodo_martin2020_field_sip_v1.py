"""Response-permitted audit of the permanently training-only Martin et al. SIP data."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = (
    ROOT
    / "validation/wp8/data/zenodo-martin2020-field-sip-4419736/"
    "FD-TD-IPdata-Martin2020JAG.zip"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "zenodo-martin2020-field-sip-training-audit-v1.json"
)

PROFILES = {
    "IP1": {
        "spacing_m": 1.0,
        "scheme": "IP1/SIP256C/IP1_SIP256C.shm",
        "rhoa": "IP1/SIP256C/IP1_SIP256C.rhoa",
        "phia": "IP1/SIP256C/IP1_SIP256C.phia",
    },
    "IP5": {
        "spacing_m": 5.0,
        "scheme": "IP5/SIP256C/IP5_SIP256C.shm",
        "rhoa": "IP5/SIP256C/IP5_SIP256C.rhoa",
        "phia": "IP5/SIP256C/IP5_SIP256C.phia",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_scheme(text: str) -> dict:
    lines = text.splitlines()
    sensor_count = int(lines[0])
    coordinates = [
        tuple(float(value) for value in lines[index].split())
        for index in range(2, 2 + sensor_count)
    ]
    quadrupole_count = int(lines[sensor_count + 2])
    quadrupoles = [
        tuple(int(value) for value in lines[index].split())
        for index in range(
            sensor_count + 4, sensor_count + 4 + quadrupole_count
        )
    ]
    ab_pairs = {(row[0], row[1]) for row in quadrupoles}
    ab_midpoints = {
        (coordinates[a - 1][0] + coordinates[b - 1][0]) / 2
        for a, b in ab_pairs
    }
    quadrupole_midpoints = {
        sum(coordinates[index - 1][0] for index in row) / 4
        for row in quadrupoles
    }
    return {
        "electrode_count": sensor_count,
        "quadrupole_count": quadrupole_count,
        "unique_current_dipoles": len(ab_pairs),
        "unique_current_dipole_midpoints": len(ab_midpoints),
        "unique_quadrupole_midpoints": len(quadrupole_midpoints),
        "minimum_x_m": min(row[0] for row in coordinates),
        "maximum_x_m": max(row[0] for row in coordinates),
    }


def matrix_shape(text: str) -> tuple[int, int]:
    rows = [line.split() for line in text.splitlines() if line.strip()]
    return len(rows) - 1, len(rows[0])


def main() -> None:
    if not ARCHIVE.is_file():
        raise FileNotFoundError(ARCHIVE)
    profiles = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for profile, contract in PROFILES.items():
            scheme = parse_scheme(archive.read(contract["scheme"]).decode("utf-8"))
            rhoa_rows, rhoa_frequencies = matrix_shape(
                archive.read(contract["rhoa"]).decode("utf-8")
            )
            phia_rows, phia_frequencies = matrix_shape(
                archive.read(contract["phia"]).decode("utf-8")
            )
            if rhoa_rows != scheme["quadrupole_count"]:
                raise RuntimeError(f"{profile} rhoa rows do not match geometry")
            if (phia_rows, phia_frequencies) != (rhoa_rows, rhoa_frequencies):
                raise RuntimeError(f"{profile} phase matrix does not match rhoa")
            profiles[profile] = {
                "electrode_spacing_m": contract["spacing_m"],
                **scheme,
                "frequency_count": rhoa_frequencies,
                "complex_observation_count": rhoa_rows * rhoa_frequencies,
            }

    payload = {
        "schema_version": "wp8-zenodo-martin2020-field-sip-training-audit-v1",
        "source": {
            "record_id": 4419736,
            "doi": "10.5281/zenodo.4419736",
            "license": "CC-BY-4.0",
            "archive_path": ARCHIVE.relative_to(ROOT).as_posix(),
            "archive_bytes": ARCHIVE.stat().st_size,
            "archive_sha256": sha256(ARCHIVE),
        },
        "partition": "permanently-training-only",
        "profiles": profiles,
        "totals": {
            "field_profiles": len(profiles),
            "electrodes": sum(row["electrode_count"] for row in profiles.values()),
            "quadrupoles": sum(
                row["quadrupole_count"] for row in profiles.values()
            ),
            "unique_current_dipoles": sum(
                row["unique_current_dipoles"] for row in profiles.values()
            ),
            "unique_quadrupole_midpoints_upper_bound": sum(
                row["unique_quadrupole_midpoints"] for row in profiles.values()
            ),
            "complex_observations": sum(
                row["complex_observation_count"] for row in profiles.values()
            ),
        },
        "formal_gate_assessment": {
            "observation_contract_support": True,
            "minimum_independent_test_clusters": 223,
            "independent_profile_upper_bound": 2,
            "independent_quadrupole_midpoint_upper_bound": sum(
                row["unique_quadrupole_midpoints"] for row in profiles.values()
            ),
            "cluster_gate_passes": False,
            "power_gate_passes": False,
            "reason": (
                "The archive materially strengthens training and parser evidence, "
                "but contains two colocated field profiles. Even the deliberately "
                "non-independent quadrupole-midpoint upper bound is below 223, and "
                "two profiles cannot support leave-one-profile-out effect-size "
                "estimation."
            ),
        },
        "formal_test_responses_opened": 0,
        "test_unseal_count": 0,
        "formal_test_result": None,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["totals"], indent=2))


if __name__ == "__main__":
    main()
