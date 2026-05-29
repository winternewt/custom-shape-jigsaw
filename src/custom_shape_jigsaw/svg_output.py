"""SVG assembly: edge endpoint snapping, straight/tab fragments and document strings.

Replaces ``imagetracer.js`` ``svgpathstringuncolored`` + ``getsvgstringstrokes`` and the
endpoint-snap of ``internodesopen``. All path coordinates are emitted in millimetres (the
viewBox coordinate space); the :class:`~custom_shape_jigsaw.units.ScaleModel` only changes the
``width``/``height`` attributes, so output unit/DPI never disturbs the geometry or tab sizing.
"""

from __future__ import annotations

import math

from custom_shape_jigsaw.automata import CornerSnap
from custom_shape_jigsaw.config import JigsawConfig
from custom_shape_jigsaw.rng import Rng
from custom_shape_jigsaw.tabs import gen_tab
from custom_shape_jigsaw.units import ScaleModel, format_number

# Matches the JS exactly so default-mm output can be byte-compared against the original.
_VERSION = "1.2.6custom"
_DESC = f"Created with a heavily modified imagetracer.js version {_VERSION}"
_STROKE = 'fill="none" stroke="black" stroke-width="0.5" opacity="1" '


def _snap(col: int, row: int, cornertable: list[CornerSnap]) -> tuple[float, float]:
    """Snap a grid endpoint to its border corner's real coordinate, if present.

    Port of the endpoint matching in ``internodesopen`` (imagetracer.js:130-139): a path point
    ``(x=col, y=row)`` is replaced by the cornertable entry whose ``(col, row)`` matches.
    """
    for snap in cornertable:
        if snap.col == col and snap.row == row:
            return snap.x, snap.y
    return float(col), float(row)


def edge_fragment(
    edge: list[tuple[int, int]],
    cornertable: list[CornerSnap],
    cell_scale: float,
    config: JigsawConfig,
    rng: Rng,
) -> str:
    """Path-data fragment for one edge: a straight line if short, else a tab.

    ``edge`` is the traced corner list; only its first and last corners are used (the JS reduces
    each edge to its two endpoints in ``paintoutput``).
    """
    r0, c0 = edge[0]
    rn, cn = edge[-1]
    x1, y1 = _snap(c0, r0, cornertable)
    x2, y2 = _snap(cn, rn, cornertable)
    start = (x1 * cell_scale, y1 * cell_scale)
    end = (x2 * cell_scale, y2 * cell_scale)
    tablength = math.hypot(end[0] - start[0], end[1] - start[1])
    if tablength < config.min_edge:
        return (
            f"M {format_number(start[0])} {format_number(start[1])} "
            f"L {format_number(end[0])} {format_number(end[1])} "
        )
    return gen_tab(
        start,
        end,
        rng,
        mode=config.tab_size_mode,
        tab_rel_size=config.tab_rel_size,
        tab_abs_size=config.tab_abs_size,
        tab_min_size=config.tab_min_size,
        tab_max_size=config.tab_max_size,
        tab_jitter=config.tab_jitter,
        is_new=True,
    )


def build_svgs(
    fragments: list[str],
    border_paths: list[str] | None,
    rows: int,
    cols: int,
    cell_scale: float,
    scale_model: ScaleModel,
) -> tuple[str, str, float, float]:
    """Assemble the display and save SVG strings.

    Returns ``(display_svg, save_svg, width_out, height_out)`` where the widths are in the
    configured output unit.
    """
    width_mm = cols * cell_scale
    height_mm = rows * cell_scale

    body: list[str] = []
    for frag in fragments:
        body.append(f'<path {_STROKE}d="{frag}" />')
    if border_paths is not None:
        for d in border_paths:
            body.append(f'<path fill="none" stroke="black" stroke-width="0.5" d="{d}"></path>')
    else:
        body.append(
            f'<rect x="0" y="0" width="{format_number(width_mm)}" '
            f'height="{format_number(height_mm)}" '
            'style="fill:none;stroke:black;stroke-width:0.5;fill-opacity:1;stroke-opacity:1" />'
        )
    common = (
        f'version="1.1" xmlns="http://www.w3.org/2000/svg" desc="{_DESC}" >'
        + "".join(body)
        + "</svg>"
    )

    display_svg = (
        f'<svg width="{format_number(width_mm)}" height="{format_number(height_mm)}" ' + common
    )

    width_out = scale_model.mm_to_output(width_mm)
    height_out = scale_model.mm_to_output(height_mm)
    suffix = scale_model.unit_suffix()
    save_header = "<svg "
    viewbox = scale_model.viewbox(width_mm, height_mm)
    if viewbox is not None:
        save_header += f'viewBox="{viewbox}" '
    save_header += f'width="{format_number(width_out)}{suffix}" '
    save_header += f'height="{format_number(height_out)}{suffix}" '
    save_svg = save_header + common

    return display_svg, save_svg, width_out, height_out
