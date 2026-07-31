#!/usr/bin/env python
"""Record response-blind WFEM public-data and contract-reference conclusions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/wfem-public-contract-references-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/wfem-public-contract-references.json"


def main() -> None:
    manifest = json.loads((DATA / "raw-manifest.json").read_text(encoding="utf-8"))
    evidence = {
        "schema_version": "wp8-wfem-public-contract-references-v1",
        "selection_role": manifest["selection_role"],
        "formal_test_endpoints_inspected": False,
        "candidates": [
            {
                "id": "nedc-hunan-huangshaping-baoshan",
                "doi": "10.12080/nedc.prj_zdyf.ds00028.2021",
                "advertised_bytes": 2290000,
                "field_data": True,
                "advertised_native_files": [".avg", ".MDE", ".stn"],
                "advertised_contract": {
                    "raw_wfem_observations": True,
                    "observation_system_configuration": True,
                    "station_coordinates_and_elevations": True,
                },
                "anonymous_download": False,
                "access": "order review required",
                "provider_download_count": 0,
                "decision": "acquisition_candidate_pending_external_order_approval",
            },
            {
                "id": "wucaiwan-distributed-wfem",
                "doi": "10.3390/app16104601",
                "article_license": "CC BY 4.0",
                "field_data": True,
                "survey_lines": 19,
                "stations_per_line": 16,
                "design_station_upper_bound": 304,
                "line_spacing_m": 74,
                "station_spacing_m": 40,
                "frequency_count": 53,
                "frequency_range_hz": [1, 8192],
                "transmitter_dipole_length_m": 1000,
                "transmitter_receiver_offset_range_m": [4300, 5700],
                "raw_data_download": False,
                "access": "corresponding-author request due to commercial or technical restrictions",
                "decision": "design_and_contract_reference_only",
            },
            {
                "id": "jiangsu-hdr-fracturing-wfem",
                "doi": "10.3389/feart.2025.1579468",
                "article_license": "CC BY 4.0",
                "field_data": True,
                "transmitter_dipole_length_m": 3000,
                "receiver_dipole_length_m": 100,
                "transmitter_receiver_offset_m": 15000,
                "current_a": 130,
                "frequency_focus_hz": [0.1, 10],
                "raw_data_download": False,
                "access": "authors will make raw data available on request",
                "decision": "contract_reference_only",
            },
        ],
        "conclusions": {
            "largest_public_design_station_upper_bound": 304,
            "downloadable_response_station_count": 0,
            "qualified_formal_station_count": 0,
            "source_receiver_contract_complete_in_public_articles": True,
            "source_receiver_contract_complete_in_downloadable_field_payload": False,
            "correlation_length_frozen": False,
            "formal_power_gate": "failed",
            "dimensionality_gate": "failed",
            "reason": (
                "the 304-station design exceeds the nominal 223 count, but its "
                "response data are request-only; the NEDC native package requires "
                "order approval, so neither can be frozen, split or correlation-audited"
            ),
        },
        "buffer_values_read": 0,
        "calibration_values_read": 0,
        "test_values_read": 0,
        "test_unseal_count": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence["conclusions"]))


if __name__ == "__main__":
    main()
