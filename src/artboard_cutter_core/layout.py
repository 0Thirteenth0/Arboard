from __future__ import annotations

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
    return [float(c) for c in chunks]


def split_last_panel_width(widths_mm: list[float] | tuple[float, ...]) -> list[float]:
    """Append one panel by splitting the last panel without changing total width."""
    widths = [float(w) for w in widths_mm]
    if not widths:
        raise ValueError("At least one panel width is required.")
    if widths[-1] <= 0:
        raise ValueError("Last panel width must be greater than 0.")
    half = widths[-1] * 0.5
    return widths[:-1] + [half, half]


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
    if edge_index < 0 or edge_index >= len(widths) - 1:
        raise IndexError("edge_index must reference an internal panel edge.")
    min_width = max(0.01, float(min_width_mm))
    left = widths[edge_index]
    right = widths[edge_index + 1]
    if left <= 0 or right <= 0:
        raise ValueError("Panel widths must be greater than 0.")

    min_delta = min_width - left
    max_delta = right - min_width
    requested_delta = float(delta_mm)
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
    bleed_eff = max(0.0, float(bleed_mm))
    widths = [float(w) for w in widths_mm]
    mode = (overlap_mode or "shared").strip().lower().replace(" ", "_").replace("-", "_")
    if mode in {"left", "left_overlap", "left_only"}:
        mode = "left"
    else:
        mode = "shared"

    if not widths:
        overlap_eff = max(0.0, float(overlap_mm))
        return [], 2 * bleed_eff, overlap_eff

    overlap_eff = max(0.0, float(overlap_mm))
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
    if preserve_vectors and fit_mode == "width" and source_width_mm and source_height_mm and source_width_mm > 0:
        return (total_width_mm / source_width_mm) * source_height_mm
    return height_mm + 2 * max(0.0, float(bleed_mm))
