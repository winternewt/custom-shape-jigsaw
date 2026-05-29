"""Configurable input/output scale, units and DPI.

All geometry is computed internally in **millimetres** (``cell_scale`` is mm/cell and the
custom border is interpreted as mm, matching the JS which strips unit suffixes and treats
numbers as mm). Because the output is pure vector geometry it can be emitted in any unit at
any DPI without loss. :class:`ScaleModel` wraps that input interpretation and output emission.

The default ``ScaleModel()`` (mm in, mm out, viewBox on) reproduces the original JS save-SVG
header byte-for-byte. Other units / DPI are a capability the JS original did not have.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OutputUnit(StrEnum):
    MM = "mm"
    CM = "cm"
    IN = "in"
    PX = "px"


# Millimetres per one unit of the named unit (px depends on DPI and is handled separately).
_MM_PER_UNIT: dict[OutputUnit, float] = {
    OutputUnit.MM: 1.0,
    OutputUnit.CM: 10.0,
    OutputUnit.IN: 25.4,
}


def format_number(value: float) -> str:
    """Match JS number stringification closely: integers print without a trailing ``.0``."""
    if value == int(value):
        return str(int(value))
    return repr(value)


class ScaleModel(BaseModel):
    """Input-parse PPI plus output unit / DPI / viewBox configuration.

    ``input_ppi`` controls how a custom border's ``viewBox`` is mapped to its declared physical
    size when ``use_viewbox=True`` (the JS original implicitly uses 96, i.e. CSS px); the
    resulting numbers are then taken as millimetres. Set it to ``25.4`` to interpret the border
    at true physical millimetres instead. It is ignored when ``use_viewbox=False`` (raw viewBox
    user units are used directly).
    """

    model_config = ConfigDict(frozen=True)

    input_ppi: float = Field(default=96.0, gt=0.0)
    output_unit: OutputUnit = OutputUnit.MM
    dpi: float = Field(default=96.0, gt=0.0)
    emit_viewbox: bool = True

    # -- output ------------------------------------------------------------------------
    def mm_to_output(self, value_mm: float) -> float:
        """Convert internal millimetres to the configured ``output_unit`` magnitude."""
        return value_mm / self._mm_per(self.output_unit)

    def unit_suffix(self) -> str:
        return self.output_unit.value

    def viewbox(self, width_mm: float, height_mm: float) -> str | None:
        """Return the ``viewBox`` value, or ``None`` if disabled.

        The viewBox is the *coordinate space* of the path data, which is always millimetres
        (the internal geometry unit). Only ``width``/``height`` carry the physical output unit,
        so changing ``output_unit`` rescales the document without touching any path coordinate.
        """
        if not self.emit_viewbox:
            return None
        return f"0 0 {format_number(width_mm)} {format_number(height_mm)}"

    def _mm_per(self, unit: OutputUnit) -> float:
        if unit is OutputUnit.PX:
            # 1 px = 1 inch / dpi
            return 25.4 / self.dpi
        return _MM_PER_UNIT[unit]
