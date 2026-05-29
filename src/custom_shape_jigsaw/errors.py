"""Exception types raised by the custom-shape-jigsaw library."""

from __future__ import annotations


class JigsawError(Exception):
    """Base class for all errors raised by this library."""


class BorderParseError(JigsawError):
    """Raised when a custom-border SVG cannot be parsed or contains no usable geometry."""


class TooLargeError(JigsawError):
    """Raised when ``rows * cols`` exceeds the configured ``max_cells`` guard.

    The original JS prompts the user to confirm; headless code raises instead.
    """


class ConfigError(JigsawError):
    """Raised when a :class:`~custom_shape_jigsaw.config.JigsawConfig` is invalid."""
