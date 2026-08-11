#!/usr/bin/env python3
"""
Artboard Cutter â€” STABLE ROLLBACK (Raster-only, nonâ€‘uniform scaling + clean crops)

This version restores the working behavior:
  â€¢ Nonâ€‘uniformly scale the *entire* first page to (sum(widths)+2b) Ã— (h+2b)
  â€¢ Slice into artboards using a fresh inâ€‘memory doc per crop + clip rectangle
  â€¢ Force page boxes; optional edge hairline for visual checks

Usage:
  python artboard_cutter.py input.pdf --b 20 --h 1200 --widths 1000 1000 400 400 -o ./out --dpi 300 --log-transform --draw-edges

Notes:
  â€¢ Units for --b, --h, and --widths are millimetres.
  â€¢ .ai files must be PDFâ€‘compatible (or export to PDF first).
  â€¢ Increase --dpi (e.g., 600) for sharper output.
"""

#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

PT_PER_MM = 72.0 / 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM


def pt_to_mm(pt: float) -> float:
    return pt / PT_PER_MM


def _force_page_boxes(page: fitz.Page) -> None:
    """Force all PDF boxes to the page rect."""
    r = page.rect
    for name in ("set_mediabox", "set_cropbox", "set_bleedbox", "set_trimbox", "set_artbox"):
        setter = getattr(page, name, None)
        if callable(setter):
            try:
                setter(r)
            except Exception:
                pass


def _draw_hairline_border(page: fitz.Page) -> None:
    """Draw a 0.1 pt rectangle exactly on the page edges for visual verification."""
    try:
        shape = page.new_shape()
        r = page.rect
        shape.draw_rect(r)
        shape.finish(color=(0, 0, 0), width=0.1, fill=None)
        shape.commit()
    except Exception:
        pass


def scale_page_raster(src_doc: fitz.Document, target_w_pt: float, target_h_pt: float,
                      dpi: int, log: bool) -> bytes:
    """
    Rasterize the source first page and place it to fill the target page size exactly.
    Returns the bytes of a single-page PDF at (target_w_pt Ã— target_h_pt).
    """
    src_page = src_doc.load_page(0)
    src_rect = src_page.rect

    # Pixel dims to render at requested DPI
    target_w_in = target_w_pt / 72.0
    target_h_in = target_h_pt / 72.0
    px_w = max(1, int(target_w_in * dpi))
    px_h = max(1, int(target_h_in * dpi))

    # Matrix so pixmap roughly matches desired pixels
    sx = px_w / src_rect.width
    sy = px_h / src_rect.height
    pix = src_page.get_pixmap(matrix=fitz.Matrix(sx, sy), alpha=False)

    if log:
        print(f"[RASTER] render target px: {px_w}Ã—{px_h}  matrix sx={sx:.6f} sy={sy:.6f}")

    # Build 1-page PDF and stretch the raster to fill page (no aspect lock)
    out_doc = fitz.open()
    out_page = out_doc.new_page(width=target_w_pt, height=target_h_pt)
    out_page.insert_image(out_page.rect, pixmap=pix, keep_proportion=False)
    _force_page_boxes(out_page)

    pdf_bytes = out_doc.tobytes()
    out_doc.close()
    return pdf_bytes


def export_artboard_crops_from_scaled_pdf_bytes(
    scaled_pdf_bytes: bytes,
    widths_mm: list[float],
    height_mm: float,
    bleed_mm: float,
    base_name: str,
    outdir: Path,
    log: bool,
    draw_edges: bool,
    dpi: int = 300,
) -> None:
    """
    Crop the scaled master by rasterizing only the desired region for each artboard,
    and place it 1:1 onto an output page of the same size.
    """
    total_h_pt = mm_to_pt(height_mm + 2 * bleed_mm)

    # Open scaled master once per crop to avoid PyMuPDF internal handle issues
    cum_x_mm = 0.0
    for idx, w_mm in enumerate(widths_mm):
        x0_pt = mm_to_pt(cum_x_mm)
        x1_pt = mm_to_pt(cum_x_mm + w_mm + 2 * bleed_mm)
        clip_rect = fitz.Rect(x0_pt, 0.0, x1_pt, total_h_pt)

        # Output page exactly equals clip size â†’ 1:1 mapping, no fitting
        out = fitz.open()
        out_page = out.new_page(width=clip_rect.width, height=clip_rect.height)
        _force_page_boxes(out_page)

        # Rasterize only the clip
        src_once = fitz.open("pdf", scaled_pdf_bytes)
        try:
            sp = src_once.load_page(0)
            pix = sp.get_pixmap(clip=clip_rect, dpi=dpi, alpha=False)
        finally:
            try:
                src_once.close()
            except Exception:
                pass

        # Place pixmap to fill page exactly
        out_page.insert_image(out_page.rect, pixmap=pix, keep_proportion=False)

        if draw_edges:
            _draw_hairline_border(out_page)

        out_name = f"{base_name}_{idx+1}.pdf"
        out.save(outdir / out_name)
        out.close()

        if log:
            print(
                f"[CROP] {out_name}: x=[{pt_to_mm(x0_pt):.3f},{pt_to_mm(x1_pt):.3f}] mm  "
                f"w={pt_to_mm(clip_rect.width):.3f} mm  h={pt_to_mm(clip_rect.height):.3f} mm"
            )
        else:
            print(f"Exported {out_name}")

        cum_x_mm += w_mm


def parse_args():
    p = argparse.ArgumentParser(description="Raster scale + artboard crop exporter")
    p.add_argument("input", help="Input PDF or AI (PDF-compatible)")
    p.add_argument("--b", "--bleed", dest="bleed_mm", type=float, required=True, help="Bleed in mm")
    p.add_argument("--h", "--height", dest="height_mm", type=float, required=True, help="Artboard height in mm (content)")
    p.add_argument("--widths", nargs='+', type=float, required=True, help="Artboard widths in mm (content)")
    p.add_argument("-o", "--outdir", default="./out", help="Output directory")
    p.add_argument("--dpi", type=int, default=300, help="Raster DPI for scaling and crops (default 300)")
    p.add_argument("--log-transform", action="store_true", help="Print debug info")
    p.add_argument("--draw-edges", action="store_true", help="Draw a 0.1pt border on outputs")
    return p.parse_args()


def main():
    args = parse_args()

    in_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    widths_mm = args.widths
    bleed_mm = float(args.bleed_mm)
    height_mm = float(args.height_mm)

    target_w_pt = mm_to_pt(sum(widths_mm) + 2 * bleed_mm)
    target_h_pt = mm_to_pt(height_mm + 2 * bleed_mm)

    print(f"Input: {in_path.name}")
    print(f"Bleed: {bleed_mm:.1f} mm   Height: {height_mm:.1f} mm   Artboards: {len(widths_mm)}")
    print(f"Widths: {widths_mm} mm  â†’ total content width: {sum(widths_mm):.1f} mm")
    print(f"Target full size (with outer bleeds): {pt_to_mm(target_w_pt):.1f} Ã— {pt_to_mm(target_h_pt):.1f} mm")
    print(f"Output dir: {outdir}")

    # Open source
    src = fitz.open(in_path)
    try:
        scaled_pdf_bytes = scale_page_raster(src, target_w_pt, target_h_pt, dpi=args.dpi, log=args.log_transform)
    finally:
        try:
            src.close()
        except Exception:
            pass

    export_artboard_crops_from_scaled_pdf_bytes(
        scaled_pdf_bytes,
        widths_mm,
        height_mm,
        bleed_mm,
        in_path.stem,
        outdir,
        log=args.log_transform,
        draw_edges=args.draw_edges,
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()
