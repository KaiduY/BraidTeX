from .core import Braid, Configuration, ConfigurationNode, Crossing, parse_config
from .render import render_svg
from .transform import render_braid, transform_tex

__version__ = "0.1.0"

__all__ = [
    "Braid",
    "Configuration",
    "ConfigurationNode",
    "Crossing",
    "parse_config",
    "render_svg",
    "render_braid",
    "transform_tex",
    "__version__",
]

try:
    from . import braidtex as braidtex  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    braidtex = None
