#!/usr/bin/env python
"""Freeze public WFEM metadata/contract references without response values."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/wfem-public-contract-references-v1"
SOURCES = {
    "nedc-hunan-dataset.html": (
        "https://data.earthquake.cn/datashare/report.shtml?"
        "PAGEID=dataset_detail&id=983e2280-f4ba-11ee-be3a-fa163ee6351b"
    ),
    "wucaiwan-crossref.json": (
        "https://api.crossref.org/works/10.3390/app16104601"
    ),
    "wucaiwan-article.pdf": (
        "https://mdpi-res.com/d_attachment/applsci/applsci-16-04601/"
        "article_deploy/applsci-16-04601-v2.pdf"
    ),
    "jiangsu-hdr-frontiers.html": (
        "https://www.frontiersin.org/journals/earth-science/articles/"
        "10.3389/feart.2025.1579468/full"
    ),
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 WFEM metadata freeze"}
    )
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as out:
        while block := response.read(1024 * 1024):
            out.write(block)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for name, url in SOURCES.items():
        path = DATA / name
        if not path.exists():
            fetch(url, path)
        members.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": url,
            }
        )
    nedc = (DATA / "nedc-hunan-dataset.html").read_text(
        encoding="utf-8", errors="replace"
    )
    if (
        "10.12080/nedc.prj_zdyf.ds00028.2021" not in nedc
        or "订单审核后获取" not in nedc
    ):
        raise RuntimeError("NEDC WFEM access contract drift")
    crossref = json.loads(
        (DATA / "wucaiwan-crossref.json").read_text(encoding="utf-8")
    )
    if crossref["message"]["DOI"].lower() != "10.3390/app16104601":
        raise RuntimeError("Wucaiwan Crossref metadata drift")
    manifest = {
        "schema_version": "wp8-wfem-public-contract-references-raw-v1",
        "selection_role": "metadata_and_contract_reference_only",
        "selection_is_response_blind": True,
        "members": members,
        "response_values_interpreted_during_acquisition": 0,
        "formal_test_endpoints_inspected": 0,
        "test_unseal_count": 0,
    }
    target = DATA / "raw-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (*[DATA / name for name in SOURCES], target):
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(members), "bytes": sum(x["bytes"] for x in members)}))


if __name__ == "__main__":
    main()
