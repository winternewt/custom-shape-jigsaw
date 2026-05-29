"""Track-2 parity: the tab bezier math matches the JS original exactly.

Injects an identical fixed RNG sequence into both the JS replica (tests/tools/capture_tab.js)
and the Python ``gen_tab``, isolating the geometry from the platform-libm sin divergence. The
numeric coordinates must agree to floating-point tolerance and the command letters must match.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from custom_shape_jigsaw.config import TabSizeMode
from custom_shape_jigsaw.tabs import gen_tab

pytestmark = pytest.mark.golden

_HARNESS = Path(__file__).parent / "tools" / "capture_tab.js"
_NODE = shutil.which("node")

# A fixed draw sequence: rbool() consumes 1, then 5x uniform() -> 6 draws per tab.
_RANDOMS = [0.73, 0.11, 0.92, 0.40, 0.58, 0.27]


def _letters(s: str) -> list[str]:
    return re.findall(r"[MLCQ]", s)


def _numbers(s: str) -> list[float]:
    return [float(t) for t in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", s)]


@pytest.mark.skipif(_NODE is None, reason="node not available")
@pytest.mark.parametrize(
    "mode",
    [TabSizeMode.RELATIVE, TabSizeMode.ABSOLUTE, TabSizeMode.RESTRICTED],
)
def test_gentab_matches_js(mode):
    v1 = (12.0, 7.5)
    v2 = (40.0, 33.25)
    params = dict(
        tab_rel_size=18.0 / 200.0,
        tab_abs_size=2.0,
        tab_min_size=1.5,
        tab_max_size=3.0,
        tab_jitter=5.0 / 100.0,
    )

    class FixedRng:
        def __init__(self, values):
            self._v = list(values)
            self._i = 0

        def random(self) -> float:
            v = self._v[self._i]
            self._i += 1
            return v

        def uniform(self, lo, hi):
            return lo + self.random() * (hi - lo)

        def rbool(self):
            return self.random() > 0.5

        def shuffle(self, arr):  # unused here
            raise NotImplementedError

    py = gen_tab(v1, v2, FixedRng(_RANDOMS), mode=mode, is_new=True, **params)

    cfg = {
        "v1": list(v1),
        "v2": list(v2),
        "mode": mode.value,
        "randoms": _RANDOMS,
        **params,
    }
    js = subprocess.check_output([_NODE, str(_HARNESS), json.dumps(cfg)], text=True)

    assert _letters(py) == _letters(js)
    assert _numbers(py) == pytest.approx(_numbers(js), abs=1e-9)
