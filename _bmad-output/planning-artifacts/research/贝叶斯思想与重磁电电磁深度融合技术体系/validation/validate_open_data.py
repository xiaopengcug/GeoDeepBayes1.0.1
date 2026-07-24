from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import statistics
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path, base: Path) -> dict:
    return {"path": path.relative_to(base).as_posix(), "sha256": sha256(path)}


def iter_manifest_files(manifest: dict):
    for dataset in manifest.get("datasets", []):
        for item in dataset.get("files", []):
            yield dataset, item


def audit_manifest(manifest_path: Path, open_root: Path) -> tuple[list[dict], list[dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    rows = []
    issues = []
    for dataset, item in iter_manifest_files(manifest):
        relative = Path(item["path"].replace("\\", os.sep))
        local = (open_root / relative).resolve()
        try:
            local.relative_to(open_root.resolve())
        except ValueError:
            issues.append({"kind": "path_escape", "dataset": dataset.get("slug") or dataset.get("id"), "path": relative.as_posix()})
            continue
        row = {
            "dataset": dataset.get("slug") or dataset.get("id"),
            "category": dataset.get("category"),
            "path": relative.as_posix(),
            "exists": local.is_file(),
            "manifest_bytes": item.get("bytes"),
            "expected_bytes": item.get("expected_bytes"),
            "manifest_sha256": item.get("sha256"),
        }
        if local.is_file():
            row["actual_bytes"] = local.stat().st_size
            row["actual_sha256"] = sha256(local)
            row["bytes_match"] = row["actual_bytes"] == row["manifest_bytes"]
            row["sha256_match"] = row["actual_sha256"] == row["manifest_sha256"]
            row["upstream_size_match"] = (
                None if row["expected_bytes"] is None
                else row["actual_bytes"] == row["expected_bytes"]
            )
        else:
            row.update(actual_bytes=None, actual_sha256=None, bytes_match=False, sha256_match=False, upstream_size_match=None)
        if not row["exists"] or not row["bytes_match"] or not row["sha256_match"]:
            issues.append({"kind": "local_integrity", **row})
        elif row["upstream_size_match"] is False:
            issues.append({"kind": "upstream_size_discrepancy", **row})
        rows.append(row)
    return rows, issues


def numeric_csv_check(path: Path) -> dict:
    values = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        for row in reader:
            for value in row.values():
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                values.append(number)
    finite = [v for v in values if math.isfinite(v)]
    return {
        "path": path.as_posix(),
        "columns": fields,
        "numeric_values": len(values),
        "non_finite": len(values) - len(finite),
        "minimum": min(finite) if finite else None,
        "maximum": max(finite) if finite else None,
        "median": statistics.median(finite) if finite else None,
        "status": "passed" if fields and finite and len(values) == len(finite) else "failed",
    }


def gxf_check(path: Path) -> dict:
    text = path.read_text(encoding="ascii", errors="replace")
    keys = sorted(set(re.findall(r"(?m)^#([A-Z0-9_]+)", text)))
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    numbers = [float(token) for token in re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?", body)]
    non_finite = sum(not math.isfinite(value) for value in numbers)
    return {"path": path.as_posix(), "header_keys": keys, "numeric_values": len(numbers), "non_finite": non_finite, "status": "passed" if ("GRID" in keys or "ROWS" in keys or "POINTS" in keys) and numbers and non_finite == 0 else "failed"}


def zip_check(path: Path, suffixes: tuple[str, ...] = (), required_tokens: tuple[bytes, ...] = ()) -> dict:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        names = archive.namelist()
        matches = [n for n in names if n.lower().endswith(suffixes)] if suffixes else [n for n in names if not n.endswith("/")]
        nonempty = [n for n in matches if archive.getinfo(n).file_size > 0]
        token_ok = True
        numeric_values = 0
        non_finite = 0
        if required_tokens and nonempty:
            sample = archive.read(nonempty[0]).upper()
            token_ok = all(token.upper() in sample for token in required_tokens)
        if nonempty:
            sample_text = archive.read(nonempty[0]).decode("utf-8", errors="replace")
            parsed = [float(token) for token in re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?", sample_text)]
            numeric_values = len(parsed)
            non_finite = sum(not math.isfinite(value) for value in parsed)
    return {"path": path.as_posix(), "entries": len(names), "matching_entries": len(matches), "nonempty_entries": len(nonempty), "required_tokens_found": token_ok, "sample_numeric_values": numeric_values, "sample_non_finite": non_finite, "first_matches": matches[:10], "status": "passed" if bad is None and matches and len(nonempty) == len(matches) and token_ok and numeric_values > 0 and non_finite == 0 else "failed", "bad_entry": bad}


def wfem_check(folder: Path) -> dict:
    files = sorted(folder.glob("*.dat"))
    checks = [numeric_csv_check(path) for path in files]
    headers = {tuple(item["columns"]) for item in checks}
    return {"dataset": folder.name, "files": len(files), "consistent_headers": len(headers) == 1, "failed_files": sum(c["status"] != "passed" for c in checks), "status": "passed" if files and len(headers) == 1 and all(c["status"] == "passed" for c in checks) else "failed"}


def do27_check(path: Path) -> dict:
    required = {
        "Forward/GRAV_noisydata.obs",
        "Forward/MAG_noisydata.obs",
        "Forward/model_grav.den",
        "Forward/model_mag.sus",
        "Forward/mesh_inverse_ubc.msh",
        "PGI_joint_inversion/Joint_PGI_Grav_Mag.ipynb",
    }
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        prefix = names[0].rstrip("/") + "/"
        normalized = {name.removeprefix(prefix) for name in names}
        missing = sorted(required - normalized)
        stats = {}
        for relative in sorted(required):
            if relative in missing or not relative.startswith("Forward/"):
                continue
            raw = archive.read(prefix + relative).decode("utf-8", errors="replace")
            numbers = [float(token) for token in re.findall(r"(?<![A-Za-z])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?", raw)]
            finite = [number for number in numbers if math.isfinite(number)]
            stats[relative] = {
                "numeric_tokens": len(numbers),
                "non_finite": len(numbers) - len(finite),
                "minimum": min(finite) if finite else None,
                "maximum": max(finite) if finite else None,
            }
    return {
        "dataset": "DO-27 synthetic gravity-magnetic joint inversion",
        "archive": path.as_posix(),
        "required_entries": len(required),
        "missing_entries": missing,
        "numeric_assets": stats,
        "asset_status": "passed" if not missing else "failed",
        "inversion_validation_status": "blocked",
        "blocking_reason": "当前Python 3.11环境未安装simpeg/discretize；原始notebook版本兼容性尚未验证。",
        "status": "passed" if not missing and all(v["non_finite"] == 0 and v["numeric_tokens"] > 0 for v in stats.values()) else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open-data-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--run-id", default=f"open-data-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    args = parser.parse_args()
    open_root = args.open_data_root.resolve()
    output_root = args.output_root.resolve()
    run_dir = output_root / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)

    primary = open_root / "00_catalog" / "open_geophysics_data_manifest.json"
    mt_manifest = open_root / "mt-dataset" / "00_catalog" / "mt_download_manifest.json"
    primary_rows, primary_issues = audit_manifest(primary, open_root)
    mt_rows, mt_issues = audit_manifest(mt_manifest, open_root / "mt-dataset")

    selected = {
        "mountain_pass_magnetic": numeric_csv_check(open_root / "magnetic" / "USGS_MountainPass_airborne_magnetic_2020" / "Magnetic_Data.csv"),
        "mountain_pass_gravity": gxf_check(open_root / "gravity" / "USGS_MountainPass_airborne_gravity_gradiometry_grids_2020" / "602202_Fourier_gD_2p67_final.gxf"),
        "mt_edi": zip_check(open_root / "mt" / "USGS_SanAndreas_Parkfield_MT_EDI_1990" / "Magnetotelluric_Cross-Power_EDI.zip", (".edi",), (b">HEAD", b">SPECTRA FREQ")),
        "dc_ip": zip_check(open_root / "dc_ip" / "USGS_LittleColoradoRiver_ERT_2019" / "MB2.5.zip", (".dat", ".txt", ".csv")),
        "tem": zip_check(sorted((open_root / "tem" / "USGS_DineroTunnel_TEM_2023").glob("*.zip"))[0], (".csv", ".txt", ".dat", ".xyz")),
        "csamt": zip_check(open_root / "csamt" / "USGS_Hualapai_CSAMT_GrandCanyonWest_PlainTankFlat_2019" / "Station-GrandCanyonWest_PlainTankFlat.zip", (".stn", ".avg", ".edi", ".csv", ".txt")),
        "wfem": wfem_check(open_root / "wfem" / "Zenodo_BaotuSpring_WFEM_2025"),
    }
    do27_archive = next((open_root / "mining_geophysics" / "Zenodo_DO27_kimberlite_gravity_magnetic_joint_inversion_synthetic").glob("*.zip"))
    do27 = do27_check(do27_archive)
    selected["do27"] = do27

    integrity = {
        "primary_manifest": {"files": len(primary_rows), "issues": primary_issues, "rows": primary_rows},
        "mt_manifest": {"files": len(mt_rows), "issues": mt_issues, "rows": mt_rows},
    }
    selected_failures = [name for name, result in selected.items() if result["status"] != "passed"]
    local_integrity_failures = [
        issue for issue in primary_issues + mt_issues if issue["kind"] == "local_integrity"
    ]
    result = {
        "run_id": args.run_id,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "公开数据完整性、格式、数值与DO-27真值资产验证；不构成钻孔留出Field-validated证据。",
        "environment": {
            "os": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "powershell": os.environ.get("PSModulePath", "available"),
        },
        "integrity_summary": {
            "primary_files": len(primary_rows),
            "mt_files": len(mt_rows),
            "local_integrity_failures": len(local_integrity_failures),
            "upstream_size_discrepancies": sum(i["kind"] == "upstream_size_discrepancy" for i in primary_issues + mt_issues),
        },
        "selected_checks": selected,
        "selected_failures": selected_failures,
        "evidence_status": "Open-data-run",
        "field_validated": False,
        "synthetic_run": False,
        "overall_status": "passed" if not local_integrity_failures and not selected_failures else "failed",
    }

    integrity_path = run_dir / "integrity.json"
    result_path = run_dir / "results.json"
    integrity_path.write_text(json.dumps(integrity, ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    script_path = Path(__file__).resolve()
    selected_inputs = [
        open_root / "magnetic/USGS_MountainPass_airborne_magnetic_2020/Magnetic_Data.csv",
        open_root / "gravity/USGS_MountainPass_airborne_gravity_gradiometry_grids_2020/602202_Fourier_gD_2p67_final.gxf",
        open_root / "mt/USGS_SanAndreas_Parkfield_MT_EDI_1990/Magnetotelluric_Cross-Power_EDI.zip",
        open_root / "dc_ip/USGS_LittleColoradoRiver_ERT_2019/MB2.5.zip",
        sorted((open_root / "tem/USGS_DineroTunnel_TEM_2023").glob("*.zip"))[0],
        open_root / "csamt/USGS_Hualapai_CSAMT_GrandCanyonWest_PlainTankFlat_2019/Station-GrandCanyonWest_PlainTankFlat.zip",
        *sorted((open_root / "wfem/Zenodo_BaotuSpring_WFEM_2025").glob("*.dat")),
        do27_archive,
    ]
    run_manifest = {
        "run_id": args.run_id,
        "evidence_id": "EVD-OPEN-001",
        "status": "Open-data-run" if result["overall_status"] == "passed" else "Failed",
        "started_at": result["started_at"],
        "completed_at": result["completed_at"],
        "inputs": [artifact(primary, open_root), artifact(mt_manifest, open_root)] + [artifact(path, open_root) for path in selected_inputs],
        "script": {"path": script_path.name, "sha256": sha256(script_path)},
        "environment": {"os": result["environment"]["os"], "powershell": "7+", "python": platform.python_version()},
        "checks": [
            {"name": "manifest-local-integrity", "status": "passed" if not local_integrity_failures else "failed", "detail": f"{len(local_integrity_failures)} local failures"},
            {"name": "multi-format-open-data", "status": "passed" if not selected_failures else "failed", "detail": ",".join(selected_failures) or "8 selected checks passed"},
            {"name": "do27-inversion-runtime", "status": "blocked", "detail": do27["blocking_reason"]},
        ],
        "outputs": [artifact(integrity_path, output_root), artifact(result_path, output_root)],
        "approval": {"owner": None, "date": None, "decision": "pending"},
    }
    manifest_path = run_dir / "run-manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), **result["integrity_summary"], "selected_failures": selected_failures, "overall_status": result["overall_status"]}, ensure_ascii=False))
    return 0 if result["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
