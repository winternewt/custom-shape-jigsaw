"""Configuration model mapping every custom-shape-page control to an API argument."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from custom_shape_jigsaw.units import ScaleModel


class BorderMode(StrEnum):
    RECTANGULAR = "rect"
    CUSTOM = "custom"


class TabSizeMode(StrEnum):
    RELATIVE = "rel"  # tabrelsize, internally value/200
    ABSOLUTE = "abs"  # abstab (mm)
    RESTRICTED = "rabs"  # relative, clamped to [mintab, maxtab] (mm)


class JigsawConfig(BaseModel):
    """All knobs from the custom-shape page, plus the new scale/DPI model.

    Percentage fields keep the JS UI semantics (e.g. ``tab_rel_pct=18``) and expose the
    derived internal values (``tab_rel_size = 18/200``) via properties, so callers can use
    whichever they find clearer.
    """

    model_config = ConfigDict(validate_assignment=True)

    # Border / grid -------------------------------------------------------------------
    mode: BorderMode = BorderMode.RECTANGULAR
    columns: int = Field(default=100, ge=1)  # ncols (rect mode only)
    rows: int = Field(default=100, ge=1)  # nrows (rect mode only)
    border_scale: float = Field(default=1.0, gt=0.0)  # cbsf, custom-border scale factor
    use_viewbox: bool = True  # abv, bake the SVG viewBox transform into coordinates

    # Randomness ----------------------------------------------------------------------
    seed: int = 0  # _seed / seed slider
    nondeterministic: bool = False  # ndr (seed ignored if True)

    # Voronoi seeding -----------------------------------------------------------------
    grid_size: int = Field(default=10, ge=1)  # gsize, seed spacing in cells
    grid_noise: float = Field(default=0.5, ge=0.0, le=1.0)  # gnoise

    # Tabs ----------------------------------------------------------------------------
    tab_size_mode: TabSizeMode = TabSizeMode.RELATIVE  # tabsizemode
    tab_rel_pct: float = Field(default=18.0, ge=0.0)  # tabrelsize (%), -> /200
    tab_abs_size: float = Field(default=2.0, gt=0.0)  # abstab (mm)
    tab_min_size: float = Field(default=1.5, gt=0.0)  # mintab (mm), rabs mode
    tab_max_size: float = Field(default=3.0, gt=0.0)  # maxtab (mm), rabs mode
    tab_jitter_pct: float = Field(default=5.0, ge=0.0)  # tabjitter (%), -> /100
    min_edge: float = Field(default=10.0, ge=0.0)  # minedge (mm); shorter -> straight

    # Cell scale ----------------------------------------------------------------------
    cell_scale: float = Field(default=2.0, gt=0.0)  # mm/cell; == imagetracer options.scale

    # Guards / output -----------------------------------------------------------------
    max_cells: int = Field(default=1_000_000, ge=1)  # rows*cols above this -> TooLargeError
    scale_model: ScaleModel = Field(default_factory=ScaleModel)

    # Derived internal values (match the JS conversions) ------------------------------
    @property
    def tab_rel_size(self) -> float:
        return self.tab_rel_pct / 200.0

    @property
    def tab_jitter(self) -> float:
        return self.tab_jitter_pct / 100.0

    @model_validator(mode="after")
    def _check_restricted_bounds(self) -> JigsawConfig:
        if self.tab_min_size > self.tab_max_size:
            raise ValueError("tab_min_size must be <= tab_max_size")
        return self
