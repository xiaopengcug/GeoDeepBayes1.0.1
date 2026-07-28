#!/usr/bin/env python
"""Audit GA VTEM/SkyTEM archive schemas without opening observation payloads."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/geoscience-australia-aem-multisystem-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
SELECTION = EVIDENCE / "geoscience-australia-aem-multisystem-training-sample.json"
INVENTORY = EVIDENCE / "geoscience-australia-aem-multisystem-inventory.json"
CONTRACT = EVIDENCE / "geoscience-australia-aem-multisystem-contract.json"
SCHEMA_SUFFIXES = (".des", ".dfn", ".ehf", ".prj")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def has(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE | re.MULTILINE) for pattern in patterns)


def main() -> None:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    by_record = {choice["record_id"]: choice for choice in selection["choices"]}
    archives = []
    contracts = []
    schema_bytes_read = 0

    for archive in sorted(RAW.glob("*.zip")):
        record_id = int(archive.name.split("-", 1)[0])
        choice = by_record[record_id]
        members = []
        schema_text = []
        schema_names = []
        with zipfile.ZipFile(archive) as source:
            for item in source.infolist():
                suffix = Path(item.filename).suffix.lower()
                members.append(
                    {
                        "name": item.filename,
                        "uncompressed_bytes": item.file_size,
                        "compressed_bytes": item.compress_size,
                        "crc32": f"{item.CRC:08x}",
                        "schema_member_read": suffix in SCHEMA_SUFFIXES,
                        "observation_payload_read": False,
                    }
                )
                if suffix in SCHEMA_SUFFIXES:
                    payload = source.read(item.filename)
                    schema_bytes_read += len(payload)
                    schema_names.append(item.filename)
                    schema_text.append(payload.decode("latin1", errors="replace"))

        text = "\n".join(schema_text)
        if choice["system"] == "SkyTEM":
            facts = {
                "system": "SkyTEM",
                "transmitter_specification_present": has(text, r"TRANSMITTER SPECIFICATIONS"),
                "lm_hm_current_present": has(text, r"LM\s*=\s*5\.9\s*A", r"HM\s*=\s*117\s*A"),
                "exact_lm_hm_waveforms_present": has(text, r"LM Tx WAVEFORM", r"HM Tx Waveform"),
                "exact_gate_open_center_close_present": has(
                    text, r"LM GATE TIMES SUPPLIED", r"HM GATE TIMES SUPPLIED",
                    r"Gate Open\s+Gate Centre\s+Gate Close",
                ),
                "receiver_specification_present": has(text, r"RECEIVER SPECIFICATIONS"),
                "coordinates_present": has(text, r"Longitude", r"Latitude"),
                "response_components": ["LM_Z", "HM_Z", "LM_X", "HM_X"],
                "response_fields_present": has(text, r"LM_Z", r"HM_Z", r"LM_X", r"HM_X"),
                "per_observation_relative_uncertainty_fields": [
                    "RUNC_LM_Z", "RUNC_HM_Z", "RUNC_LM_X", "RUNC_HM_X"
                ],
                "per_observation_uncertainty_present": has(
                    text, r"RUNC_LM_Z", r"RUNC_HM_Z", r"RUNC_LM_X", r"RUNC_HM_X",
                    r"relative uncertainty",
                ),
            }
        else:
            facts = {
                "system": "VTEM",
                "transmitter_specification_present": has(
                    text, r"Transmitter loop diameter:\s*26\s*m",
                    r"Effective transmitter loop area:\s*2123\.7\s*m2",
                    r"Transmitter base frequency:\s*25\s*Hz",
                ),
                "peak_current_present": has(text, r"Peak current:\s*192\s*A"),
                "exact_waveform_present": has(text, r"VTEM Transmitter Current Waveform", r"Time\s+Current"),
                "exact_gate_table_present": has(text, r"Number of channels:\s*45", r"0\.021\s*-\s*10\.667\s*ms"),
                "receiver_specification_present": has(text, r"Receiver"),
                "coordinates_present": has(text, r"Longitude", r"Latitude"),
                "response_components": ["BFx", "BFz", "SFx", "SFz"],
                "response_fields_present": has(text, r"BFx", r"BFz", r"SFx", r"SFz"),
                "per_observation_relative_uncertainty_fields": [],
                "per_observation_uncertainty_present": False,
            }
        facts["contract_ready"] = all(
            value for key, value in facts.items()
            if key.endswith("_present") and key != "per_observation_uncertainty_present"
        ) and facts["per_observation_uncertainty_present"]
        facts["schema_members"] = schema_names
        contracts.append(facts)
        archives.append(
            {
                "record_id": record_id,
                "system": choice["system"],
                "archive": archive.name,
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": sha256(archive),
                "members": members,
            }
        )

    inventory = {
        "schema_version": "wp8-geoscience-australia-aem-multisystem-inventory-v1",
        "selection_sha256": sha256(SELECTION),
        "archives": archives,
        "central_directory_member_count": sum(len(item["members"]) for item in archives),
        "schema_bytes_read": schema_bytes_read,
        "allowed_schema_suffixes": list(SCHEMA_SUFFIXES),
        "observation_payload_members_opened": 0,
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    contract = {
        "schema_version": "wp8-geoscience-australia-aem-multisystem-contract-v1",
        "inventory_sha256": None,
        "audit_is_response_blind": True,
        "systems": contracts,
        "skytem_contract_ready": next(
            item["contract_ready"] for item in contracts if item["system"] == "SkyTEM"
        ),
        "vtem_contract_ready": next(
            item["contract_ready"] for item in contracts if item["system"] == "VTEM"
        ),
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "warning": (
            "SkyTEM has a complete waveform/geometry/gate/relative-uncertainty "
            "contract. VTEM lacks a per-observation uncertainty field, so the "
            "multi-system formal TEM contract remains incomplete."
        ),
    }
    INVENTORY.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    contract["inventory_sha256"] = sha256(INVENTORY)
    CONTRACT.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "archives": len(archives),
        "schema_bytes_read": schema_bytes_read,
        "skytem_contract_ready": contract["skytem_contract_ready"],
        "vtem_contract_ready": contract["vtem_contract_ready"],
        "observation_payload_members_opened": 0,
    }))


if __name__ == "__main__":
    main()
