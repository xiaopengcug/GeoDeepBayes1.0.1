#!/usr/bin/env python
"""Create a response-blind NTGS IP digital-attachment catalogue."""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/ntgs-ip-open-search-catalogue-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/ntgs-ip-open-search-catalogue.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for group in ("feeds", "pages"):
        for member in manifest[group]:
            path = RAW / member["path"]
            if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
                raise RuntimeError(f"NTGS catalogue member drift: {member['path']}")
    candidates = []
    for page in manifest["pages"]:
        text = (RAW / page["path"]).read_text(encoding="utf-8", errors="replace")
        links = [
            {
                "url": html.unescape(url),
                "name": re.sub(r"\s+", " ", html.unescape(name)).strip(),
            }
            for url, name in re.findall(
                r'href="([^"]+/bitstream/[^"]+)"[^>]*>([^<]+)</a>',
                text,
                flags=re.IGNORECASE,
            )
        ]
        for item in links:
            item["url"] = urllib.parse.urljoin(page["source_url"], item["url"])
        digital = [
            item
            for item in links
            if Path(urllib_name(item["name"])).suffix.lower()
            in {".zip", ".dat", ".gdd", ".mdb", ".csv", ".txt"}
        ]
        ip_named = [
            item
            for item in digital
            if re.search(r"(?:^|[_\W])(ip|dcip|pdip|gaip)(?:[_\W]|$)", item["name"], re.I)
            or re.search(r"raw.*(?:survey|geophys)|geophys.*raw", item["name"], re.I)
        ]
        if digital:
            candidates.append(
                {
                    "handle_url": page["source_url"],
                    "title": page["title"],
                    "digital_attachments": digital,
                    "ip_or_raw_named_attachments": ip_named,
                }
            )
    explicit = [item for item in candidates if item["ip_or_raw_named_attachments"]]
    result = {
        "schema_version": "wp8-ntgs-ip-open-search-catalogue-audit-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "query_count": len(manifest["queries"]),
        "unique_item_count": manifest["unique_item_count"],
        "items_with_digital_attachments": len(candidates),
        "items_with_explicit_ip_or_raw_named_attachments": len(explicit),
        "explicit_candidates": explicit,
        "data_payloads_downloaded": 0,
        "response_values_interpreted": 0,
        "nominal_223_item_threshold_exceeded": manifest["unique_item_count"] >= 223,
        "formal_contract_ready": False,
        "formal_cluster_power_gate_passes": False,
        "formal_test_endpoints_inspected": False,
        "test_unseal_count": 0,
        "conclusion": (
            "The search catalogue exceeds 223 nominal report items, but most are "
            "annual reports or mixed geophysics packages. Attachment names alone "
            "cannot prove TDIP observation contracts, licences, distinct campaigns "
            "or correlation-adjusted clusters. Only explicit candidates should be "
            "probed, response-blind, before any payload interpretation."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "items": result["unique_item_count"],
                "digital": len(candidates),
                "explicit": len(explicit),
            }
        )
    )


def urllib_name(value: str) -> str:
    return value.split("?", 1)[0]


if __name__ == "__main__":
    main()
