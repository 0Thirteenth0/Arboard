PT_PER_MM = 72.0 / 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM


def pt_to_mm(pt: float) -> float:
    return pt / PT_PER_MM


def compute_scale_matrix(src_rect, target_w_pt: float, target_h_pt: float) -> tuple[float, float]:
    sx = target_w_pt / float(src_rect.width)
    sy = target_h_pt / float(src_rect.height)
    return sx, sy


def estimate_pixels(w_pt: float, h_pt: float, dpi: int) -> float:
    w_in = w_pt / 72.0
    h_in = h_pt / 72.0
    return (w_in * dpi) * (h_in * dpi)


def preview_render_scale(max_dimension_pt: float, max_pixels: int = 1600, max_scale: float = 2.0) -> float:
    """Scale a preview so its longest side never exceeds the pixel budget."""
    dimension = float(max_dimension_pt)
    if dimension <= 0:
        return 1.0
    return min(float(max_scale), max(1.0 / dimension, float(max_pixels) / dimension))


def fmt_mm(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.3f}".rstrip("0").rstrip(".")
