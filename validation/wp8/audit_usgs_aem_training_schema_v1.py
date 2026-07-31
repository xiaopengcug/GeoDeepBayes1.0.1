#!/usr/bin/env python
# /// script
# dependencies = ["netCDF4==1.7.2"]
# ///
"""Audit completed preregistered USGS AEM training files at schema level."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-aem-training-expansion-design-v1.json"
)
DATA = ROOT / "validation/wp8/data/usgs-aem-training-expansion-v1/files"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-aem-training-schema-audit-v1.json"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def walk(group, prefix: str = "") -> list[dict]:
    variables = []
    for name, variable in group.variables.items():
        variables.append(
            {
                "path": f"{prefix}/{name}",
                "dtype": str(variable.dtype),
                "dimensions": list(variable.dimensions),
                "shape": list(variable.shape),
                "standard_name": getattr(variable, "standard_name", None),
                "long_name": getattr(variable, "long_name", None),
                "units": getattr(variable, "units", None),
            }
        )
    for name, child in group.groups.items():
        variables.extend(walk(child, f"{prefix}/{name}"))
    return variables


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    records = []
    for survey in design["training_surveys"]:
        payload = survey["payload"]
        path = DATA / f"{survey['sciencebase_id']}__{payload['name']}"
        if not path.exists() or path.stat().st_size != payload["size"]:
            continue
        if path.suffix.lower() != ".nc":
            records.append(
                {
                    "sciencebase_id": survey["sciencebase_id"],
                    "systems": survey["systems"],
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                    "format": "non_netcdf_pending_format_audit",
                    "metadata_only": True,
                }
            )
            continue
        with Dataset(path) as dataset:
            variables = walk(dataset)
        searchable = [
            " ".join(
                str(variable.get(key) or "")
                for key in ("path", "standard_name", "long_name")
            ).lower()
            for variable in variables
        ]

        def present(*cues: str) -> bool:
            return any(
                any(cue in text for cue in cues) for text in searchable
            )

        records.append(
            {
                "sciencebase_id": survey["sciencebase_id"],
                "systems": survey["systems"],
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "format": "netcdf4",
                "variable_count": len(variables),
                "variables": variables,
                "contract": {
                    "coordinates": present(
                        "longitude", "latitude", "easting", "northing"
                    ),
                    "line_identity": present("line number", "/line"),
                    "height": present("instrument height", "altitude"),
                    "gate_times": present("gate_times", "gate times"),
                    "response": present("em_data_", "em data"),
                    "response_standard_deviation": present(
                        "em_data_std", "standard deviation"
                    ),
                    "transmitter_geometry": present(
                        "transmitter_area",
                        "loop coordinates",
                        "transmitter orientation",
                    ),
                    "waveform": present("waveform"),
                    "receiver_geometry": present(
                        "receiver_area", "receiver_orientation", "txrx_"
                    ),
                },
                "response_values_interpreted": 0,
                "metadata_only": True,
            }
        )
    output = {
        "schema_version": "wp8-usgs-aem-training-schema-audit-v1",
        "design_sha256": sha(DESIGN),
        "completed_training_file_count": len(records),
        "records": records,
        "formal_contract_ready_count": sum(
            record.get("format") == "netcdf4"
            and all(record["contract"].values())
            for record in records
        ),
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "completed_files": len(records),
                "formal_contract_ready": output[
                    "formal_contract_ready_count"
                ],
                "response_values_interpreted": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
