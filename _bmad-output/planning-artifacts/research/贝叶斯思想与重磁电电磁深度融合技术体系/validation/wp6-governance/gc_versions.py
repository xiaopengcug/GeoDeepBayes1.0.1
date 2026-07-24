"""WP6孤儿版本报告与显式安全清理。默认永不删除。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys


HERE = Path(__file__).resolve().parent
CONTRACTS = HERE.parents[1] / "contracts"
RESEARCH_ROOT = HERE.parents[1]
PROTECTION_SOURCES = HERE / "protection-sources.json"
spec = importlib.util.spec_from_file_location("wp6_gc_governance", CONTRACTS / "wp6_governance.py")
module = importlib.util.module_from_spec(spec)
if spec.loader is None:
    raise RuntimeError("无法加载WP6治理模块")
sys.modules["wp6_gc_governance"] = module
spec.loader.exec_module(module)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions-root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    policy = json.loads((HERE / "policy.json").read_text(encoding="utf-8"))
    source_config = json.loads(PROTECTION_SOURCES.read_text(encoding="utf-8"))
    protected, examined = module.protected_version_closure(
        RESEARCH_ROOT,
        source_config["sources"],
        policy["protected_reference_types"],
    )
    report = module.gc_report(args.versions_root, protected)
    deleted: list[str] = []
    if args.prune:
        for item in report["candidates"]:
            target = args.versions_root / item["path"]
            module.resolve_inside(args.versions_root, target)
            current_protected, _ = module.protected_version_closure(
                RESEARCH_ROOT,
                source_config["sources"],
                policy["protected_reference_types"],
            )
            if target.name in current_protected or target.is_symlink():
                raise RuntimeError(f"二次检查拒绝删除: {target}")
            shutil.rmtree(target)
            deleted.append(target.name)
    record = {
        "schema_version": "1.0.0",
        "mode": "Prune" if args.prune else "Report",
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report": report,
        "protection_sources_examined": examined,
        "protected_versions": sorted(protected),
        "deleted": deleted,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
