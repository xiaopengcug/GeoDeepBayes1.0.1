"""Training-only header audit of NTGS CR2013-0857 CSAMT raw files."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = (
    ROOT
    / "validation/wp8/data/ntgs-cr2013-0857-csamt-v1/"
    "CR2013-0857_Geophysics.zip"
)
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "ntgs-cr20130857-csamt-design-audit-v1.json"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "ntgs-cr20130857-csamt-training-header-audit-v1.json"
)

ACQUISITION_HEADER = re.compile(
    r"^\s*(?P<frequency>\d+(?:\.\d+)?)\s+Hz\s+"
    r"(?P<cycles>\d+)\s+Cyc\s+Tx Curr\s+"
    r"(?P<current>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
JOB_HEADER = re.compile(
    r"^JOB\s+\d+\s+LINE\s+(?P<line>\d+)\s+N", re.IGNORECASE
)
RESPONSE_PREFIX = re.compile(r"^\s*\d+\s+(?:Ex|Hy)\s+", re.IGNORECASE)
RECORD_HEADER = re.compile(r"^[A-Z]{4}\d{4}\s+.*\s(?P<mode>AMT|D-D)\s")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if not design.get("role_assignment_frozen_before_response_access"):
        raise SystemExit("line roles were not frozen before training access")
    if design.get("response_payload_members_opened") != 0:
        raise SystemExit("design audit was not response blind")
    train_lines = set(design["line_roles"]["train"])
    sealed_lines = set(design["line_roles"]["test"])

    audited = {}
    observed_frequencies: Counter[float] = Counter()
    observed_currents: Counter[float] = Counter()
    with ZipFile(ARCHIVE) as archive:
        raw_members = {
            Path(name).stem: name
            for name in archive.namelist()
            if name.lower().endswith(".raw")
        }
        if not train_lines <= raw_members.keys():
            raise SystemExit("a frozen training raw member is missing")
        if not sealed_lines <= raw_members.keys():
            raise SystemExit("a frozen test raw member is missing")

        for line in sorted(train_lines):
            member = raw_members[line]
            payload = archive.read(member)
            text = payload.decode("latin1")
            frequency_headers = []
            job_lines = []
            response_row_count_not_interpreted = 0
            mode = None
            for row in text.splitlines():
                record = RECORD_HEADER.match(row)
                if record:
                    mode = record.group("mode")
                    continue
                acquisition = ACQUISITION_HEADER.match(row)
                if acquisition and mode == "AMT":
                    frequency = float(acquisition.group("frequency"))
                    cycles = int(acquisition.group("cycles"))
                    current = float(acquisition.group("current"))
                    frequency_headers.append(
                        {
                            "frequency_hz": frequency,
                            "cycles": cycles,
                            "transmitter_current_a": current,
                        }
                    )
                    observed_frequencies[frequency] += 1
                    observed_currents[current] += 1
                    continue
                job = JOB_HEADER.match(row)
                if job:
                    job_lines.append(job.group("line"))
                    continue
                if mode == "AMT" and RESPONSE_PREFIX.match(row):
                    response_row_count_not_interpreted += 1

            audited[line] = {
                "member": member,
                "bytes": len(payload),
                "sha256": sha256(payload),
                "job_line_identifiers": sorted(set(job_lines)),
                "acquisition_header_count": len(frequency_headers),
                "unique_frequency_hz": sorted(
                    {row["frequency_hz"] for row in frequency_headers}
                ),
                "unique_transmitter_current_a": sorted(
                    {row["transmitter_current_a"] for row in frequency_headers}
                ),
                "response_rows_skipped_without_value_parsing": (
                    response_row_count_not_interpreted
                ),
            }

    evidence = {
        "schema_version": "wp8-ntgs-cr20130857-csamt-training-header-audit-v1",
        "audit_date": "2026-07-25",
        "design_path": DESIGN.relative_to(ROOT).as_posix(),
        "design_sha256": sha256(DESIGN.read_bytes()),
        "archive_path": ARCHIVE.relative_to(ROOT).as_posix(),
        "archive_sha256": sha256(ARCHIVE.read_bytes()),
        "training_raw_members_opened": len(audited),
        "calibration_raw_members_opened": 0,
        "test_raw_members_opened": 0,
        "test_response_values_interpreted": 0,
        "training_response_values_interpreted": 0,
        "parsed_content": (
            "record/job headers and frequency/cycle/current acquisition headers only"
        ),
        "training_lines": audited,
        "training_acquisition_header_count": sum(
            line["acquisition_header_count"] for line in audited.values()
        ),
        "unique_frequency_hz": sorted(observed_frequencies),
        "unique_transmitter_current_a": sorted(observed_currents),
        "sampled_transmitter_waveform_present": False,
        "waveform_evidence_present": (
            "frequency, cycle count, source current, and odd-harmonic response "
            "labels only; no transmitter time samples or transmitter harmonic "
            "amplitude/phase series"
        ),
        "observation_contract_ready": False,
        "cluster_gate_passes": False,
        "power_gate_passes": False,
        "decision": (
            "Retain as provenance evidence but do not unseal calibration or test "
            "responses and do not admit to formal WP8 validation."
        ),
    }
    OUTPUT.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "training_members_opened": len(audited),
                "test_members_opened": 0,
                "frequencies": evidence["unique_frequency_hz"],
                "currents": evidence["unique_transmitter_current_a"],
                "output": OUTPUT.relative_to(ROOT).as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
