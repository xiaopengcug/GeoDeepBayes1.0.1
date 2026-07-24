"""最小可执行运行合同：输入冻结、任务图和可验证检查点。

该模块不实现某一物理方法的正演；它为所有已实现算子提供相同的
schema/谱系/恢复边界，避免把文档中的工程接口误写成不可验证的约定。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence


def _canonical_hash(value: object) -> str:
    """Return a stable SHA-256 hash for JSON-compatible contract content."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TaskSpec:
    """A DAG task with explicit immutable dependencies."""

    name: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunContract:
    """Minimum fields required before a numerical run may start."""

    input_hashes: Mapping[str, str]
    operator_version: str
    model_contract: str
    algorithm_contract: str
    environment_hash: str
    tasks: tuple[TaskSpec, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        required = {
            "operator_version": self.operator_version,
            "model_contract": self.model_contract,
            "algorithm_contract": self.algorithm_contract,
            "environment_hash": self.environment_hash,
        }
        empty = [name for name, value in required.items() if not value]
        if empty:
            raise ValueError(f"missing run-contract fields: {', '.join(empty)}")
        if not self.input_hashes or any(not key or not value for key, value in self.input_hashes.items()):
            raise ValueError("input_hashes must contain named immutable hashes")
        names = {task.name for task in self.tasks}
        if len(names) != len(self.tasks) or "" in names:
            raise ValueError("task names must be non-empty and unique")
        for task in self.tasks:
            unknown = set(task.depends_on) - names
            if unknown:
                raise ValueError(f"task {task.name} has unknown dependencies: {sorted(unknown)}")
        self.topological_order()

    def topological_order(self) -> tuple[str, ...]:
        """Return a deterministic order or reject a cyclic task graph."""
        pending = {task.name: set(task.depends_on) for task in self.tasks}
        ordered: list[str] = []
        while pending:
            ready = sorted(name for name, deps in pending.items() if not deps)
            if not ready:
                raise ValueError("task DAG contains a cycle")
            for name in ready:
                ordered.append(name)
                del pending[name]
            for deps in pending.values():
                deps.difference_update(ready)
        return tuple(ordered)

    @property
    def contract_hash(self) -> str:
        self.validate()
        return _canonical_hash(
            {
                "input_hashes": dict(self.input_hashes),
                "operator_version": self.operator_version,
                "model_contract": self.model_contract,
                "algorithm_contract": self.algorithm_contract,
                "environment_hash": self.environment_hash,
                "tasks": [asdict(task) for task in self.tasks],
            }
        )


@dataclass(frozen=True)
class Checkpoint:
    """A restart record that is valid only for its exact frozen contract."""

    contract_hash: str
    completed_tasks: tuple[str, ...]
    state_hash: str

    def validate_for(self, contract: RunContract) -> None:
        contract.validate()
        if self.contract_hash != contract.contract_hash:
            raise ValueError("checkpoint contract hash mismatch")
        if not self.state_hash:
            raise ValueError("checkpoint state hash is missing")
        known = set(contract.topological_order())
        unknown = set(self.completed_tasks) - known
        if unknown:
            raise ValueError(f"checkpoint lists unknown tasks: {sorted(unknown)}")
        done = set(self.completed_tasks)
        for task in contract.tasks:
            if task.name in done and not set(task.depends_on).issubset(done):
                raise ValueError(f"checkpoint violates dependency closure at {task.name}")

    def write(self, path: str | Path) -> None:
        target = Path(path)
        target.write_text(json.dumps(asdict(self), sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: str | Path) -> "Checkpoint":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            contract_hash=data["contract_hash"],
            completed_tasks=tuple(data["completed_tasks"]),
            state_hash=data["state_hash"],
        )
