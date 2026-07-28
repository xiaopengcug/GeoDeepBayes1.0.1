#!/usr/bin/env python
"""Freeze the public OEDI Cymric FDEM package as a permanent WFEM mapping candidate."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/oedi-cymric-fdem-v1/permanently-training-only"
DOI = "10.15121/1560530"
PAGE = "https://data.openei.org/submissions/7306"
LICENSE = "CC-BY-4.0"
ANCHORS = {
    "oedi-submission-7306.html": (PAGE, 95663, "b6b1d0acfa90f1a181257a62cb9329351b34ef0adf0ecff42b130c77854a7055"),
    "cymric_field_data1_5hz.txt": ("https://gdr.openei.org/files/1169/cymric_field_data1_5hz.txt", 602, "e01824251e60a8cd24fbb639229fb8b9b770f00c834f8e089f1a4e39fba45a1a"),
    "cymric2_field_data_1Hz.txt": ("https://gdr.openei.org/files/1169/cymric2_field_data_1Hz.txt", 2286, "1987409b0bf7319a4f77aad2fd90a191b7a1f32a02abbd90f57a33cb07ecde30"),
    "cymric2_field_data_5Hz.txt": ("https://gdr.openei.org/files/1169/cymric2_field_data_5Hz.txt", 2284, "e19154c4cd8e1c67c3492747b150ea35774b6abbe11840164bb48e380beefa37"),
    "cymric_data1_survey_configuration.PNG": ("https://gdr.openei.org/files/1169/cymric_data1_survey_configuration.PNG", 68010, "12cdcddf8b999a8c31e0d864977709bd087ee611c6a6677b2bc4a29e20c51785"),
    "cymric_data2_survey_configuration.PNG": ("https://gdr.openei.org/files/1169/cymric_data2_survey_configuration.PNG", 851681, "5574c99617e6e29a6766aa64e6d9a954fc6804e66048d34080963262ea6ad9c1"),
}
SOURCES = {name: anchor[0] for name, anchor in ANCHORS.items()}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8-Cymric-training-freeze/1.0"}
    )
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as out:
            while block := response.read(1024 * 1024):
                out.write(block)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_manifest(data: Path = DATA) -> dict[str, object]:
    members = []
    for name, (url, expected_bytes, expected_sha) in ANCHORS.items():
        path = data / name
        if (
            not path.is_file()
            or path.stat().st_size != expected_bytes
            or sha256(path) != expected_sha
        ):
            raise RuntimeError(f"OEDI Cymric provider anchor drift: {name}")
        members.append(
            {"path": name, "source_url": url, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    page = (data / "oedi-submission-7306.html").read_text(encoding="utf-8", errors="replace")
    if DOI not in page or "https://creativecommons.org/licenses/by/4.0/" not in page:
        raise RuntimeError("OEDI Cymric DOI/license metadata drift")
    for url in SOURCES.values():
        if url not in page and url != PAGE:
            raise RuntimeError("OEDI Cymric public file inventory drift")
    return {
        "schema_version": "wp8-oedi-cymric-fdem-permanent-training-manifest-v1",
        "scope": "permanently-training-only",
        "mapping_role": "FDEM-to-WFEM-contract-candidate-only",
        "fdem_is_wfem": False,
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "doi": DOI,
        "submission_url": PAGE,
        "license": {"spdx": LICENSE, "url": "https://creativecommons.org/licenses/by/4.0/"},
        "members": members,
    }


def write_immutable(path: Path, value: dict[str, object]) -> None:
    body = (json.dumps(value, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable OEDI Cymric manifest drift")
        return
    path.write_bytes(body)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        path = DATA / name
        if not path.exists():
            fetch(url, path)
        expected_url, expected_bytes, expected_sha = ANCHORS[name]
        if (
            url != expected_url
            or path.stat().st_size != expected_bytes
            or sha256(path) != expected_sha
        ):
            raise RuntimeError(f"OEDI Cymric downloaded member drift: {name}")
    manifest = build_manifest()
    write_immutable(DATA / "raw-manifest.json", manifest)
    for path in (*[DATA / name for name in SOURCES], DATA / "raw-manifest.json"):
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(manifest["members"]), "scope": manifest["scope"]}))


if __name__ == "__main__":
    main()
