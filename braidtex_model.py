"""Reusable geometric/model primitives for composable BraidTeX diagrams.

Coordinates are in centimetres. Strand identifiers are persistent 1-based input
identities; ``level`` counts Artin generators from the top (0..len(word)).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence
import math


def _finite_positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 if allow_zero else value <= 0:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {relation}")
    return float(value)


@dataclass(frozen=True)
class Separator:
    """A horizontal separator at a generator boundary.

    ``ticks`` are absolute x-coordinates. ``tick_ports`` instead select 1-based
    left-to-right ports at this level, so they follow the automatic layout.
    The two representations may not be mixed in one separator.
    """
    level: int
    ticks: tuple[float, ...] = ()
    style: str = "densely dotted"
    line_width: float = 0.45
    offset_down: float = 0.0
    tick_ports: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.level, int) or self.level < 0:
            raise ValueError("Separator level must be a non-negative integer")
        object.__setattr__(self, "ticks", tuple(float(x) for x in self.ticks))
        object.__setattr__(self, "tick_ports", tuple(int(x) for x in self.tick_ports))
        if not all(math.isfinite(x) for x in self.ticks):
            raise ValueError("Separator ticks must be finite coordinates")
        if self.ticks and self.tick_ports:
            raise ValueError("Use separator ticks or tick_ports, not both")
        if any(port < 1 for port in self.tick_ports):
            raise ValueError("Separator tick_ports are 1-based positive positions")
        object.__setattr__(self, "line_width", _finite_positive(self.line_width, "separator line_width"))
        object.__setattr__(self, "offset_down", _finite_positive(self.offset_down, "separator offset_down", allow_zero=True))


@dataclass(frozen=True)
class CoordinateFrame:
    """Optional coordinate frame independent of braid topology.

    Tick positions are explicit x-coordinates; endpoints are not ticked unless
    requested. ``separators`` are shared-level separators with optional ticks.
    """
    top_axis: bool = True
    bottom_axis: bool = True
    left_axis: bool = True
    right_boundary: bool = True
    top_ticks: tuple[float, ...] = ()
    bottom_ticks: tuple[float, ...] = ()
    top_tick_ports: tuple[int, ...] = ()
    bottom_tick_ports: tuple[int, ...] = ()
    axis_color: str = "black"
    axis_width: float = 0.8
    tick_half_height: float = 0.09
    boundary_style: str = "gray!65,densely dotted"
    boundary_width: float = 0.45
    separators: tuple[Separator, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "top_ticks", tuple(float(x) for x in self.top_ticks))
        object.__setattr__(self, "bottom_ticks", tuple(float(x) for x in self.bottom_ticks))
        object.__setattr__(self, "top_tick_ports", tuple(int(x) for x in self.top_tick_ports))
        object.__setattr__(self, "bottom_tick_ports", tuple(int(x) for x in self.bottom_tick_ports))
        for name in ("top_ticks", "bottom_ticks"):
            if not all(math.isfinite(x) for x in getattr(self, name)):
                raise ValueError(f"{name} must contain finite coordinates")
        if self.top_ticks and self.top_tick_ports:
            raise ValueError("Use top_ticks or top_tick_ports, not both")
        if self.bottom_ticks and self.bottom_tick_ports:
            raise ValueError("Use bottom_ticks or bottom_tick_ports, not both")
        if any(p < 1 for p in (*self.top_tick_ports, *self.bottom_tick_ports)):
            raise ValueError("Frame tick ports are 1-based positive positions")
        object.__setattr__(self, "axis_width", _finite_positive(self.axis_width, "frame axis_width"))
        object.__setattr__(self, "tick_half_height", _finite_positive(self.tick_half_height, "tick_half_height", allow_zero=True))
        object.__setattr__(self, "boundary_width", _finite_positive(self.boundary_width, "boundary_width"))
        separators: list[Separator] = []
        for item in self.separators:
            if isinstance(item, Separator):
                separators.append(item)
            elif isinstance(item, dict):
                separators.append(Separator(**item))
            else:
                raise TypeError("frame separators must be Separator instances or mappings")
        object.__setattr__(self, "separators", tuple(separators))


@dataclass(frozen=True)
class Connector:
    """Horizontal connector between persistent strand identities at a level.

    Intervening strands do not acquire nodes. The connector is an annotation,
    not a braid crossing, so it does not affect permutation or braid word.
    """
    strand_a: int
    strand_b: int
    level: int = 0
    color: str = "black"
    line_width: float = 0.75
    node_radius: float = 0.045
    nodes: bool = True
    visible: bool = True
    name: str | None = None
    offset_down: float = 0.0
    layer: str = "back"

    def __post_init__(self) -> None:
        if not isinstance(self.strand_a, int) or self.strand_a < 1:
            raise ValueError("Connector strand_a must be a positive 1-based strand identity")
        if not isinstance(self.strand_b, int) or self.strand_b < 1:
            raise ValueError("Connector strand_b must be a positive 1-based strand identity")
        if self.strand_a == self.strand_b:
            raise ValueError("A connector must join two distinct strand identities")
        if not isinstance(self.level, int) or self.level < 0:
            raise ValueError("Connector level must be a non-negative integer")
        object.__setattr__(self, "line_width", _finite_positive(self.line_width, "connector line_width"))
        object.__setattr__(self, "node_radius", _finite_positive(self.node_radius, "connector node_radius", allow_zero=True))
        object.__setattr__(self, "offset_down", _finite_positive(self.offset_down, "connector offset_down", allow_zero=True))
        if self.layer not in ("back", "front"):
            raise ValueError("Connector layer must be 'back' or 'front'")


@dataclass(frozen=True)
class AuxiliaryPath:
    """A non-topological dotted trajectory or path annotation.

    Supply absolute ``points`` in diagram coordinates, or ``follow_strand`` to
    draw a smooth approximation alongside that persistent strand identity.
    Auxiliary paths never affect braid topology.
    """
    points: tuple[tuple[float, float], ...] = ()
    style: str = "densely dotted"
    color: str = "black"
    line_width: float = 0.65
    follow_strand: int | None = None
    offset: float = 0.14
    start_level: int = 0
    end_level: int | None = None
    visible: bool = True

    def __post_init__(self) -> None:
        pts = tuple((float(p[0]), float(p[1])) for p in self.points)
        if any(not math.isfinite(x) or not math.isfinite(y) for x, y in pts):
            raise ValueError("Auxiliary path coordinates must be finite")
        if pts and len(pts) < 2:
            raise ValueError("An explicit auxiliary path needs at least two points")
        if not pts and self.follow_strand is None:
            raise ValueError("AuxiliaryPath needs points or follow_strand")
        object.__setattr__(self, "points", pts)
        object.__setattr__(self, "line_width", _finite_positive(self.line_width, "auxiliary line_width"))
        if not isinstance(self.offset, (int, float)) or not math.isfinite(self.offset):
            raise ValueError("Auxiliary path offset must be finite")
        if self.follow_strand is not None and (not isinstance(self.follow_strand, int) or self.follow_strand < 1):
            raise ValueError("follow_strand must be a positive 1-based strand identity")
        if not isinstance(self.start_level, int) or self.start_level < 0:
            raise ValueError("start_level must be a non-negative integer")
        if self.end_level is not None and (not isinstance(self.end_level, int) or self.end_level < self.start_level):
            raise ValueError("end_level must be >= start_level")


@dataclass(frozen=True)
class Region:
    """Named vertical region bounded by two generator levels."""
    start_level: int
    end_level: int
    label: str
    side: str = "left"
    offset: float = 0.48
    color: str = "black"
    line_width: float = 0.65
    start_offset: float = 0.0
    end_offset: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.start_level, int) or not isinstance(self.end_level, int):
            raise ValueError("Region levels must be integers")
        if self.start_level < 0 or self.end_level < self.start_level:
            raise ValueError("Region requires 0 <= start_level <= end_level")
        if self.start_level == self.end_level and self.end_offset <= self.start_offset:
            raise ValueError("A same-level region needs end_offset > start_offset")
        if self.side not in ("left", "right"):
            raise ValueError("Region side must be 'left' or 'right'")
        object.__setattr__(self, "offset", _finite_positive(self.offset, "region offset"))
        object.__setattr__(self, "line_width", _finite_positive(self.line_width, "region line_width"))
        object.__setattr__(self, "start_offset", _finite_positive(self.start_offset, "region start_offset", allow_zero=True))
        object.__setattr__(self, "end_offset", _finite_positive(self.end_offset, "region end_offset", allow_zero=True))


def coerce_separator(value: Any) -> Separator:
    if isinstance(value, Separator):
        return value
    if isinstance(value, dict):
        return Separator(**value)
    if isinstance(value, (tuple, list)) and len(value) >= 1:
        return Separator(int(value[0]), tuple(value[1]) if len(value) > 1 else ())
    raise TypeError("Expected Separator, mapping, or (level[, ticks])")


def coerce_frame(value: CoordinateFrame | dict[str, Any] | None) -> CoordinateFrame | None:
    if value is None or isinstance(value, CoordinateFrame):
        return value
    if isinstance(value, dict):
        return CoordinateFrame(**value)
    raise TypeError("frame must be a CoordinateFrame, mapping, or None")


def coerce_connector(value: Connector | dict[str, Any] | Sequence[Any]) -> Connector:
    if isinstance(value, Connector):
        return value
    if isinstance(value, dict):
        return Connector(**value)
    if isinstance(value, (tuple, list)) and 3 <= len(value) <= 5:
        kwargs: dict[str, Any] = {"strand_a": value[0], "strand_b": value[1], "level": value[2]}
        if len(value) >= 4:
            kwargs["color"] = value[3]
        if len(value) == 5:
            kwargs["nodes"] = value[4]
        return Connector(**kwargs)
    raise TypeError("Connector must be Connector, mapping, or (strand_a, strand_b, level[, color[, nodes]])")


def coerce_auxiliary_path(value: AuxiliaryPath | dict[str, Any]) -> AuxiliaryPath:
    if isinstance(value, AuxiliaryPath):
        return value
    if isinstance(value, dict):
        return AuxiliaryPath(**value)
    raise TypeError("Auxiliary path must be AuxiliaryPath or mapping")


def coerce_region(value: Region | dict[str, Any] | Sequence[Any]) -> Region:
    if isinstance(value, Region):
        return value
    if isinstance(value, dict):
        return Region(**value)
    if isinstance(value, (tuple, list)) and 3 <= len(value) <= 4:
        return Region(value[0], value[1], value[2], *(value[3:]))
    raise TypeError("Region must be Region, mapping, or (start_level, end_level, label[, side])")
