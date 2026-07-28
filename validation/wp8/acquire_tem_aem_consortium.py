#!/usr/bin/env python
"""Acquire compatible USGS AEM candidates without interpreting response values."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/tem-aem-consortium-v1"
OUTPUT = RAW / "raw-manifest.json"
USER_AGENT = "GeoDeepBayes-WP8-feasibility/1.0 (public scientific data audit)"
ITEMS = {
    "yellowstone": {
        "doi": "10.5066/P9LVAU7W",
        "processed_item": "613793ced34e40dd9c0cdae3",
        "contract_item": "5d35fe69e4b01d82ce8a61d1",
        "names": {
            "YellowstoneNP_2016_Caldera_ProcessedData_Models.csv",
            "YellowstoneNP_2016_Central_ProcessedData_Models.csv",
            "YellowstoneNP_2016_MudPot_ProcessedData_Models.csv",
            "YellowstoneNP_2016_Norris_ProcessedData_Models.csv",
            "YellowstoneNP_2016_NorthEast_ProcessedData_Models.csv",
            "YellowstoneNP_2016_NYellowstone_ProcessedData_Models.csv",
            "YellowstoneNP_2016_ULGeysersB_ProcessedData_Models.csv",
            "YellowstoneNP_2016_DataDictionary_ProcessedData_Models.csv",
            "YellowstoneNP_2016_ProcessedData_Models.xml",
        },
    },
    "hualapai": {
        "doi": "10.5066/P91OLJN3",
        "processed_item": "5d606016e4b01d82ce98558e",
        "contract_item": "5d605f5de4b01d82ce98557e",
        "names": {
            "GrandCanyonWest2018_AEMGateTime.csv",
            "GrandCanyonWest2018_AEMProcessedData.xml",
            "GrandCanyonWest2018_DataDictionary_ProcessedAEMData.csv",
            "GrandCanyonWest2018_ProcessedAEMdata.csv",
            "GrandCanyonWest2018_SkyTEM_DataReport.pdf",
        },
    },
}


def api(item_id: str) -> tuple[bytes, dict[str, object]]:
    url = f"https://www.sciencebase.gov/catalog/item/{item_id}?format=json"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read()
    return body, json.loads(body)


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def download(url: str, path: Path) -> str:
    temporary = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as target:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            target.write(chunk)
    temporary.replace(path)
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    surveys = []
    for survey, specification in ITEMS.items():
        directory = RAW / survey
        directory.mkdir(exist_ok=True)
        metadata_records = []
        available = {}
        for item_id in (specification["processed_item"], specification["contract_item"]):
            body, metadata = api(str(item_id))
            metadata_records.append(
                {
                    "sciencebase_item_id": item_id,
                    "api_sha256": hashlib.sha256(body).hexdigest(),
                }
            )
            for entry in metadata["files"]:
                if entry["name"] in specification["names"]:
                    available[entry["name"]] = {**entry, "sciencebase_item_id": item_id}
        if set(available) != specification["names"]:
            raise RuntimeError(
                f"{survey} membership drift: {sorted(specification['names'] - set(available))}"
            )
        members = []
        for name in sorted(available):
            entry = available[name]
            path = directory / name
            retrieved = None
            if not path.is_file():
                retrieved = download(entry["downloadUri"], path)
            if path.stat().st_size != int(entry["size"]):
                raise RuntimeError(f"{survey} size mismatch: {name}")
            os.chmod(path, stat.S_IREAD)
            members.append(
                {
                    "name": name,
                    "path": f"{survey}/{name}",
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                    "download_uri": entry["downloadUri"],
                    "sciencebase_item_id": entry["sciencebase_item_id"],
                    "retrieved_at_utc": retrieved,
                    "observation_response_interpreted": False,
                }
            )
            print(f"downloaded/verified {survey}/{name}", flush=True)
        surveys.append(
            {
                "survey": survey,
                "doi": specification["doi"],
                "metadata": metadata_records,
                "member_count": len(members),
                "total_bytes": sum(member["bytes"] for member in members),
                "members": members,
            }
        )
    result = {
        "schema_version": "wp8-tem-aem-consortium-raw-manifest-v1",
        "candidate_status": "acquired_not_selected",
        "license": "USGS CC0/public domain",
        "survey_count": len(surveys),
        "member_count": sum(item["member_count"] for item in surveys),
        "total_bytes": sum(item["total_bytes"] for item in surveys),
        "observation_response_interpreted": False,
        "surveys": surveys,
    }
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(
        json.dumps(
            {
                "surveys": len(surveys),
                "members": result["member_count"],
                "bytes": result["total_bytes"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
