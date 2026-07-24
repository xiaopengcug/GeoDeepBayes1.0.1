"""WP6统一治理门。默认验证工程门，--release额外验证发布签核与证明。"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
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


def validate_release_evidence(
    project: Path,
    evidence_root_path: Path,
    bundle_path: Path,
    verification_path: Path,
) -> list[str]:
    errors: list[str] = []
    evidence = json.loads(evidence_root_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    expected_identity = (
        "https://github.com/xiaopengcug/GeoDeepBayes1.0.1/"
        ".github/workflows/ci.yml@refs/heads/main"
    )
    expected_issuer = "https://token.actions.githubusercontent.com"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if evidence.get("commit_sha") != head:
        errors.append("evidence-root未绑定当前HEAD")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("evidence-root artifacts非法")
    else:
        if governance.canonical_sha256(artifacts) != evidence.get("root_sha256"):
            errors.append("evidence-root根哈希不匹配")
        for artifact in artifacts:
            path = project / artifact["path"]
            try:
                path = governance.resolve_inside(project, path)
            except (FileNotFoundError, ValueError):
                errors.append(f"evidence-root成员路径非法: {artifact.get('path')}")
                continue
            if (
                path.stat().st_size != artifact.get("bytes")
                or governance.file_sha256(path) != artifact.get("sha256")
            ):
                errors.append(f"evidence-root成员漂移: {artifact.get('path')}")
    bundle_hash = sha256(bundle_path.read_bytes()).hexdigest()
    expected_record = {
        "verified": True,
        "provider": "sigstore-fulcio-rekor",
        "commit_sha": head,
        "repository": "xiaopengcug/GeoDeepBayes1.0.1",
        "certificate_identity": expected_identity,
        "certificate_oidc_issuer": expected_issuer,
        "bundle_sha256": bundle_hash,
    }
    for field, expected in expected_record.items():
        if verification.get(field) != expected:
            errors.append(f"attestation记录字段不匹配: {field}")
    cosign = shutil.which("cosign")
    if cosign is None:
        errors.append("发布门缺少cosign可执行文件")
    else:
        result = subprocess.run(
            [
                cosign,
                "verify-blob",
                str(evidence_root_path),
                "--bundle",
                str(bundle_path),
                "--certificate-identity",
                expected_identity,
                "--certificate-oidc-issuer",
                expected_issuer,
            ],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            errors.append("cosign密码学验证失败")
    return errors


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
    try:
        source_config = json.loads(
            (HERE / "protection-sources.json").read_text(encoding="utf-8")
        )
        protected, examined = governance.protected_version_closure(
            RESEARCH_ROOT,
            source_config["sources"],
            policy["protected_reference_types"],
        )
        if not protected or not examined:
            failures.append("GC保护闭包为空")
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        failures.append(f"GC保护闭包构建失败: {error}")

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
        for required in (
            "cosign sign-blob",
            "cosign verify-blob",
            "https://token.actions.githubusercontent.com",
        ):
            if required not in text:
                failures.append(f"CI缺少最终evidence-root外部证明: {required}")

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
        bundle = HERE / "evidence-root.sigstore.json"
        attestation = HERE / "attestation-verification.json"
        if not all(path.is_file() for path in (evidence_root, bundle, attestation)):
            failures.append("缺少最终evidence-root、Sigstore bundle或外部证明验证记录")
        else:
            failures.extend(
                f"release:{message}"
                for message in validate_release_evidence(
                    project, evidence_root, bundle, attestation
                )
            )

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
