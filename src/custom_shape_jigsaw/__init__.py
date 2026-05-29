"""Headless Python port of the CustomShapeJigsawJs procedural jigsaw generator.

Public entry points::

    from custom_shape_jigsaw import generate_jigsaw, generate_jigsaw_sync, JigsawConfig

See :mod:`custom_shape_jigsaw.api` for the async/sync generation functions and
:mod:`custom_shape_jigsaw.config` for the configuration model.
"""

from __future__ import annotations

from custom_shape_jigsaw.api import generate_jigsaw as generate_jigsaw
from custom_shape_jigsaw.api import generate_jigsaw_sync as generate_jigsaw_sync
from custom_shape_jigsaw.config import BorderMode as BorderMode
from custom_shape_jigsaw.config import JigsawConfig as JigsawConfig
from custom_shape_jigsaw.config import TabSizeMode as TabSizeMode
from custom_shape_jigsaw.errors import BorderParseError as BorderParseError
from custom_shape_jigsaw.errors import ConfigError as ConfigError
from custom_shape_jigsaw.errors import JigsawError as JigsawError
from custom_shape_jigsaw.errors import TooLargeError as TooLargeError
from custom_shape_jigsaw.result import JigsawResult as JigsawResult
from custom_shape_jigsaw.units import OutputUnit as OutputUnit
from custom_shape_jigsaw.units import ScaleModel as ScaleModel
