"""End-to-end generation: determinism, properties, output structure, custom borders."""

from __future__ import annotations

import asyncio
import xml.dom.minidom as minidom

import pytest

from custom_shape_jigsaw import (
    BorderMode,
    JigsawConfig,
    OutputUnit,
    ScaleModel,
    generate_jigsaw,
    generate_jigsaw_sync,
)
from custom_shape_jigsaw.errors import ConfigError, TooLargeError


def _rect(**kw) -> JigsawConfig:
    base = dict(mode=BorderMode.RECTANGULAR, rows=20, columns=20, seed=0)
    base.update(kw)
    return JigsawConfig(**base)


def _custom(border, **kw):
    base = dict(mode=BorderMode.CUSTOM, seed=0, cell_scale=3.0)
    base.update(kw)
    return generate_jigsaw_sync(JigsawConfig(**base), border)


def _well_formed(svg: str) -> minidom.Document:
    return minidom.parseString(svg)


def test_rectangular_basic():
    r = generate_jigsaw_sync(_rect())
    _well_formed(r.save_svg)
    _well_formed(r.display_svg)
    assert r.piece_count > 0
    assert r.rows == 20 and r.cols == 20
    assert r.width == 40.0 and r.height == 40.0
    assert r.save_svg.startswith('<svg viewBox="0 0 40 40" width="40mm" height="40mm"')


def test_determinism_same_seed():
    assert generate_jigsaw_sync(_rect()).save_svg == generate_jigsaw_sync(_rect()).save_svg


def test_seed_variation():
    a = generate_jigsaw_sync(_rect(seed=0)).save_svg
    b = generate_jigsaw_sync(_rect(seed=1)).save_svg
    assert a != b


def test_min_edge_extremes():
    no_tabs = generate_jigsaw_sync(_rect(min_edge=1e9))
    assert " C " not in no_tabs.save_svg  # all straight lines
    all_tabs = generate_jigsaw_sync(_rect(min_edge=0.0))
    assert " C " in all_tabs.save_svg


def test_nondeterministic_differs_run_to_run():
    cfg = _rect(nondeterministic=True)
    assert generate_jigsaw_sync(cfg).save_svg != generate_jigsaw_sync(cfg).save_svg


def test_too_large_guard():
    with pytest.raises(TooLargeError):
        generate_jigsaw_sync(_rect(rows=2000, columns=2000, max_cells=1_000_000))


def test_custom_requires_border():
    with pytest.raises(ConfigError):
        generate_jigsaw_sync(JigsawConfig(mode=BorderMode.CUSTOM))


def test_output_unit_px_scales_only_attributes():
    mm = generate_jigsaw_sync(_rect())
    px = generate_jigsaw_sync(_rect(scale_model=ScaleModel(output_unit=OutputUnit.PX, dpi=300)))
    # viewBox (coordinate space) identical; width attribute rescaled and suffixed px.
    assert 'viewBox="0 0 40 40"' in px.save_svg
    assert "px" in px.save_svg.split(">", 1)[0]
    assert px.width == pytest.approx(40.0 / 25.4 * 300.0)
    # The path geometry is byte-identical between unit choices.
    assert mm.save_svg.split("><path", 1)[1] == px.save_svg.split("><path", 1)[1]


def test_async_matches_sync():
    cfg = _rect()
    async_result = asyncio.run(generate_jigsaw(cfg))
    assert async_result.save_svg == generate_jigsaw_sync(cfg).save_svg


def test_write_files(tmp_path):
    out = tmp_path / "sub" / "jigsaw.svg"
    r = generate_jigsaw_sync(_rect(), save_path=out)
    assert out.exists()
    assert out.read_text() == r.save_svg


def test_custom_border_rect(rect_border):
    r = _custom(rect_border)
    _well_formed(r.save_svg)
    assert r.piece_count >= 1
    # The border outline path is always appended verbatim after any puzzle edges.
    assert r.save_svg.count("<path") >= 1


def test_custom_border_circle_multipiece(circle_border):
    r = _custom(circle_border)
    _well_formed(r.save_svg)
    assert r.piece_count >= 2
    # Puzzle edges (with tabs) plus the border outline.
    assert r.save_svg.count("<path") >= r.piece_count


def test_custom_border_donut_hole(donut_border):
    # The annulus exercises the even/odd flood fill (a hole inside the shape).
    r = _custom(donut_border)
    _well_formed(r.save_svg)
    assert r.piece_count >= 1


def test_use_viewbox_toggle_changes_scale():
    # A border with a viewBox smaller than its declared size: abv on vs off differ.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 50 50"><rect x="5" y="5" width="40" height="40"/></svg>'
    )
    on = _custom(svg, use_viewbox=True)
    off = _custom(svg, use_viewbox=False)
    assert (on.width, on.height) != (off.width, off.height)


@pytest.mark.slow
def test_all_animals_stress(all_animals_path):
    r = generate_jigsaw_sync(
        JigsawConfig(mode=BorderMode.CUSTOM, seed=0, cell_scale=4.0), all_animals_path
    )
    _well_formed(r.save_svg)
    assert r.piece_count > 0
    assert r.rows * r.cols > 1000  # large grid completed without recursion overflow
