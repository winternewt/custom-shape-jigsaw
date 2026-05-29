"""Jigsaw tab (knob/blank) generator.

Direct port of draradech's tab generator embedded in ``index.html`` (lines 91-209). A tab is
nine control points defined parametrically along/perpendicular to the edge ``v1 -> v2`` and
emitted as three cubic-bezier segments ("M C C C"). The five jitter values plus the flip bool
are redrawn for every tab via :func:`_next_jitter`; **preserving that exact draw order is
required** because it advances the shared RNG interleaved with edge iteration.

Only ``lerp`` and the vector helpers are needed here — the JS ``scale``/``rotate``/``translate``/
``process`` helpers fed the canvas preview and are dead code for the SVG output path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from custom_shape_jigsaw.config import TabSizeMode
from custom_shape_jigsaw.rng import Rng

Vec = tuple[float, float]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def _mul(s: float, v: Vec) -> Vec:
    return (s * v[0], s * v[1])


def _rot90(v: Vec) -> Vec:
    return (-v[1], v[0])


@dataclass
class _Jitter:
    flip: bool
    a: float
    b: float
    c: float
    d: float
    e: float


def _next_jitter(rng: Rng, tab_jitter: float) -> _Jitter:
    """Replicate JS ``next()``: flip first, then a,b,c,d,e — in this exact order."""
    flip = rng.rbool()
    a = rng.uniform(-tab_jitter, tab_jitter)
    b = rng.uniform(-tab_jitter, tab_jitter)
    c = rng.uniform(-tab_jitter, tab_jitter)
    d = rng.uniform(-tab_jitter, tab_jitter)
    e = rng.uniform(-tab_jitter, tab_jitter)
    return _Jitter(flip, a, b, c, d, e)


def _tab_size(
    length: float,
    mode: TabSizeMode,
    tab_rel_size: float,
    tab_abs_size: float,
    tab_min_size: float,
    tab_max_size: float,
) -> float:
    """Compute the parametric tab size from the configured mode (index.html:175-192)."""
    if mode is TabSizeMode.RELATIVE:
        return tab_rel_size
    if mode is TabSizeMode.RESTRICTED:
        size = tab_rel_size
        if tab_rel_size * length < tab_min_size:
            size = tab_min_size / length
        if tab_rel_size * length > tab_max_size:
            size = tab_max_size / length
        return size
    if mode is TabSizeMode.ABSOLUTE:
        return tab_abs_size / length
    raise ValueError(f"unknown tab size mode: {mode!r}")


def _lerp(p_l: float, p_w: float, v1: Vec, v2: Vec, op: str) -> str:
    """Place a control point ``p_l`` along the edge and ``p_w`` perpendicular; format it.

    Mirrors JS ``lerp`` exactly, including the numeric stringification of the two coords.
    """
    dl = _sub(v2, v1)
    dw = _rot90(dl)
    vec = _add(v1, _mul(p_l, dl))
    vec = _add(vec, _mul(p_w, dw))
    return f"{op}{_num(vec[0])} {_num(vec[1])} "


def _num(value: float) -> str:
    """Stringify a coordinate the way JS string-concatenation does for these floats."""
    if value == int(value):
        return str(int(value))
    return repr(value)


def gen_tab(
    v1: Vec,
    v2: Vec,
    rng: Rng,
    *,
    mode: TabSizeMode,
    tab_rel_size: float,
    tab_abs_size: float,
    tab_min_size: float,
    tab_max_size: float,
    tab_jitter: float,
    is_new: bool = True,
) -> str:
    """Return the SVG path-data fragment for one tabbed edge from ``v1`` to ``v2``.

    ``v1``/``v2`` are the *scaled* endpoints (already multiplied by the output scale).
    """
    length = math.hypot(v2[0] - v1[0], v2[1] - v1[1])
    ts = _tab_size(length, mode, tab_rel_size, tab_abs_size, tab_min_size, tab_max_size)

    j = _next_jitter(rng, tab_jitter)
    sign = -1.0 if j.flip else 1.0

    def w(v: float) -> float:
        return v * sign

    # Nine control points (index.html p0..p9); l() is identity.
    points = [
        (0.0, w(0.0)),
        (0.2, w(j.a)),
        (0.5 + j.b + j.d, w(-ts + j.c)),
        (0.5 - ts + j.b, w(ts + j.c)),
        (0.5 - 2.0 * ts + j.b - j.d, w(3.0 * ts + j.c)),
        (0.5 + 2.0 * ts + j.b - j.d, w(3.0 * ts + j.c)),
        (0.5 + ts + j.b, w(ts + j.c)),
        (0.5 + j.b + j.d, w(-ts + j.c)),
        (0.8, w(j.e)),
        (1.0, w(0.0)),
    ]

    ops = ["M ", "C ", "", "", "C ", "", "", "C ", "", ""]
    out = []
    for idx, (pl, pw) in enumerate(points):
        if idx == 0 and not is_new:
            continue
        out.append(_lerp(pl, pw, v1, v2, ops[idx]))
    return "".join(out)
