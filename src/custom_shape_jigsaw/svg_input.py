"""Custom-border SVG loading, transform flattening, normalisation and sampling.

Replaces the browser pieces the JS used for custom borders: ``DOMParser`` + ``flatten.js``
(transform flattening + shape->path) + ``getBBox`` + ``getTotalLength``/``getPointAtLength``.
``svgelements`` does the parsing/flattening/bbox; arc-length sampling is done here by
subdividing each path segment by length (dense enough that no traversed grid cell is skipped),
which is parity-equivalent to the JS ``plotpath`` for the purpose of mask filling.
"""

from __future__ import annotations

import io
import logging
import math
import re
from pathlib import Path as FsPath
from typing import IO, NamedTuple

from svgelements import SVG, Matrix, Path, Shape

from custom_shape_jigsaw.errors import BorderParseError

logger = logging.getLogger(__name__)

BorderSource = str | bytes | FsPath | IO[str] | IO[bytes]

# Arc-length sample spacing as a fraction of a cell. 1/8 cell keeps consecutive samples well
# under one cell apart in every direction, so every crossed grid cell receives a sample.
_SAMPLE_FRACTION = 0.125
# Cheap chord probes used to estimate a segment's length without svgelements' arc-length
# integration, which recurses pathologically slowly on some degenerate curves.
_LENGTH_PROBES = 8
# Hard ceiling on samples per segment, so a malformed segment can never hang the sampler.
_MAX_SEGMENT_SAMPLES = 100_000

_SVG_OPEN_TAG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_DIM_ATTR = re.compile(r'\s(?:width|height)\s*=\s*"[^"]*"', re.IGNORECASE)


class BorderSample(NamedTuple):
    """One sampled point on the border, in grid coordinate space."""

    gx: int  # quantised grid column = round(rx)
    gy: int  # quantised grid row = round(ry)
    rx: float  # real grid column = svg_x / cell_scale
    ry: float  # real grid row = svg_y / cell_scale


def _js_round(value: float) -> int:
    """JS ``Math.round`` (round half up), not Python's round-half-to-even."""
    return math.floor(value + 0.5)


def _segment_subdivisions(segment, step: float) -> int:
    """How many sub-steps to sample a segment at ~``step`` spacing.

    Estimates the segment length from a few chord probes via the cheap ``point(t)`` API rather
    than svgelements' ``length()`` (whose adaptive arc-length integration can recurse
    pathologically on degenerate curves). Returns 0 for degenerate/zero-length segments.
    """
    start = segment.point(0.0)
    prev_x, prev_y = float(start.x), float(start.y)
    approx = 0.0
    for i in range(1, _LENGTH_PROBES + 1):
        point = segment.point(i / _LENGTH_PROBES)
        cur_x, cur_y = float(point.x), float(point.y)
        approx += math.hypot(cur_x - prev_x, cur_y - prev_y)
        prev_x, prev_y = cur_x, cur_y
    if approx == 0.0:
        return 0
    return min(_MAX_SEGMENT_SAMPLES, max(1, math.ceil(approx / step)))


def load_border_text(source: BorderSource) -> str:
    """Normalise any accepted border source to SVG text.

    Accepts a filesystem path, raw SVG text, bytes, or a text/binary file-like object.
    """
    if isinstance(source, bytes):
        return source.decode("utf-8")
    if hasattr(source, "read"):
        data = source.read()
        return data.decode("utf-8") if isinstance(data, bytes) else data
    if isinstance(source, FsPath):
        return source.read_text(encoding="utf-8")
    if isinstance(source, str):
        if "<svg" in source.lower():
            return source
        return FsPath(source).read_text(encoding="utf-8")
    raise BorderParseError(f"unsupported border source type: {type(source)!r}")


def _strip_root_dimensions(svg_text: str) -> str:
    """Remove ``width``/``height`` from the root ``<svg>`` tag only.

    Neutralises the viewBox->viewport scaling so coordinates stay in raw viewBox user units
    (the ``use_viewbox=False`` / ``abv`` unchecked behaviour).
    """
    match = _SVG_OPEN_TAG.search(svg_text)
    if not match:
        return svg_text
    tag = match.group(0)
    stripped_tag = _DIM_ATTR.sub("", tag)
    return svg_text[: match.start()] + stripped_tag + svg_text[match.end() :]


class CustomBorder:
    """A parsed, flattened, scaled and top-left-normalised custom border.

    Coordinates are in millimetres. ``paths`` are normalised svgelements ``Path`` objects (used
    both for grid-mask sampling and, after a half-cell shift, for the verbatim output outline).
    """

    def __init__(self, paths: list[Path], width: float, height: float) -> None:
        self.paths = paths
        self.width = width
        self.height = height

    @classmethod
    def from_source(
        cls,
        source: BorderSource,
        *,
        use_viewbox: bool,
        border_scale: float,
        input_ppi: float,
    ) -> CustomBorder:
        """Parse and normalise a border SVG, mirroring the JS ``generate()`` preprocessing."""
        text = load_border_text(source)
        if not use_viewbox:
            text = _strip_root_dimensions(text)

        svg = SVG.parse(io.StringIO(text), reify=True, ppi=input_ppi)
        raw_paths: list[Path] = []
        for element in svg.elements():
            if isinstance(element, Shape):
                path = abs(Path(element))
                if len(path) > 0:
                    raw_paths.append(path)
        if not raw_paths:
            raise BorderParseError("border SVG contains no usable shapes/paths")

        # Scale by the custom-border scale factor (cbsf), then normalise to the top-left corner.
        scale_matrix = Matrix.scale(border_scale)
        scaled = []
        for path in raw_paths:
            transformed = path * scale_matrix
            transformed.reify()
            scaled.append(transformed)

        min_x, min_y, _, _ = _combined_bbox(scaled)
        shift = Matrix.translate(-min_x, -min_y)
        normalised = []
        for path in scaled:
            transformed = path * shift
            transformed.reify()
            normalised.append(transformed)

        bb_x, bb_y, bb_x2, bb_y2 = _combined_bbox(normalised)
        # JS: width = bbox.width + bbox.x ; height = bbox.height + bbox.y (post-normalisation).
        width = (bb_x2 - bb_x) + bb_x
        height = (bb_y2 - bb_y) + bb_y
        logger.info(
            "Loaded custom border: %d paths, %.3f x %.3f mm (use_viewbox=%s, scale=%g)",
            len(normalised), width, height, use_viewbox, border_scale,
        )
        return cls(normalised, width, height)

    def sample_cells(self, cell_scale: float) -> list[BorderSample]:
        """Densely sample every path; return points in grid coordinate space.

        Replacement for the JS ``plotpath`` + ``fillmask`` sample-collection loop.
        """
        step = cell_scale * _SAMPLE_FRACTION
        samples: list[BorderSample] = []
        capped = 0
        for path in self.paths:
            for segment in path:
                n = _segment_subdivisions(segment, step)
                if n == 0:
                    continue
                if n >= _MAX_SEGMENT_SAMPLES:
                    capped += 1
                for i in range(n + 1):
                    point = segment.point(i / n)
                    rx = float(point.x) / cell_scale
                    ry = float(point.y) / cell_scale
                    samples.append(BorderSample(_js_round(rx), _js_round(ry), rx, ry))
        if capped:
            logger.warning("Sample cap hit on %d segment(s); border may be undersampled", capped)
        logger.info("Sampled %d border points (step=%.3f mm)", len(samples), step)
        return samples

    def output_paths(self, cell_scale: float) -> list[str]:
        """Return path ``d`` strings (millimetres) for the output outline.

        Applies the half-cell shift the JS adds after mask filling (``translate(cs/2, cs/2)``,
        index.html:886) so the outline aligns with the snapped border corners, then serialises.
        """
        transform = Matrix.translate(cell_scale / 2, cell_scale / 2)
        out: list[str] = []
        for path in self.paths:
            transformed = path * transform
            transformed.reify()
            out.append(transformed.d())
        return out


def _combined_bbox(paths: list[Path]) -> tuple[float, float, float, float]:
    """Union bounding box (min_x, min_y, max_x, max_y) over all paths."""
    boxes = [p.bbox() for p in paths if p.bbox() is not None]
    if not boxes:
        raise BorderParseError("border SVG has no measurable geometry")
    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    max_x = max(b[2] for b in boxes)
    max_y = max(b[3] for b in boxes)
    return min_x, min_y, max_x, max_y
