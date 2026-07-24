"""forward 子包测试共享 fixture: 小规模地下网格 + 地表观测点。"""
import numpy as np
import pytest
from discretize import TensorMesh


@pytest.fixture(scope="session")
def small_mesh():
    """8×8×4 = 256 单元的地下网格; x∈[0,400], y∈[-200,200], z∈[-200,0]。"""
    h = [8 * [50.0], 8 * [50.0], 4 * [50.0]]
    mesh = TensorMesh(h, origin=[0.0, -200.0, -200.0])
    return mesh


@pytest.fixture(scope="session")
def rx_locs():
    """地表（z=10）观测点, 6×6=36 点。"""
    x = np.linspace(50.0, 350.0, 6)
    y = np.linspace(-150.0, 150.0, 6)
    xx, yy = np.meshgrid(x, y)
    z = np.full(xx.size, 10.0)
    return np.c_[xx.ravel(), yy.ravel(), z]


@pytest.fixture(scope="session")
def ind_active(small_mesh):
    """活动单元: 全部地下单元（cell_centers 已在 z∈[-200,0]）。"""
    cc = small_mesh.cell_centers
    return cc[:, 2] <= -1e-9


@pytest.fixture
def grav_op(small_mesh, rx_locs, ind_active):
    from geodeepbayes.forward.gravity import GravityOperator
    return GravityOperator(small_mesh, rx_locs, "gz", ind_active)


@pytest.fixture
def mag_op(small_mesh, rx_locs, ind_active):
    from geodeepbayes.forward.magnetic import MagneticOperator
    return MagneticOperator(small_mesh, rx_locs, ind_active=ind_active)


@pytest.fixture
def rng():
    return np.random.default_rng(20260717)
