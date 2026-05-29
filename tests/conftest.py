"""Shared test fixtures and paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"
PROJECT_INPUT = Path(__file__).parent.parent / "data" / "input"


@pytest.fixture(scope="session")
def rng_reference() -> dict[str, list[float]]:
    """JS-captured ``random()`` sequences keyed by seed (see tests/tools/capture_rng.js)."""
    return json.loads((DATA_DIR / "rng_reference.json").read_text())


@pytest.fixture
def rect_border() -> str:
    return (DATA_DIR / "border_rect.svg").read_text()


@pytest.fixture
def circle_border() -> str:
    return (DATA_DIR / "border_circle.svg").read_text()


@pytest.fixture
def donut_border() -> str:
    return (DATA_DIR / "border_donut.svg").read_text()


@pytest.fixture
def all_animals_path() -> Path:
    """The user-provided multi-layer stress SVG (skipped if absent)."""
    p = PROJECT_INPUT / "ALL_ANIMALS.svg"
    if not p.exists():
        pytest.skip("ALL_ANIMALS.svg not present in data/input")
    return p
