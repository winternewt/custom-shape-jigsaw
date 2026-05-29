"""Command-line interface (typer)."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from custom_shape_jigsaw.api import generate_jigsaw_sync
from custom_shape_jigsaw.config import BorderMode, JigsawConfig, TabSizeMode
from custom_shape_jigsaw.units import OutputUnit, ScaleModel

app = typer.Typer(
    add_completion=False,
    help="Headless generator for custom-shape (and rectangular) jigsaw-puzzle SVGs.",
)

_DEFAULT_OUTPUT = Path("data/output/jigsaw.svg")


@app.command()
def generate(
    border: Path | None = typer.Option(
        None, "--border", "-b", help="Custom border SVG (omit for a rectangular puzzle)."
    ),
    save: Path = typer.Option(_DEFAULT_OUTPUT, "--save", "-o", help="Output SVG path."),
    display: Path | None = typer.Option(
        None, "--display", help="Also write the unit-less preview SVG here."
    ),
    # Grid (rectangular mode) --------------------------------------------------------
    columns: int = typer.Option(100, help="Columns in cells (rectangular mode)."),
    rows: int = typer.Option(100, help="Rows in cells (rectangular mode)."),
    border_scale: float = typer.Option(1.0, help="Custom-border scale factor (cbsf)."),
    use_viewbox: bool = typer.Option(True, help="Bake the border SVG viewBox transform (abv)."),
    # Randomness ---------------------------------------------------------------------
    seed: int = typer.Option(0, help="Random seed (ignored if --nondeterministic)."),
    nondeterministic: bool = typer.Option(False, help="Use a non-reproducible RNG."),
    # Voronoi ------------------------------------------------------------------------
    grid_size: int = typer.Option(10, help="Voronoi seed spacing in cells (gsize)."),
    grid_noise: float = typer.Option(0.5, help="Seed jitter 0..1 (gnoise)."),
    # Tabs ---------------------------------------------------------------------------
    tab_size_mode: TabSizeMode = typer.Option(TabSizeMode.RELATIVE, help="Tab sizing mode."),
    tab_rel_pct: float = typer.Option(18.0, help="Relative tab size %% (tabrelsize)."),
    tab_abs_size: float = typer.Option(2.0, help="Absolute tab size mm (abstab)."),
    tab_min_size: float = typer.Option(1.5, help="Min tab size mm (mintab, rabs)."),
    tab_max_size: float = typer.Option(3.0, help="Max tab size mm (maxtab, rabs)."),
    tab_jitter_pct: float = typer.Option(5.0, help="Tab jitter %% (tabjitter)."),
    min_edge: float = typer.Option(10.0, help="Min edge length mm to draw a tab (minedge)."),
    cell_scale: float = typer.Option(2.0, help="Cell size in mm (cell_scale)."),
    max_cells: int = typer.Option(1_000_000, help="Guard: refuse puzzles above this cell count."),
    # Output scale / DPI -------------------------------------------------------------
    output_unit: OutputUnit = typer.Option(OutputUnit.MM, help="Unit for width/height."),
    dpi: float = typer.Option(96.0, help="Output DPI (used when --output-unit px)."),
    input_ppi: float = typer.Option(96.0, help="PPI for mapping the border viewBox."),
    no_viewbox: bool = typer.Option(False, help="Omit the viewBox from the saved SVG."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable info logging."),
) -> None:
    """Generate a jigsaw SVG and write it to --save."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    mode = BorderMode.CUSTOM if border is not None else BorderMode.RECTANGULAR
    config = JigsawConfig(
        mode=mode,
        columns=columns,
        rows=rows,
        border_scale=border_scale,
        use_viewbox=use_viewbox,
        seed=seed,
        nondeterministic=nondeterministic,
        grid_size=grid_size,
        grid_noise=grid_noise,
        tab_size_mode=tab_size_mode,
        tab_rel_pct=tab_rel_pct,
        tab_abs_size=tab_abs_size,
        tab_min_size=tab_min_size,
        tab_max_size=tab_max_size,
        tab_jitter_pct=tab_jitter_pct,
        min_edge=min_edge,
        cell_scale=cell_scale,
        max_cells=max_cells,
        scale_model=ScaleModel(
            input_ppi=input_ppi,
            output_unit=output_unit,
            dpi=dpi,
            emit_viewbox=not no_viewbox,
        ),
    )

    result = generate_jigsaw_sync(config, border, save_path=save, display_path=display)
    typer.echo(
        f"Wrote {save} - {result.piece_count} pieces, "
        f"{result.width:g} x {result.height:g} {output_unit.value} "
        f"({result.rows} x {result.cols} cells)"
    )


if __name__ == "__main__":
    app()
