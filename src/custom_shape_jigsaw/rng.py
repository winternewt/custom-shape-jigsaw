"""Deterministic and non-deterministic random number generation.

Faithful port of the JS RNG from ``index.html``::

    function random() {
        if ($("ndr").checked) { return Math.random(); }
        else { var x = Math.sin(seed) * 10000; seed += 1; return x - Math.floor(x); }
    }

``seed`` is an **integer counter** that increments by one on every draw.

Parity caveat: CPython's ``math.sin`` (platform libm) and V8's ``Math.sin`` (fdlibm) agree
for small integer arguments but diverge by ~1 ULP for some (e.g. 17, 18, 20...). Amplified by
``* 10000`` that is a ~1e-12 difference in the returned fraction, so the deterministic stream
matches the website only for roughly the first ~17 draws, then drifts. This means:

* **Internal determinism is exact** - the same inputs always yield byte-identical output, which
  is what reproducible library use needs.
* **Byte-exact parity with the website is not achievable** for non-trivial puzzles without
  vendoring V8's exact ``sin``. ``tests/test_rng.py`` asserts the matching prefix exactly and
  the full stream to a tolerance.
"""

from __future__ import annotations

import math
import random as _stdlib_random
from typing import Protocol, runtime_checkable


@runtime_checkable
class Rng(Protocol):
    """Minimal RNG interface used throughout the generator."""

    def random(self) -> float:
        """Return a float in ``[0, 1)``."""
        ...

    def uniform(self, lo: float, hi: float) -> float:
        ...

    def rbool(self) -> bool:
        ...

    def shuffle(self, arr: list) -> None:
        ...


class DeterministicRng:
    """Seeded ``sin``-based generator matching the JS implementation exactly.

    ``seed`` is kept as an integer and only ever incremented, never reassigned to a
    float, so no floating-point drift accumulates in the counter itself.
    """

    __slots__ = ("seed",)

    def __init__(self, seed: int) -> None:
        self.seed = int(seed)

    def random(self) -> float:
        x = math.sin(self.seed) * 10000.0
        self.seed += 1
        return x - math.floor(x)

    def uniform(self, lo: float, hi: float) -> float:
        return lo + self.random() * (hi - lo)

    def rbool(self) -> bool:
        return self.random() > 0.5

    def shuffle(self, arr: list) -> None:
        """In-place Fisher-Yates, matching JS ``Shuffle`` (``j = floor(random()*(i+1))``)."""
        for i in range(len(arr) - 1, 0, -1):
            j = math.floor(self.random() * (i + 1))
            arr[i], arr[j] = arr[j], arr[i]


class NondeterministicRng:
    """Wraps the standard library RNG, for the ``ndr`` ("ignore seed") checkbox."""

    __slots__ = ("_rng",)

    def __init__(self, seed: int | None = None) -> None:
        self._rng = _stdlib_random.Random(seed)

    def random(self) -> float:
        return self._rng.random()

    def uniform(self, lo: float, hi: float) -> float:
        return lo + self.random() * (hi - lo)

    def rbool(self) -> bool:
        return self.random() > 0.5

    def shuffle(self, arr: list) -> None:
        for i in range(len(arr) - 1, 0, -1):
            j = math.floor(self.random() * (i + 1))
            arr[i], arr[j] = arr[j], arr[i]


def palette_rng_draw_count(num_colors: int) -> int:
    """Number of ``random()`` draws consumed by ``generatepalette`` + ``Shuffle``.

    In the JS, ``generate()`` calls ``generatepalette(n)`` then ``Shuffle(palette)`` between
    seeding the grid and growing the Voronoi regions. The colors are preview-only, but those
    draws advance the *same* global seed, so the geometry RNG that follows depends on them.
    This computes the exact draw count so the port can replicate it.

    ``generatepalette`` (imagetracer.js:93) only calls ``random()`` when ``n >= 8`` (the RGB
    cube branch), filling ``rnd = n - floor(n**(1/3))**3`` leftover colors with 4 draws each.
    ``Shuffle`` of an ``n``-length list always consumes ``n - 1`` draws.
    """
    n = int(num_colors)
    palette_draws = 0
    if n >= 8:
        colorqnum = math.floor(n ** (1.0 / 3.0))
        rnd = n - colorqnum * colorqnum * colorqnum
        palette_draws = 4 * rnd
    shuffle_draws = max(0, n - 1)
    return palette_draws + shuffle_draws


def consume_palette_rng(rng: Rng, num_colors: int) -> None:
    """Advance ``rng`` by exactly the number of draws the JS palette step consumes."""
    for _ in range(palette_rng_draw_count(num_colors)):
        rng.random()
