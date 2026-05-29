# custom-shape-jigsaw

A headless **Python port** of [CustomShapeJigsawJs](https://github.com/proceduraljigsaw/CustomShapeJigsawJs).
It generates procedural jigsaw-puzzle SVGs — either a plain rectangle or the shape of an arbitrary
custom border SVG — using Voronoi tessellation for the piece layout and draradech's cubic-bezier
tab generator for the piece edges. **No browser, no Chrome/kaleido** — pure Python on the SVG.

The original `CustomShapeJigsawJs/` is kept in-repo as the reference implementation.

## Install

```bash
uv sync                  # runtime deps
uv sync --group dev      # + pytest, ruff
```

Runtime deps: `svgelements` (parse/flatten/sample), `numpy` (grid backend), `typer` (CLI),
`pydantic` (config). Python >= 3.11 (bounded by numpy 2.3+).

## Library usage

Async is the primary API (the CPU-bound core is offloaded to an executor); a sync wrapper is
provided for convenience.

```python
import asyncio
from custom_shape_jigsaw import generate_jigsaw, generate_jigsaw_sync, JigsawConfig, BorderMode

# Rectangular puzzle
cfg = JigsawConfig(mode=BorderMode.RECTANGULAR, rows=40, columns=40, seed=7)
result = generate_jigsaw_sync(cfg, save_path="data/output/rect.svg")
print(result.piece_count, result.width, result.height)

# Custom-shape puzzle from a border SVG (path, str, bytes, or file-like)
cfg = JigsawConfig(mode=BorderMode.CUSTOM, seed=0, cell_scale=3.0)
result = asyncio.run(generate_jigsaw(cfg, "data/input/shape.svg",
                                     save_path="data/output/shape.svg"))
```

`JigsawResult` exposes `display_svg`, `save_svg`, `width`, `height`, `piece_count`, `rows`, `cols`
and `write_save(path)` / `write_display(path)`.

## CLI

```bash
uv run custom-shape-jigsaw --rows 40 --columns 40 --seed 7 --save data/output/rect.svg
uv run custom-shape-jigsaw --border data/input/shape.svg --cell-scale 3 \
    --output-unit px --dpi 300 --save data/output/shape.svg
uv run custom-shape-jigsaw --help
```

## Form control → API argument

Every control on the original custom-shape page maps to a `JigsawConfig` field:

| JS control (id)        | `JigsawConfig` field        | Default | Notes |
|------------------------|-----------------------------|---------|-------|
| rect/custom tab        | `mode`                      | `RECTANGULAR` | `BorderMode` |
| `ncols` / `nrows`      | `columns` / `rows`          | 100 / 100 | rectangular mode |
| `cbsf`                 | `border_scale`              | 1.0     | custom-border scale factor |
| `abv` (Use viewbox)    | `use_viewbox`               | True    | bake the border viewBox transform |
| `_seed` / `seed`       | `seed`                      | 0       | ignored if `nondeterministic` |
| `ndr`                  | `nondeterministic`          | False   | |
| `gsize`                | `grid_size`                 | 10      | Voronoi seed spacing (cells) |
| `gnoise`               | `grid_noise`                | 0.5     | seed jitter 0..1 |
| `tabsizemode`          | `tab_size_mode`             | `RELATIVE` | `rel`/`abs`/`rabs` |
| `tabrelsize`           | `tab_rel_pct`               | 18      | → `tab_rel_size = /200` |
| `abstab`               | `tab_abs_size`              | 2.0     | mm |
| `mintab` / `maxtab`    | `tab_min_size` / `tab_max_size` | 1.5 / 3.0 | mm (rabs) |
| `tabjitter`            | `tab_jitter_pct`            | 5       | → `tab_jitter = /100` |
| `minedge`              | `min_edge`                  | 10      | mm; shorter edges drawn straight |
| `cell_scale`           | `cell_scale`                | 2.0     | mm/cell |
| (1e6 guard)            | `max_cells`                 | 1_000_000 | raises `TooLargeError` (no prompt) |
| (new)                  | `scale_model`               | `ScaleModel()` | output unit/DPI/viewBox |

Preview-only controls (`pixelscell`, `stv`, colour palette) are intentionally omitted.

## Output scale / DPI

All geometry lives in **millimetres** (the viewBox coordinate space). `ScaleModel` controls only
how the document is *labelled*, so changing units never disturbs the geometry or tab sizing:

```python
from custom_shape_jigsaw import ScaleModel, OutputUnit
ScaleModel(output_unit=OutputUnit.PX, dpi=300)   # width/height in px at 300 dpi, viewBox in mm
ScaleModel(output_unit=OutputUnit.IN)            # inches
ScaleModel(input_ppi=25.4)                        # interpret a custom border at true physical mm
ScaleModel(emit_viewbox=False)                    # omit the viewBox
```

The default `ScaleModel()` (mm in, mm out, viewBox on) reproduces the original save-SVG header.

## Fidelity to the JavaScript original

- **Internal determinism is exact**: the same config + seed always yields byte-identical output.
- **The tab geometry is bit-exact** vs the JS (verified in `tests/test_tab_parity.py`, which feeds
  an identical fixed RNG sequence into both implementations).
- **Byte-exact parity with the website is *not* achievable** for non-trivial puzzles, and no amount
  of output-structure sorting fixes it. The RNG is `sin(seed)*10000 - floor(...)`; CPython's libm
  `sin` and V8's fdlibm `sin` agree for the first ~17 draws then differ by ~1 ULP (~1e-12 after
  `*10000`). Because each draw feeds `floor`/`rbool` branch decisions, the *sequences themselves*
  diverge — so the puzzles differ in geometry, not merely in element order. True parity would
  require vendoring a V8-identical `sin`. `tests/test_rng.py` asserts the matching prefix exactly
  and the full stream to tolerance.
- A few JS floating-point quirks are reproduced deliberately (e.g. `floor(64**(1/3)) == 3`).

## numpy backend

The automaton grids are numpy-backed (compact storage + vectorised scans). Per repo convention,
`numpy` is imported lazily inside `grids.py`; if it is ever absent, those functions raise
`NotImplementedError` — a deliberate seam for a future pure-Python backend.

## Tests

```bash
uv run pytest                 # all (incl. Node-based golden tests if node is present)
uv run pytest -m "not slow"   # skip the large stress test
uv run pytest -m golden        # Track-2 parity vs JS (needs node)
```

Data lives under `data/input`, `data/output`, `data/interim` per repo convention.
