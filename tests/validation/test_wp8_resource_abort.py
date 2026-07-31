import pytest

from geodeepbayes.validation.feasibility import enforce_resource_budget


def test_resource_budget_accepts_measurement_below_limits():
    enforce_resource_budget(
        wall_time_seconds=1.0,
        peak_memory_bytes=100,
        timeout_seconds=2.0,
        memory_limit_bytes=200,
    )


@pytest.mark.parametrize(
    ("wall", "memory"),
    [(2.0, 100), (1.0, 200), (2.0, 200)],
)
def test_resource_budget_accepts_measurement_equal_to_limits(wall, memory):
    enforce_resource_budget(
        wall_time_seconds=wall,
        peak_memory_bytes=memory,
        timeout_seconds=2.0,
        memory_limit_bytes=200,
    )


@pytest.mark.parametrize(
    ("wall", "memory", "message"),
    [(2.1, 100, "wall-time"), (1.0, 201, "peak-memory")],
)
def test_resource_budget_aborts_on_limit_exceedance(wall, memory, message):
    with pytest.raises(RuntimeError, match=message):
        enforce_resource_budget(
            wall_time_seconds=wall,
            peak_memory_bytes=memory,
            timeout_seconds=2.0,
            memory_limit_bytes=200,
        )
