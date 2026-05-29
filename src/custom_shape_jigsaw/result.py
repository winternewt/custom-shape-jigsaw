"""Result object returned by the generation functions."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class JigsawResult(BaseModel):
    """The generated jigsaw, as two SVG documents plus geometry metadata.

    ``display_svg`` uses unit-less ``width``/``height`` (browser preview style); ``save_svg``
    carries a ``viewBox`` plus unit-suffixed ``width``/``height`` for cutting/printing.
    Coordinates are expressed in ``scale_model.output_unit``.
    """

    model_config = ConfigDict(frozen=True)

    display_svg: str
    save_svg: str
    width: float
    height: float
    piece_count: int
    rows: int
    cols: int

    def write_save(self, path: str | Path) -> Path:
        """Write the cutting/printing SVG to ``path``; returns the resolved path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.save_svg, encoding="utf-8")
        logger.info("Wrote save SVG to %s (%d pieces, %gx%g)", out, self.piece_count,
                    self.width, self.height)
        return out

    def write_display(self, path: str | Path) -> Path:
        """Write the preview SVG to ``path``; returns the resolved path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.display_svg, encoding="utf-8")
        logger.info("Wrote display SVG to %s", out)
        return out
