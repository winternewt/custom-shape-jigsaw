"""Deterministic RNG parity with the JS original (Track 1)."""

from __future__ import annotations

import math

import pytest

from custom_shape_jigsaw.rng import (
    DeterministicRng,
    NondeterministicRng,
    consume_palette_rng,
    palette_rng_draw_count,
)

# Number of leading draws that match V8 bit-for-bit before platform-libm sin drift appears.
_EXACT_PREFIX = 16


@pytest.mark.parametrize("seed", ["0", "1", "42", "9999"])
def test_matches_js_prefix_exact(rng_reference, seed):
    """The first ~16 draws are bit-identical to V8 (small-integer sin agrees exactly)."""
    rng = DeterministicRng(int(seed))
    expected = rng_reference[seed][:_EXACT_PREFIX]
    produced = [rng.random() for _ in range(_EXACT_PREFIX)]
    assert produced == expected


@pytest.mark.parametrize("seed", ["0", "1", "42", "9999"])
def test_matches_js_within_tolerance(rng_reference, seed):
    """Beyond the exact prefix, libm vs fdlibm sin differ by ~1 ULP (~1e-12 after *10000)."""
    rng = DeterministicRng(int(seed))
    expected = rng_reference[seed]
    produced = [rng.random() for _ in range(len(expected))]
    assert produced == pytest.approx(expected, abs=1e-9)


def test_seed_is_integer_counter():
    rng = DeterministicRng(5)
    rng.random()
    rng.random()
    assert rng.seed == 7


def test_uniform_and_rbool_use_random():
    rng = DeterministicRng(0)
    # First draw at seed 0 is exactly 0.0 -> uniform maps to lo, rbool -> False.
    assert rng.uniform(10.0, 20.0) == 10.0
    rng2 = DeterministicRng(0)
    assert rng2.rbool() is False


def test_shuffle_is_deterministic():
    a = list(range(10))
    b = list(range(10))
    DeterministicRng(123).shuffle(a)
    DeterministicRng(123).shuffle(b)
    assert a == b
    assert sorted(a) == list(range(10))


@pytest.mark.parametrize(
    "n,palette_draws",
    [
        (4, 0),  # < 8 -> grayscale, no random() calls
        (7, 0),
        (8, 4 * (8 - 2**3)),  # floor(8**(1/3))=2 -> cube 8 -> 0 leftovers
        (27, 4 * (27 - 3**3)),  # floor=3 -> cube 27 -> 0 leftovers
        (50, 4 * (50 - 3**3)),  # floor=3 -> 23 leftovers
        # NB: floor(64**(1/3))==3 in BOTH Python and V8 (64**(1/3)==3.9999...), so the cube is
        # 27, not 64. We reproduce the JS FP quirk rather than the mathematically "correct" 4.
        (64, 4 * (64 - 3**3)),
        (125, 4 * (125 - 4**3)),  # floor(125**(1/3))==4 -> cube 64
    ],
)
def test_palette_draw_count(n, palette_draws):
    assert palette_rng_draw_count(n) == palette_draws + (n - 1)


def test_consume_palette_advances_seed():
    rng = DeterministicRng(0)
    consume_palette_rng(rng, 50)
    assert rng.seed == palette_rng_draw_count(50)


def test_nondeterministic_differs_between_instances():
    a = [NondeterministicRng().random() for _ in range(5)]
    b = [NondeterministicRng().random() for _ in range(5)]
    assert a != b


def test_cuberoot_floor_matches_js_quirk():
    # These lock the shared Python/V8 floating-point behaviour the palette count depends on.
    # 64**(1/3) and 125**(1/3) fall just below the integer, so floor drops them by one.
    assert math.floor(8 ** (1.0 / 3.0)) == 2
    assert math.floor(27 ** (1.0 / 3.0)) == 3
    assert math.floor(64 ** (1.0 / 3.0)) == 3  # not 4 (64**(1/3) == 3.9999999999999996)
    assert math.floor(125 ** (1.0 / 3.0)) == 4  # not 5 (125**(1/3) == 4.999999999999999)
