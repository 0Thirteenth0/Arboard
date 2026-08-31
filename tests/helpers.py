from __future__ import annotations

import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from src.artboard_cutter_core.units import mm_to_pt


FAILURE_ARTIFACT_DIR = Path("test_outputs") / "failures"


def make_grid_pdf(path: Path, width_mm=220, height_mm=120):
    doc = fitz.open()
    page = doc.new_page(width=mm_to_pt(width_mm), height=mm_to_pt(height_mm))
    shape = page.new_shape()
    shape.draw_rect(page.rect)
    shape.finish(color=(0, 0, 0), width=1)
    for x in range(0, int(width_mm) + 1, 20):
        shape.draw_line(fitz.Point(mm_to_pt(x), 0), fitz.Point(mm_to_pt(x), mm_to_pt(height_mm)))
    for y in range(0, int(height_mm) + 1, 20):
        shape.draw_line(fitz.Point(0, mm_to_pt(y)), fitz.Point(mm_to_pt(width_mm), mm_to_pt(y)))
    shape.finish(color=(0.2, 0.2, 0.2), width=0.2)
    shape.commit()
    doc.save(path)
    doc.close()


def make_color_stripe_pdf(path: Path, width_mm=200, height_mm=100):
    colors = [
        (0.80, 0.10, 0.10),
        (0.10, 0.60, 0.20),
        (0.10, 0.25, 0.85),
        (0.90, 0.70, 0.10),
    ]
    doc = fitz.open()
    page = doc.new_page(width=mm_to_pt(width_mm), height=mm_to_pt(height_mm))
    stripe_w = width_mm / len(colors)
    shape = page.new_shape()
    for idx, color in enumerate(colors):
        x0 = mm_to_pt(idx * stripe_w)
        x1 = mm_to_pt((idx + 1) * stripe_w)
        shape.draw_rect(fitz.Rect(x0, 0, x1, mm_to_pt(height_mm)))
        shape.finish(color=color, fill=color, width=0)
    shape.commit()
    doc.save(path)
    doc.close()


def make_multipage_pdf(path: Path, page_specs=None):
    specs = page_specs or [
        (100, 80, (0.85, 0.10, 0.10)),
        (120, 90, (0.10, 0.65, 0.20)),
        (140, 100, (0.10, 0.25, 0.85)),
    ]
    doc = fitz.open()
    for width_mm, height_mm, color in specs:
        page = doc.new_page(width=mm_to_pt(width_mm), height=mm_to_pt(height_mm))
        shape = page.new_shape()
        shape.draw_rect(page.rect)
        shape.finish(color=color, fill=color, width=0)
        shape.commit()
    doc.save(path)
    doc.close()


def make_rotated_pdf(path: Path, width_mm=120, height_mm=80, rotation=90):
    make_color_stripe_pdf(path, width_mm=width_mm, height_mm=height_mm)
    doc = fitz.open(path)
    page = doc.load_page(0)
    page.set_rotation(rotation)
    tmp = path.with_suffix(".rotated.tmp.pdf")
    doc.save(tmp)
    doc.close()
    tmp.replace(path)


def make_unusual_page_box_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page(width=mm_to_pt(240), height=mm_to_pt(160))
    crop = fitz.Rect(mm_to_pt(20), mm_to_pt(10), mm_to_pt(220), mm_to_pt(130))
    shape = page.new_shape()
    shape.draw_rect(page.rect)
    shape.finish(color=(0.85, 0.85, 0.85), fill=(0.85, 0.85, 0.85), width=0)
    shape.draw_rect(crop)
    shape.finish(color=(0.10, 0.25, 0.85), fill=(0.10, 0.25, 0.85), width=0)
    shape.commit()
    page.set_cropbox(crop)
    page.set_trimbox(crop)
    page.set_bleedbox(crop)
    doc.save(path)
    doc.close()


def make_layered_pdf(path: Path, width_mm=100, height_mm=60):
    """Create one visible and one default-hidden optional-content group."""
    doc = fitz.open()
    page = doc.new_page(width=mm_to_pt(width_mm), height=mm_to_pt(height_mm))
    visible = doc.add_ocg("Visible artwork", on=True)
    hidden = doc.add_ocg("Hidden do not print", on=False)
    midpoint = mm_to_pt(width_mm / 2)
    page.draw_rect(
        fitz.Rect(0, 0, midpoint, mm_to_pt(height_mm)),
        color=None,
        fill=(0.85, 0.10, 0.10),
        oc=visible,
    )
    page.draw_rect(
        fitz.Rect(midpoint, 0, mm_to_pt(width_mm), mm_to_pt(height_mm)),
        color=None,
        fill=(0.05, 0.15, 0.90),
        oc=hidden,
    )
    doc.save(path)
    doc.close()


def render_pdf_page_rgb(path: Path, dpi=96):
    doc = fitz.open(path)
    try:
        pix = doc.load_page(0).get_pixmap(dpi=dpi, alpha=False)
        return pix.width, pix.height, bytes(pix.samples)
    finally:
        doc.close()


def pixel_diff_stats(a, b):
    aw, ah, adata = a
    bw, bh, bdata = b
    if (aw, ah) != (bw, bh):
        raise AssertionError(f"Rendered sizes differ: {(aw, ah)} != {(bw, bh)}")
    if len(adata) != len(bdata):
        raise AssertionError(f"Rendered byte counts differ: {len(adata)} != {len(bdata)}")
    if not adata:
        return {"mean_abs": 0.0, "max_abs": 0, "different_ratio": 0.0}

    total = 0
    max_abs = 0
    different = 0
    for left, right in zip(adata, bdata, strict=True):
        delta = abs(left - right)
        total += delta
        max_abs = max(max_abs, delta)
        if delta:
            different += 1
    return {
        "mean_abs": total / len(adata),
        "max_abs": max_abs,
        "different_ratio": different / len(adata),
    }


def save_ppm_diff_artifact(name: str, a, b):
    aw, ah, adata = a
    bw, bh, bdata = b
    if (aw, ah) != (bw, bh):
        return None
    FAILURE_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    diff = bytearray()
    for left, right in zip(adata, bdata, strict=True):
        diff.append(min(255, abs(left - right) * 8))
    out = FAILURE_ARTIFACT_DIR / f"{name}.ppm"
    out.write_bytes(f"P6\n{aw} {ah}\n255\n".encode("ascii") + bytes(diff))
    return out


def require_tk_root(testcase):
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        return root
    except Exception as exc:
        testcase.skipTest(f"Tk unavailable for interactive GUI smoke tests: {exc}")


def is_windows() -> bool:
    return sys.platform.startswith("win")
