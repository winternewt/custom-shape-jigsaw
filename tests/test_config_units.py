"""Config validation, derived values and the scale/unit model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from custom_shape_jigsaw.config import BorderMode, JigsawConfig, TabSizeMode
from custom_shape_jigsaw.units import OutputUnit, ScaleModel, format_number


def test_derived_conversions():
    cfg = JigsawConfig(tab_rel_pct=18.0, tab_jitter_pct=5.0)
    assert cfg.tab_rel_size == 18.0 / 200.0
    assert cfg.tab_jitter == 5.0 / 100.0


def test_enum_coercion_from_string():
    cfg = JigsawConfig(mode="custom", tab_size_mode="abs")
    assert cfg.mode is BorderMode.CUSTOM
    assert cfg.tab_size_mode is TabSizeMode.ABSOLUTE


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cell_scale": 0},
        {"grid_noise": 1.5},
        {"grid_size": 0},
        {"border_scale": -1},
        {"rows": 0},
        {"tab_min_size": 5, "tab_max_size": 1},
    ],
)
def test_invalid_config_rejected(kwargs):
    with pytest.raises((ValidationError, ValueError)):
        JigsawConfig(**kwargs)


def test_format_number_integers_have_no_decimal():
    assert format_number(40.0) == "40"
    assert format_number(40) == "40"
    assert format_number(1.5) == "1.5"


def test_scale_model_mm_identity():
    sm = ScaleModel()  # mm/mm/96/viewbox
    assert sm.mm_to_output(200.0) == 200.0
    assert sm.unit_suffix() == "mm"
    assert sm.viewbox(200.0, 100.0) == "0 0 200 100"


def test_scale_model_px_uses_dpi():
    sm = ScaleModel(output_unit=OutputUnit.PX, dpi=300.0)
    # 200 mm at 300 dpi = 200/25.4*300 px
    assert sm.mm_to_output(200.0) == pytest.approx(200.0 / 25.4 * 300.0)
    assert sm.unit_suffix() == "px"
    # viewBox stays in the mm coordinate space regardless of output unit.
    assert sm.viewbox(200.0, 100.0) == "0 0 200 100"


def test_scale_model_inch_and_cm():
    assert ScaleModel(output_unit=OutputUnit.IN).mm_to_output(25.4) == pytest.approx(1.0)
    assert ScaleModel(output_unit=OutputUnit.CM).mm_to_output(10.0) == pytest.approx(1.0)


def test_viewbox_can_be_disabled():
    assert ScaleModel(emit_viewbox=False).viewbox(10, 10) is None
