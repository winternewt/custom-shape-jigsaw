"""Grid storage backend.

The cellular-automata grids are backed by numpy arrays (compact ``int32`` storage for puzzles
up to ~1e6 cells, plus vectorised passes for the embarrassingly-parallel scans). Per the repo
standard, ``numpy`` is the one library allowed to be imported lazily/inline: this module is the
single place that imports it, behind :func:`_require_numpy`, which raises
:class:`NotImplementedError` if numpy is unavailable. That is the deliberate seam where a future
pure-Python fallback backend could be added without touching the algorithm code.

Callers (``automata.py``) only ever touch the returned arrays via integer indexing
(``arr[i, j]``) and the vectorised helpers below, so they never need to import numpy themselves.
"""

from __future__ import annotations

import math
from typing import Any

NAN = math.nan


def _require_numpy() -> Any:
    """Return the numpy module, or raise ``NotImplementedError`` if it is not installed.

    Inline numpy import is the sanctioned exception to the no-inline-imports rule (see CLAUDE.md).
    """
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised only in numpy-less environments
        raise NotImplementedError(
            "The numpy grid backend is required but numpy is not installed. "
            "Install numpy (`uv add numpy`), or implement a pure-Python grid backend at this seam."
        ) from exc
    return np


def int_grid(rows: int, cols: int) -> Any:
    """Zero-filled ``int32`` grid of shape ``(rows, cols)``."""
    np = _require_numpy()
    return np.zeros((rows, cols), dtype=np.int32)


def float_grid(rows: int, cols: int, fill: float = NAN) -> Any:
    """``float64`` grid pre-filled with ``fill`` (NaN by default, used as an "empty" sentinel)."""
    np = _require_numpy()
    return np.full((rows, cols), fill, dtype=np.float64)


def count_truthy(arr: Any) -> int:
    """Number of non-zero entries (vectorised)."""
    np = _require_numpy()
    return int(np.count_nonzero(arr))


def count_empty(grid: Any, mask: Any) -> int:
    """Number of cells that are zero in ``grid`` AND zero in ``mask`` (vectorised)."""
    np = _require_numpy()
    return int(np.count_nonzero((grid == 0) & (mask == 0)))


def mod2_inplace(arr: Any) -> None:
    """Collapse every entry to its parity (``arr %= 2``), in place (vectorised)."""
    arr %= 2
