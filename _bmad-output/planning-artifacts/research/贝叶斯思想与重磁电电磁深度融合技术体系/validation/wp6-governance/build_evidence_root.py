"""为最终commit生成可供GitHub attestation签署的证据根。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
CONTRACTS = HERE.parents[1] / "contracts"
spec = importlib.util.spec_from_file_location(
    "wp6_governance_builder", CONTRACTS / "wp6_governance.py"
)
module = importlib.util.module_from_spec(spec)
if spec.loader is None:
    raise RuntimeError("无法加载WP6治理模块")
sys.modules["wp6_governance_builder"] = module
spec.loader.exec_module(module)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/contract-registry.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/data-contract.schema.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/operator-capability.schema.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/evidence-run.schema.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/validate_contracts.py",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/wp6_governance.py",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/legacy-index.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/governance-snapshots.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/signoff.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/policy.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/protection-sources.json",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/gc_versions.py",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/record_attestation.py",
        "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp6-governance/validate_wp6.py"
    ]
    result = module.build_evidence_root(
        args.project_root.resolve(), paths, commit_sha=args.commit_sha
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(result["root_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
