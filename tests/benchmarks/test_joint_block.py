"""EVD-JOINT-001 诊断仪器的发布包正向对照。"""
from __future__ import annotations

from pathlib import Path
import json
import hashlib

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
JOINT_BLOCK_PATH = (
    REPOSITORY_ROOT / "src" / "geodeepbayes" / "benchmarks" / "joint_block.py"
)
POSITIVE_CONTROL_ROOT = (
    REPOSITORY_ROOT
    / "papers"
    / "paper01-rasti"
    / "evidence"
    / "positive-control"
)


def _joint_block_module():
    assert JOINT_BLOCK_PATH.is_file(), "发布树必须包含产生 65/65 判定的 joint_block.py"
    from geodeepbayes.benchmarks import joint_block

    return joint_block


def test_compute_diagnostics_passes_healthy_iid_positive_control():
    """捕获仪器只能失败、却没有可通过健康输入的回归。"""
    joint_block = _joint_block_module()
    rng = np.random.default_rng(20260825)
    channels = rng.standard_normal((4, 2000, 3))
    log_density = rng.standard_normal((4, 2000))
    thresholds = {
        "rank_normalized_split_rhat_max": 1.1,
        "bulk_ess_min": 100.0,
        "tail_ess_min": 100.0,
        "relative_mcse_max": 0.2,
    }

    result = joint_block.compute_diagnostics(channels, log_density, thresholds)

    assert result["status"] == "Passed"
    assert result["diagnostic_stop_reason"] is None
    assert all(result["checks"].values())
    assert result["degenerate_channel_count"] == 0


def test_published_positive_control_replays_to_declared_pass():
    """捕获发布包正向对照缺失、损坏或与仪器行为脱节的回归。"""
    joint_block = _joint_block_module()
    input_path = POSITIVE_CONTROL_ROOT / "joint-diagnostics-input.npz"
    expected_path = POSITIVE_CONTROL_ROOT / "joint-diagnostics-expected.json"
    assert input_path.is_file(), "发布包必须携带正向对照输入"
    assert expected_path.is_file(), "发布包必须携带正向对照预期结果"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(input_path.read_bytes()).hexdigest() == expected["input_sha256"]
    with np.load(input_path, allow_pickle=False) as payload:
        result = joint_block.compute_diagnostics(
            payload["channels"], payload["log_density"], expected["thresholds"]
        )

    assert {
        "status": result["status"],
        "checks": result["checks"],
        "n_channels": result["n_channels"],
        "diagnostic_stop_reason": result["diagnostic_stop_reason"],
    } == expected["expected"]
