"""WP6机器契约验证器。

JSON Schema负责结构约束；本模块负责时间、成熟度、主张、哈希和唯一合同等
跨字段不变量。任何失败均返回非零退出码。
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import importlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent
RESEARCH_ROOT = ROOT.parent
MATURITY = {
    "Planned": 0,
    "Implemented": 1,
    "Unit-verified": 2,
    "Synthetic-verified": 3,
    "Field-validated": 4,
}
CLAIM_LEVEL = {
    "design": 0,
    "implemented": 1,
    "unit-behavior": 2,
    "synthetic": 3,
    "field": 4,
}


def project_root() -> Path:
    current = ROOT
    while current.parent != current:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("无法定位项目根目录")


def load(path: str | Path) -> Any:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return json.loads(candidate.read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def schema_errors(schema_name: str, instance: Any) -> list[str]:
    validator = Draft202012Validator(
        load(schema_name), format_checker=FormatChecker()
    )
    return [
        f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    ]


def evidence_semantic_errors(run: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    execution = run["execution"]
    started = datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00"))
    ended = datetime.fromisoformat(execution["ended_at"].replace("Z", "+00:00"))
    if ended < started:
        errors.append("ended_at早于started_at")
    if execution["outcome"] == "succeeded":
        if execution["exit_code"] != 0:
            errors.append("成功运行的exit_code必须为0")
        if execution["failure_reason"] is not None:
            errors.append("成功运行不得填写failure_reason")
        if not run["outputs"]:
            errors.append("成功运行必须至少有一个输出")
    else:
        if not execution["failure_reason"]:
            errors.append("失败或阻塞运行必须填写failure_reason")
        if run["claims"]:
            errors.append("失败或阻塞运行不得支持正向主张")
    randomness = run["randomness"]
    if randomness["stochastic"] and not randomness["seeds"]:
        errors.append("随机运行必须登记至少一个seed")
    if not randomness["stochastic"] and randomness["seeds"]:
        errors.append("确定性运行不得登记seed")
    expected_root = canonical_sha256(run["code"]["manifest"])
    if run["code"]["sha256"] != expected_root:
        errors.append("code.sha256与规范化manifest根不一致")
    attestation = run["attestation"]
    if attestation["required"]:
        required = ("subject_digest", "workflow", "commit_sha")
        if any(not attestation[field] for field in required) or not attestation["verified"]:
            errors.append("required attestation必须字段完整且verified=true")
    for claim in run["claims"]:
        if CLAIM_LEVEL[claim["scope"]] > MATURITY[claim["max_maturity"]]:
            errors.append(f"主张{claim['claim_id']}超过max_maturity")
    return errors


def capability_semantic_errors(capability: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    level = MATURITY[capability["maturity"]]
    implementation = capability["implementation"]
    verification = capability["verification"]
    if level == 0:
        if implementation is not None or any(verification.values()):
            errors.append("Planned能力不得登记实现或验证证据")
        if capability["allowed_claims"] != ["design"]:
            errors.append("Planned能力只允许design主张")
        return errors
    if implementation is None:
        errors.append("Implemented及以上必须绑定模块和符号")
    else:
        try:
            module = importlib.import_module(implementation["module"])
            if not hasattr(module, implementation["symbol"]):
                errors.append("实现符号不存在")
        except Exception as exc:  # noqa: BLE001 - 必须把导入失败转成治理失败
            errors.append(f"实现模块不可导入: {exc}")
    root = project_root()
    if level >= 2:
        if not verification["unit_tests"]:
            errors.append("Unit-verified及以上必须绑定单元测试")
        for node in verification["unit_tests"]:
            test_path = node.split("::", 1)[0]
            if not (root / test_path).is_file():
                errors.append(f"单元测试路径不存在: {test_path}")
    if level >= 3 and not verification["synthetic_runs"]:
        errors.append("Synthetic-verified及以上必须绑定合成运行")
    if level >= 4 and not verification["field_runs"]:
        errors.append("Field-validated必须绑定现场运行")
    for scope in capability["allowed_claims"]:
        if CLAIM_LEVEL[scope] > level:
            errors.append(f"允许主张{scope}超过成熟度")
    return errors


def registry_errors() -> list[str]:
    errors: list[str] = []
    registry = load("contract-registry.json")
    diagnostics = registry["contracts"]["diagnostics"]
    canonical = RESEARCH_ROOT / diagnostics["canonical_path"]
    if not canonical.is_file():
        return ["唯一诊断合同不存在"]
    actual = sha256(canonical.read_bytes()).hexdigest()
    if diagnostics["sha256"] != actual:
        errors.append("诊断合同registry哈希漂移")
    diagnostic_id = load(canonical)["contract_id"]
    if diagnostic_id != diagnostics["contract_id"]:
        errors.append("诊断合同ID与registry不一致")
    return errors


def method_fixture(base: dict[str, Any], method: str) -> dict[str, Any]:
    result = deepcopy(base)
    result["dataset_id"] = f"fixture-{method}-v2"
    result["method"] = method
    result["sampling"] = {"frequencies_hz": [], "time_windows_s": []}
    if method in {"sip_fdip", "mt_amt", "csamt", "wfem"}:
        result["sampling"]["frequencies_hz"] = [1.0]
    if method in {"tdip", "tem"}:
        result["sampling"]["time_windows_s"] = [[0.001, 0.002]]
    return result


def run_validation(self_test: bool = False) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    base = load("examples/valid-data-contract.json")
    methods = ["gravity", "magnetic", "dc", "tdip", "sip_fdip", "tem", "mt_amt", "csamt", "wfem"]
    for method in methods:
        errors = schema_errors("data-contract.schema.json", method_fixture(base, method))
        if errors:
            failures.append({"case": f"observation-{method}", "errors": errors})

    capabilities = load("operator-capabilities.json")
    for capability in capabilities:
        errors = schema_errors("operator-capability.schema.json", capability)
        errors += capability_semantic_errors(capability) if not errors else []
        if errors:
            failures.append({"case": f"capability-{capability['operator_id']}", "errors": errors})

    run = load("examples/valid-evidence-run-v2.json")
    errors = schema_errors("evidence-run.schema.json", run)
    errors += evidence_semantic_errors(run) if not errors else []
    if errors:
        failures.append({"case": "evidence-v2", "errors": errors})

    registry = registry_errors()
    if registry:
        failures.append({"case": "diagnostic-registry", "errors": registry})

    if self_test:
        for field in (
            "data", "coordinates", "acquisition", "sampling",
            "uncertainty", "nuisance", "applicability",
        ):
            broken = deepcopy(base)
            del broken[field]
            if not schema_errors("data-contract.schema.json", broken):
                failures.append({"case": f"missing-observation-{field}", "errors": ["负例被接受"]})

        planned_upgrade = deepcopy(capabilities[-1])
        planned_upgrade["maturity"] = "Implemented"
        if not capability_semantic_errors(planned_upgrade):
            failures.append({"case": "placeholder-upgrade", "errors": ["不存在的实现被升级"]})

        mutations = {
            "time-order": lambda item: item["execution"].update(
                started_at="2026-07-24T00:00:02Z", ended_at="2026-07-24T00:00:01Z"
            ),
            "exit-code": lambda item: item["execution"].update(exit_code=1),
            "missing-seed": lambda item: item["randomness"].update(seeds=[]),
            "code-root": lambda item: item["code"].update(sha256="0" * 64),
            "claim-level": lambda item: item["claims"][0].update(
                scope="field", max_maturity="Unit-verified"
            ),
        }
        for name, mutate in mutations.items():
            broken = deepcopy(run)
            mutate(broken)
            if not evidence_semantic_errors(broken):
                failures.append({"case": name, "errors": ["证据语义负例被接受"]})

        for field in ("code", "inputs", "configs", "outputs", "environment", "randomness", "approval", "claims"):
            broken = deepcopy(run)
            del broken[field]
            if not schema_errors("evidence-run.schema.json", broken):
                failures.append({"case": f"missing-evidence-{field}", "errors": ["缺字段负例被接受"]})

    return {
        "status": "passed" if not failures else "failed",
        "methods": len(methods),
        "capabilities": len(capabilities),
        "self_test": self_test,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = run_validation(args.self_test)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
