"""Audit public metadata for locked WP8 methods on geodata.cn.

Only catalogue JSON, access-contract JSON, and public data-document attachments
are opened.  Entity response payloads are deliberately not requested.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geodata-cn-locked-methods-metadata-v1"
EVIDENCE = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "geodata-cn-locked-methods-metadata-audit-v1.json"
)
INFO_URL = (
    "https://www.geodata.cn/ManagerDev/"
    "comprehensive/api/scidata/entry/info?guid={guid}"
)
ENTITY_URL = (
    "https://www.geodata.cn/ManagerDev/"
    "comprehensive/api/scidata/entry/science/entity?guid={guid}"
)
FILE_URL = (
    "https://www.geodata.cn/ManagerDev/"
    "comprehensive/api/files/downloadStream?objectName={object_name}"
)

CANDIDATES = (
    {
        "id": "sichuan-central-wfem-2017",
        "method": "wfem",
        "guid": "37412589003507",
        "doi": "10.12041/geodata.37412589003507.ver1.db",
    },
    {
        "id": "jiajika-high-power-ip-2018",
        "method": "tdip_not_sip_fdip",
        "guid": "85294953740909",
        "doi": "10.12041/geodata.85294953740909.ver1.db",
    },
    {
        "id": "xiangnan-dual-frequency-ip-2018",
        "method": "dual_frequency_ip",
        "guid": "95559119370311",
        "doi": "10.12041/geodata.95559119370311.ver1.db",
    },
    {
        "id": "xiangdongbei-dual-frequency-ip-2018",
        "method": "dual_frequency_ip",
        "guid": "73507568835545",
        "doi": "10.12041/geodata.73507568835545.ver1.db",
    },
    {
        "id": "laizhou-em-demonstration-2020",
        "method": "csamt_offline_candidate",
        "guid": "95277768730770",
        "doi": "10.12041/geodata.95277768730770.ver1.db",
        "design": {
            "survey_area": "Shandong Laizhou",
            "line_ids": ["S1", "S2", "S3"],
            "total_line_length_km": 15,
            "csamt_station_spacing_m": 50,
            "nominal_station_upper_bound": 300,
            "formats": ["EDI"],
        },
    },
    {
        "id": "laizhou-em-comparison-2020",
        "method": "csamt_offline_candidate",
        "guid": "14839885116687",
        "doi": "10.12041/geodata.14839885116687.ver1.db",
        "design": {
            "survey_area": "Shandong Laizhou",
            "line_ids": ["C1"],
            "total_line_length_km": 8,
            "csamt_station_spacing_m": 50,
            "nominal_station_upper_bound": 160,
            "formats": ["EDI", "AVG"],
        },
    },
    {
        "id": "caosiyao-em-demonstration-2020",
        "method": "csamt_offline_candidate",
        "guid": "85425730722323",
        "doi": "10.12041/geodata.85425730722323.ver1.db",
        "design": {
            "survey_area": "Inner Mongolia Caosiyao",
            "line_ids": ["L1", "L2", "L3"],
            "total_line_length_km": 15,
            "csamt_station_spacing_m": 50,
            "nominal_station_upper_bound": 300,
            "formats": ["EDI"],
        },
    },
    {
        "id": "caosiyao-em-comparison-2020",
        "method": "csamt_offline_candidate",
        "guid": "35110458226511",
        "doi": "10.12041/geodata.35110458226511.ver1.db",
        "design": {
            "survey_area": "Inner Mongolia Caosiyao",
            "line_ids": ["L8"],
            "total_line_length_km": 8,
            "station_spacing_m": 100,
            "nominal_station_upper_bound": 80,
        },
    },
    {
        "id": "taohemu-em-demonstration-2019",
        "method": "csamt_offline_candidate",
        "guid": "6206984388243",
        "doi": "10.12041/geodata.6206984388243.ver1.db",
        "design": {
            "survey_area": "Inner Mongolia Taohemu",
            "line_ids": ["L1", "L2", "L3"],
            "total_line_length_km": 15,
            "nominal_station_upper_bound": None,
        },
    },
    {
        "id": "taohemu-em-comparison-2019",
        "method": "csamt_offline_candidate",
        "guid": "94898011792185",
        "doi": "10.12041/geodata.94898011792185.ver1.db",
        "design": {
            "survey_area": "Inner Mongolia Taohemu",
            "line_ids": ["L8"],
            "total_line_length_km": 8,
            "nominal_station_upper_bound": None,
        },
    },
    {
        "id": "xiongan-controlled-source-em-2020",
        "method": "controlled_source_offline_candidate",
        "guid": "88075782085513",
        "doi": "10.12041/geodata.88075782085513.ver1.db",
        "design": {
            "survey_area": "Xiongan",
            "total_line_length_km": 4,
            "station_spacing_m": 200,
            "nominal_station_upper_bound": 21,
            "published_product_counts": {"pxy": 21, "rxy": 21},
        },
    },
    {
        "id": "tongling-tensor-controlled-source-2021",
        "method": "controlled_source_offline_candidate",
        "guid": "2561252853247",
        "doi": "10.12041/geodata.2561252853247.ver1.db",
        "design": {
            "survey_area": "Anhui Tongling",
            "components": ["XY", "YX"],
            "products": ["apparent resistivity", "phase"],
            "nominal_station_upper_bound": None,
        },
    },
    {
        "id": "tongling-short-offset-em-2021",
        "method": "controlled_source_offline_candidate",
        "guid": "1722195349655",
        "doi": "10.12041/geodata.1722195349655.ver1.db",
        "design": {
            "survey_area": "Anhui Tongling",
            "documented_fields": [
                "line",
                "station",
                "x",
                "y",
                "frequency",
                "current",
                "Ex",
                "Ey",
                "Hx",
                "Hy",
                "Hz",
                "wide-field apparent resistivity",
                "wavenumber apparent resistivity",
            ],
            "nominal_station_upper_bound": None,
        },
    },
)


def get_bytes(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "GeoDeepBayes-WP8-public-metadata-audit/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except (TimeoutError, OSError, http.client.HTTPException) as error:
            last_error = error
            if attempt < 2:
                time.sleep(1 + attempt)
    assert last_error is not None
    raise last_error


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for paragraph in root.iter(namespace + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def compact(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    for candidate in CANDIDATES:
        guid = candidate["guid"]
        info_payload = get_bytes(INFO_URL.format(guid=guid))
        entity_payload = get_bytes(ENTITY_URL.format(guid=guid))
        info = json.loads(info_payload)["data"]
        access_rows = json.loads(entity_payload)["data"]

        if str(info["guid"]) != guid:
            raise ValueError(f"catalogue GUID mismatch for {guid}")
        if info.get("doi") != candidate["doi"]:
            raise ValueError(f"DOI mismatch for {guid}")
        if len(access_rows) != 1:
            raise ValueError(f"unexpected entity-contract count for {guid}")

        access = access_rows[0]
        profile_rows = info.get("profileData") or []
        if not profile_rows:
            raise ValueError(f"unexpected public document count for {guid}")
        profile_signatures = {
            (row.get("fileName"), row.get("fileSize"))
            for row in profile_rows
        }
        if len(profile_signatures) != 1:
            raise ValueError(f"non-identical public documents for {guid}")
        profile = profile_rows[0]
        file_path = profile["filePath"]
        suffix = Path(profile["fileName"]).suffix.lower()
        local_name = f"{candidate['id']}{suffix}"
        local_path = DATA / local_name
        document_payload = get_bytes(
            FILE_URL.format(object_name=urllib.parse.quote(file_path, safe=""))
        )
        if len(document_payload) != int(profile["fileSize"]):
            raise ValueError(f"public document byte count mismatch for {guid}")
        local_path.write_bytes(document_payload)

        text = docx_text(local_path) if suffix == ".docx" else ""
        record: dict[str, object] = {
            **candidate,
            "title": info["title"],
            "landing_page": (
                "https://www.geodata.cn/main/index.html"
                f"#/face_science_detail?guid={guid}"
            ),
            "catalogue_entity_bytes": int(info["fileSize"]),
            "catalogue_is_online": info.get("isOnline"),
            "catalogue_is_opened": info.get("isOpened"),
            "access_group_id": access.get("groupid"),
            "access_description": access.get("resDesc"),
            "anonymous_entity_download": False,
            "public_document_path": local_path.relative_to(ROOT).as_posix(),
            "catalogue_public_document_rows": len(profile_rows),
            "catalogue_public_document_unique_files": len(profile_signatures),
            "public_document_bytes": len(document_payload),
            "public_document_sha256": sha256_bytes(document_payload),
            "description": compact(info.get("description")),
            "quality": compact(info.get("descQuality")),
            "response_entity_opened": False,
        }

        if candidate["method"] == "wfem":
            fields = {
                "station": "Station" in text,
                "frequency": "Freq/Hz" in text,
                "source_current": "I/A" in text,
                "electric_field": "Emag/μV" in text,
                "relative_error": "Error%" in text,
                "apparent_resistivity": "Rho/Ω·m" in text,
                "receiver_coordinates": all(
                    token in text for token in ("X（m）", "Y（m）", "H（m）")
                ),
            }
            record.update(
                {
                    "documented_fields": fields,
                    "transmitter": "GY-200",
                    "receiver": "JSGY-2 (48 channels)",
                    "pseudo_random_source_documented": "伪随机信号" in compact(
                        info.get("description")
                    ),
                    "sampled_transmitter_waveform_public": False,
                    "source_endpoint_coordinates_public": False,
                    "station_count_public": None,
                    "formal_observation_contract_ready": False,
                    "cluster_gate_passes": False,
                    "power_gate_passes": False,
                    "decision": "high_value_offline_application_candidate",
                }
            )
        else:
            is_spectral = candidate["method"] == "sip_fdip"
            record.update(
                {
                    "locked_sip_fdip_method_match": is_spectral,
                    "formal_cluster_contribution": 0,
                    "decision": (
                        "excluded_time_domain_ip"
                        if candidate["method"] == "tdip_not_sip_fdip"
                        else "excluded_two_frequency_ip_not_spectral_population"
                    ),
                }
            )
            if "design" in candidate:
                record.update(
                    {
                        "public_document_design_audit": candidate["design"],
                        "sampled_transmitter_waveform_public": False,
                        "source_complete_population_public": False,
                        "formal_cluster_contribution": 0,
                        "decision": "high_value_offline_application_candidate",
                    }
                )

        records.append(record)

    evidence = {
        "schema_version": "wp8-geodata-cn-locked-methods-metadata-audit-v1",
        "audit_scope": "catalogue_access_contract_and_public_documents_only",
        "formal_test_responses_opened": 0,
        "test_unseal_count": 0,
        "records": records,
        "conclusion": {
            "new_wfem_original_data_catalogue_record_found": True,
            "anonymous_wfem_entity_download_found": False,
            "new_locked_sip_fdip_population_found": False,
            "offline_active_source_candidates_found": 9,
            "offline_csamt_candidates_found": 6,
            "nominal_csamt_station_upper_bound_at_least_223": 2,
            "formal_gate_change": False,
            "reason": (
                "The WFEM document exposes a strong field/geometry contract, "
                "but the entity is an offline resource available only by "
                "verified-user application; the IP records are time-domain or "
                "two-frequency products rather than a locked SIP/FDIP population. "
                "Two CSAMT catalogue designs nominally exceed 223 stations, but "
                "all nine added active-source entities are offline application "
                "resources and expose neither a source-complete anonymous "
                "population nor sampled transmitter waveforms."
            ),
        },
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
