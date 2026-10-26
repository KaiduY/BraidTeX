"""BraidTeX - braid diagrams for mathematical writing."""
from __future__ import annotations

from .cache import Asset, Cache, cache_key
from .config import Node, parse_config, unlabeled
from .errors import (BraidTeXError, BraidValidationError, BuildError, ConfigSyntaxError,
                     IncompatibleBoundaryError, TransformError)
from .geometry import build_geometry, count_intersections
from .layout import normalized_positions
from .model import Axis, Braid, Crossing, Loop, LoopEvent, Point, SURFACES, parse_generator
from .render import render_standalone, render_svg, render_tikz
from .style import Style

__version__ = "0.5.0"

__all__ = ["Loop", "LoopEvent", "SURFACES", "parse_generator", "Braid", "Axis", "Point", "Crossing", "Style", "Node", "parse_config", "unlabeled",
           "normalized_positions", "build_geometry", "count_intersections", "render_tikz",
           "render_standalone", "render_svg", "Cache", "Asset", "cache_key", "BraidTeXError",
           "BraidValidationError", "IncompatibleBoundaryError", "ConfigSyntaxError",
           "TransformError", "BuildError", "__version__"]
