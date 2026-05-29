"""Public generation API: the orchestration core plus async and sync entry points.

The generation pipeline mirrors the JS ``generate()`` + ``paintoutput()`` exactly. It is
CPU-bound (pure-Python scalar automaton), so the async entry point offloads the core to an
executor; the sync wrapper calls the core directly.
"""

from __future__ import annotations

import asyncio
import concurrent.futures as cf
import logging
import math
from pathlib import Path

from custom_shape_jigsaw.automata import Automata
from custom_shape_jigsaw.config import BorderMode, JigsawConfig
from custom_shape_jigsaw.errors import ConfigError, TooLargeError
from custom_shape_jigsaw.result import JigsawResult
from custom_shape_jigsaw.rng import DeterministicRng, NondeterministicRng, Rng, consume_palette_rng
from custom_shape_jigsaw.svg_input import BorderSource, CustomBorder
from custom_shape_jigsaw.svg_output import build_svgs, edge_fragment

logger = logging.getLogger(__name__)


def _make_rng(config: JigsawConfig) -> Rng:
    if config.nondeterministic:
        return NondeterministicRng()
    return DeterministicRng(config.seed)


def _generate_core(config: JigsawConfig, border: BorderSource | None) -> JigsawResult:
    """Run the whole generation pipeline synchronously. Safe to call in a worker thread/process."""
    rng = _make_rng(config)

    custom_border: CustomBorder | None = None
    if config.mode is BorderMode.CUSTOM:
        if border is None:
            raise ConfigError("custom border mode requires a `border` source")
        custom_border = CustomBorder.from_source(
            border,
            use_viewbox=config.use_viewbox,
            border_scale=config.border_scale,
            input_ppi=config.scale_model.input_ppi,
        )
        cols = math.ceil(custom_border.width / config.cell_scale) + 1
        rows = math.ceil(custom_border.height / config.cell_scale) + 1
    else:
        rows, cols = config.rows, config.columns

    if rows * cols > config.max_cells:
        raise TooLargeError(
            f"{rows} x {cols} = {rows * cols} cells exceeds max_cells={config.max_cells}"
        )

    automata = Automata(rows, cols)
    if custom_border is not None:
        automata.fill_mask(custom_border.sample_cells(config.cell_scale))

    automata.grid_seed(config.grid_size, config.grid_noise, rng)
    # Reproduce the palette/shuffle RNG consumption that happens between seeding and growth.
    consume_palette_rng(rng, automata.piece_count + 1)
    automata.grow_regions(rng)

    corners = automata.find_corners(has_border=custom_border is not None)
    edges = automata.find_edges(corners)

    fragments = [
        edge_fragment(edge, automata.cornertable, config.cell_scale, config, rng) for edge in edges
    ]
    border_paths = (
        custom_border.output_paths(config.cell_scale) if custom_border is not None else None
    )

    display_svg, save_svg, width, height = build_svgs(
        fragments, border_paths, rows, cols, config.cell_scale, config.scale_model
    )
    logger.info("Generated jigsaw: %d pieces, %d edges, %d x %d cells",
                automata.piece_count, len(edges), rows, cols)
    return JigsawResult(
        display_svg=display_svg,
        save_svg=save_svg,
        width=width,
        height=height,
        piece_count=automata.piece_count,
        rows=rows,
        cols=cols,
    )


async def generate_jigsaw(
    config: JigsawConfig,
    border: BorderSource | None = None,
    *,
    save_path: str | Path | None = None,
    display_path: str | Path | None = None,
    executor: cf.Executor | None = None,
) -> JigsawResult:
    """Async entry point. Offloads the CPU-bound core to ``executor`` (default thread pool).

    For real parallelism across requests pass a :class:`concurrent.futures.ProcessPoolExecutor`;
    then ``border`` must be picklable (a path/str/bytes, not an open file object).
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, _generate_core, config, border)
    if save_path is not None:
        await asyncio.to_thread(result.write_save, save_path)
    if display_path is not None:
        await asyncio.to_thread(result.write_display, display_path)
    return result


def generate_jigsaw_sync(
    config: JigsawConfig,
    border: BorderSource | None = None,
    *,
    save_path: str | Path | None = None,
    display_path: str | Path | None = None,
) -> JigsawResult:
    """Synchronous wrapper around the generation core."""
    result = _generate_core(config, border)
    if save_path is not None:
        result.write_save(save_path)
    if display_path is not None:
        result.write_display(display_path)
    return result
