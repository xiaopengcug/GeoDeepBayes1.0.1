"""WP6统一治理门。默认验证工程门，--release额外验证发布签核与证明。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parents[1]
CONTRACTS = RESEARCH_ROOT / "contracts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"无法加载模块: {path}")
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract_validator = load_module(
    "wp6_contract_validator_runtime", CONTRACTS / "validate_contracts.py"
)
governance = load_module("wp6_governance_runtime", CONTRACTS / "wp6_governance.py")


def find_project_root() -> Path:
    current = HERE
    while current.parent != current:
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent
    raise RuntimeError("无法定位项目根目录")


def validate(*, self_test: bool, release: bool) -> dict[str, object]:
    project = find_project_root()
    failures: list[str] = []

    contracts = contract_validator.run_validation(self_test=self_test)
    for failure in contracts["failures"]:
        failures.append(f"contract:{failure['case']}:{failure['errors']}")

    legacy = HERE / "legacy-index.json"
    failures.extend(
        f"legacy:{message}"
        for message in governance.validate_legacy_index(RESEARCH_ROOT, legacy)
    )

    snapshots = json.loads((HERE / "governance-snapshots.json").read_text(encoding="utf-8"))
    counts = [snapshot["entries"] for snapshot in snapshots["snapshots"]]
    if counts != [58, 59]:
        failures.append("治理快照必须按历史顺序登记entries=58和entries=59")

    policy = json.loads((HERE / "policy.json").read_text(encoding="utf-8"))
    if policy["retention_days"] != 30 or policy["quota_gib"] != 20:
        failures.append("孤儿保留策略必须为30天/20GiB")
    required_protection = {
        "active-pointer", "manifest", "claim", "signoff",
        "migration-envelope", "attestation",
    }
    if set(policy["protected_reference_types"]) != required_protection:
        failures.append("GC保护引用类型不完整")

    workflow = (project / ".github" / "workflows" / "ci.yml")
    if not workflow.is_file():
        failures.append("缺少CI工作流")
    else:
        text = workflow.read_text(encoding="utf-8")
        if "continue-on-error: true" in text:
            failures.append("CI仍含continue-on-error: true")
        for required in ("pull_request:", "merge_group:", "windows-latest", "ubuntu-latest"):
            if required not in text:
                failures.append(f"CI缺少: {required}")
        if "actions/attest" not in text:
            failures.append("CI缺少最终evidence-root attestation")

    gitignore = project / ".gitignore"
    if not gitignore.is_file():
        failures.append("缺少Git提交边界")
    else:
        ignore = gitignore.read_text(encoding="utf-8")
        for required in ("open-data/", ".venv", "__pycache__", "versions/"):
            if required not in ignore:
                failures.append(f".gitignore缺少排除规则: {required}")

    if release:
        signoff = json.loads((HERE / "signoff.json").read_text(encoding="utf-8"))
        decisions = [item["decision"] for item in signoff["roles"]]
        if signoff["status"] != "Done" or decisions != ["Approved"] * 3:
            failures.append("WP6发布签核未完成")
        evidence_root = HERE / "evidence-root.json"
        attestation = HERE / "attestation-verification.json"
        if not evidence_root.is_file() or not attestation.is_file():
            failures.append("缺少最终evidence-root或外部证明验证记录")
        else:
            verification = json.loads(attestation.read_text(encoding="utf-8"))
            if verification.get("verified") is not True:
                failures.append("外部attestation尚未验证")

    return {
        "status": "passed" if not failures else "failed",
        "self_test": self_test,
        "release": release,
        "contracts": contracts,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    result = validate(self_test=args.self_test, release=args.release)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
