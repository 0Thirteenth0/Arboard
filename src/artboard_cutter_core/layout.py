from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PanelLayout:
    index: int
    outer_left: float
    outer_right: float
    content_left: float
    content_right: float
    width: float

    @property
    def outer_width(self) -> float:
        return self.outer_right - self.outer_left

    def to_legacy_dict(self) -> dict[str, float]:
        return {
            "outer_left": self.outer_left,
            "outer_right": self.outer_right,
            "content_left": self.content_left,
            "content_right": self.content_right,
            "width": self.width,
        }


def parse_widths_list(s: str) -> list[float]:
    chunks = [c.strip() for c in s.replace(",", " ").split() if c.strip()]
    widths = [float(c) for c in chunks]
    if any(not math.isfinite(width) for width in widths):
        raise ValueError("Panel widths must contain only finite numbers.")
    return widths


def split_last_panel_width(widths_mm: list[float] | tuple[float, ...]) -> list[float]:
    """Append one panel by splitting the last panel without changing total width."""
    widths = [float(w) for w in widths_mm]
    if not widths:
        raise ValueError("At least one panel width is required.")
    if any(not math.isfinite(width) or width <= 0 for width in widths):
        raise ValueError("Panel widths must contain one or more positive finite numbers.")
    half = widths[-1] * 0.5
    return widths[:-1] + [half, half]


def redistribute_panel_widths(total_width_mm: float, panel_count: int) -> list[float]:
    """Divide a content width evenly while preserving the exact floating-point total."""
    total = float(total_width_mm)
    count = int(panel_count)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Total artwork width must be a positive finite number.")
    if count < 1:
        raise ValueError("Panel count must be at least 1.")
    width = total / count
    widths = [width] * count
    # Put any floating-point remainder in the final panel so sum(widths) stays exact.
    widths[-1] = total - sum(widths[:-1])
    return widths


def add_evenly_distributed_panel(widths_mm: list[float] | tuple[float, ...]) -> list[float]:
    """Add one panel and redistribute the complete artwork width evenly."""
    widths = [float(width) for width in widths_mm]
    if not widths or any(not math.isfinite(width) or width <= 0 for width in widths):
        raise ValueError("Panel widths must contain one or more positive finite numbers.")
    return redistribute_panel_widths(sum(widths), len(widths) + 1)


def resize_adjacent_panel_widths(
    widths_mm: list[float] | tuple[float, ...],
    edge_index: int,
    delta_mm: float,
    *,
    min_width_mm: float = 1.0,
    clamp: bool = True,
) -> list[float]:
    """
    Move the boundary between two adjacent panels while preserving total width.

    edge_index is the zero-based internal edge between widths[edge_index] and
    widths[edge_index + 1]. Positive delta increases the left panel and
    decreases the right panel.
    """
    widths = [float(w) for w in widths_mm]
    if len(widths) < 2:
        raise ValueError("At least two panel widths are required.")
    if any(not math.isfinite(width) or width <= 0 for width in widths):
        raise ValueError("Panel widths must contain only positive finite numbers.")
    if edge_index < 0 or edge_index >= len(widths) - 1:
        raise IndexError("edge_index must reference an internal panel edge.")
    min_width = float(min_width_mm)
    requested_delta = float(delta_mm)
    if not math.isfinite(min_width) or not math.isfinite(requested_delta):
        raise ValueError("Panel resize values must be finite numbers.")
    min_width = max(0.01, min_width)
    left = widths[edge_index]
    right = widths[edge_index + 1]
    if min_width * 2 > left + right:
        raise ValueError("Minimum panel width is too large for this panel pair.")

    min_delta = min_width - left
    max_delta = right - min_width
    if not clamp and (requested_delta < min_delta or requested_delta > max_delta):
        return widths
    delta = min(max(requested_delta, min_delta), max_delta)
    widths[edge_index] = left + delta
    widths[edge_index + 1] = right - delta
    return widths


def compute_panel_layout(
    widths_mm: list[float] | tuple[float, ...],
    bleed_mm: float,
    overlap_mm: float,
    overlap_mode: str = "shared",
) -> tuple[list[PanelLayout], float, float]:
    """
    Build per-panel horizontal extents.

    Rules preserved from the legacy GUI:
    - bleed exists only on the outside edges of the full assembled artwork
    - shared mode: internal overlap is shared equally by neighboring panels
    - left mode: each panel after the first extends left by the full overlap
    - total width is content width plus outside bleed, not repeated per panel
    """
    bleed_value = float(bleed_mm)
    overlap_value = float(overlap_mm)
    if not math.isfinite(bleed_value) or not math.isfinite(overlap_value):
        raise ValueError("Bleed and overlap must be finite numbers.")
    bleed_eff = max(0.0, bleed_value)
    widths = [float(w) for w in widths_mm]
    if any(not math.isfinite(width) or width <= 0 for width in widths):
        raise ValueError("Panel widths must contain only positive finite numbers.")
    mode = (overlap_mode or "shared").strip().lower().replace(" ", "_").replace("-", "_")
    if mode in {"left", "left_overlap", "left_only"}:
        mode = "left"
    else:
        mode = "shared"

    if not widths:
        overlap_eff = max(0.0, overlap_value)
        return [], 2 * bleed_eff, overlap_eff

    overlap_eff = max(0.0, overlap_value)
    min_w = min(widths)
    if overlap_eff >= min_w:
        overlap_eff = max(0.0, min_w - 0.01)

    layout: list[PanelLayout] = []
    cursor = bleed_eff

    for idx, width in enumerate(widths):
        content_left = cursor
        content_right = cursor + width

        if mode == "left":
            # Left-overlap mode keeps the preceding panel's right edge at its
            # content edge. The next panel carries the entire internal overlap
            # back over the previous panel. The first panel has no overlap.
            outer_left = content_left - (bleed_eff if idx == 0 else overlap_eff)
            outer_right = content_right + (bleed_eff if idx == len(widths) - 1 else 0.0)
        else:
            overlap_half = overlap_eff * 0.5
            outer_left = content_left - (bleed_eff if idx == 0 else overlap_half)
            outer_right = content_right + (bleed_eff if idx == len(widths) - 1 else overlap_half)

        layout.append(
            PanelLayout(
                index=idx + 1,
                outer_left=max(0.0, outer_left),
                outer_right=max(outer_left, outer_right),
                content_left=content_left,
                content_right=content_right,
                width=width,
            )
        )
        cursor = content_right

    return layout, layout[-1].outer_right, overlap_eff


def compute_preview_page_height(
    total_width_mm: float,
    height_mm: float,
    bleed_mm: float,
    preserve_vectors: bool,
    fit_mode: str,
    source_width_mm: float | None,
    source_height_mm: float | None,
) -> float:
    total_width = float(total_width_mm)
    height = float(height_mm)
    bleed = float(bleed_mm)
    if any(not math.isfinite(value) for value in (total_width, height, bleed)):
        raise ValueError("Preview dimensions must be finite numbers.")
    if preserve_vectors and fit_mode == "width" and source_width_mm and source_height_mm and source_width_mm > 0:
        source_width = float(source_width_mm)
        source_height = float(source_height_mm)
        if not math.isfinite(source_width) or not math.isfinite(source_height):
            raise ValueError("Source dimensions must be finite numbers.")
        return (total_width / source_width) * source_height
    return height + 2 * max(0.0, bleed)
