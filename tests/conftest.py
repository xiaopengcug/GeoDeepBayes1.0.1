"""pytest 根级配置。

采用 src 布局；pyproject.toml 已设 pythonpath=["src"]，此处仅作兜底，
保证未 `pip install -e .` 时也可直接 `pytest tests/`。
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
