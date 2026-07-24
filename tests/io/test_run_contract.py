"""运行合同、DAG 与检查点恢复的独立回归测试。"""
from dataclasses import replace

import pytest

from geodeepbayes.io import Checkpoint, RunContract, TaskSpec


def _contract():
    return RunContract(
        input_hashes={"data": "a" * 64, "mesh": "b" * 64},
        operator_version="gravity-operator-v1",
        model_contract="joint-model-v1",
        algorithm_contract="metropolis-v1",
        environment_hash="c" * 64,
        tasks=(
            TaskSpec("ingest"),
            TaskSpec("forward", ("ingest",)),
            TaskSpec("infer", ("forward",)),
        ),
    )


def test_contract_has_deterministic_dag_and_hash():
    contract = _contract()
    assert contract.topological_order() == ("ingest", "forward", "infer")
    assert contract.contract_hash == _contract().contract_hash


def test_contract_rejects_cycle_and_missing_dependency():
    with pytest.raises(ValueError, match="cycle"):
        replace(_contract(), tasks=(TaskSpec("a", ("b",)), TaskSpec("b", ("a",)))).validate()
    with pytest.raises(ValueError, match="unknown dependencies"):
        replace(_contract(), tasks=(TaskSpec("a", ("missing",)),)).validate()


def test_checkpoint_requires_exact_contract_and_dependency_closure(tmp_path):
    contract = _contract()
    checkpoint = Checkpoint(contract.contract_hash, ("ingest", "forward"), "d" * 64)
    checkpoint.validate_for(contract)
    path = tmp_path / "checkpoint.json"
    checkpoint.write(path)
    assert Checkpoint.read(path) == checkpoint
    with pytest.raises(ValueError, match="contract hash mismatch"):
        Checkpoint("0" * 64, checkpoint.completed_tasks, checkpoint.state_hash).validate_for(contract)
    with pytest.raises(ValueError, match="dependency closure"):
        Checkpoint(contract.contract_hash, ("forward",), checkpoint.state_hash).validate_for(contract)
