"""Download only STG files belonging to the frozen Taiwan ERI training components."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-design-v1.json"
INVENTORY = DATA / "taiwan-eri-mendeley-file-inventory-v2.json"
DESTINATION = DATA / "taiwan-eri-training-v1"
MANIFEST = DESTINATION / "manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    if (
        not design["selection_frozen_before_response_payload_access"]
        or design["role_counts"] != {"training": 23, "test": 223}
        or design["response_payloads_downloaded"] != 0
        or design["test_unseal_count"] != 0
    ):
        raise RuntimeError("Taiwan ERI design is not sealed")

    folders = {item["folder_id"]: item for item in inventory}
    children: dict[str, list[str]] = defaultdict(list)
    for item in inventory:
        if item.get("parent_id"):
            children[item["parent_id"]].append(item["folder_id"])

    selected: dict[str, dict[str, object]] = {}
    for component in design["components"]:
        if component["role"] != "training":
            continue
        component_id = component["component_id"]
        for centre in component["centres"]:
            profile_keys = {canonical(value) for value in centre["profiles"]}
            for metadata_folder in centre["metadata_folders"]:
                root_id = metadata_folder.split(":", 1)[0]
                queue = deque([root_id])
                visited = set()
                while queue:
                    folder_id = queue.popleft()
                    if folder_id in visited:
                        continue
                    visited.add(folder_id)
                    queue.extend(children.get(folder_id, []))
                    folder = folders.get(folder_id)
                    if folder is None or canonical(folder["folder_name"]) not in profile_keys:
                        continue
                    for item in folder["files"]:
                        if not item["filename"].lower().endswith(".stg"):
                            continue
                        stem = canonical(Path(item["filename"]).stem)
                        if not any(
                            stem.startswith(key)
                            and (len(stem) == len(key) or not stem[len(key)].isdigit())
                            for key in profile_keys
                        ):
                            continue
                        selected[item["id"]] = {
                            "component_id": component_id,
                            "folder_id": folder_id,
                            "folder_name": folder["folder_name"],
                            "file_id": item["id"],
                            "filename": item["filename"],
                            "declared_size": item["content_details"]["size"],
                            "download_url": item["content_details"]["download_url"],
                        }

    selected_components = {item["component_id"] for item in selected.values()}
    training_components = {
        item["component_id"]
        for item in design["components"]
        if item["role"] == "training"
    }
    if selected_components != training_components:
        missing = sorted(training_components - selected_components)
        raise RuntimeError(f"training STG mapping incomplete: {missing}")

    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = []
    for item in sorted(selected.values(), key=lambda value: (value["component_id"], value["file_id"])):
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", item["filename"])
        local_name = f"{item['component_id']}_{item['file_id']}_{safe_name}"
        path = DESTINATION / local_name
        if not path.is_file() or path.stat().st_size != item["declared_size"]:
            request = urllib.request.Request(
                item["download_url"], headers={"User-Agent": "WP8-training-audit/1.0"}
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                path.write_bytes(response.read())
        if path.stat().st_size != item["declared_size"]:
            raise RuntimeError(f"download size mismatch: {item['filename']}")
        manifest.append(
            {
                **{key: value for key, value in item.items() if key != "download_url"},
                "local_name": local_name,
                "downloaded_size": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    output = {
        "schema_version": "wp8-taiwan-eri-training-manifest-v1",
        "design_sha256": sha256(DESIGN),
        "inventory_sha256": sha256(INVENTORY),
        "training_component_count": len(training_components),
        "training_file_count": len(manifest),
        "training_bytes": sum(item["downloaded_size"] for item in manifest),
        "files": manifest,
        "test_files_downloaded": 0,
        "test_response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    MANIFEST.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_components": len(training_components),
                "training_files": len(manifest),
                "training_bytes": output["training_bytes"],
                "test_files_downloaded": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
