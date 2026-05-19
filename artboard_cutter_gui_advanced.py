#!/usr/bin/env python3
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    BaseTk = tk.Tk
    DND_AVAILABLE = False
    DND_FILES = None

import fitz  # PyMuPDF

# --- TIFF / JPG helpers via Pillow (NO TiffImagePlugin usage) ---
try:
    from PIL import Image
    PIL_AVAILABLE = True
    try:
        Image.MAX_IMAGE_PIXELS = None  # allow very large images
    except Exception:
        pass
except Exception:
    PIL_AVAILABLE = False

# Optional: ImageTk for drawing preview images on Canvas
try:
    from PIL import ImageTk  # type: ignore
    IMAGE_TK_AVAILABLE = True
except Exception:
    IMAGE_TK_AVAILABLE = False

def pixmap_to_pil(pix):
    """Convert a PyMuPDF Pixmap to a Pillow Image, forcing RGB (drop alpha)."""
    if pix.alpha:
        im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        return im.convert("RGB")
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

def _save_tiff_with_retries(im, out_path, dpi_int: int, log_cb=None):
    """
    Save a Pillow image as TIFF robustly, without importing TiffImagePlugin:
      - Force RGB/L
      - Try BigTIFF first, then normal TIFF
      - Try multiple compressions
      - Always write DPI
    """
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")

    compressions = [
        ("tiff_lzw", {"compression": "tiff_lzw"}),
        ("tiff_adobe_deflate", {"compression": "tiff_adobe_deflate"}),
        ("tiff_deflate", {"compression": "tiff_deflate"}),
        ("packbits", {"compression": "packbits"}),
        ("uncompressed", {}),
    ]

    last_err = None
    for big in (True, False):  # try BigTIFF first
        for label, extra in compressions:
            kwargs = dict(extra)
            kwargs["dpi"] = (dpi_int, dpi_int)
            if big:
                kwargs["bigtiff"] = True  # some Pillow builds may not accept; we catch TypeError

            try:
                im.save(str(out_path), format="TIFF", **kwargs)
                if log_cb:
                    log_cb(f"[TIFF] saved with {label}{' + BigTIFF' if big else ''}")
                return
            except TypeError as e:
                # If Pillow doesn't accept 'bigtiff', continue without it on later attempts
                if "bigtiff" in str(e).lower():
                    continue
                last_err = e
                if log_cb:
                    log_cb(f"[TIFF] retry ({label}{' + BigTIFF' if big else ''}) failed: {e}")
            except Exception as e:
                last_err = e
                if log_cb:
                    log_cb(f"[TIFF] retry ({label}{' + BigTIFF' if big else ''}) failed: {e}")

    raise last_err

def _save_jpg_with_dpi(im, out_path, dpi_int: int):
    """Save JPEG with explicit DPI and high quality (no chroma subsampling)."""
    if im.mode != "RGB":
        im = im.convert("RGB")
    im.save(
        str(out_path),
        format="JPEG",
        quality=95,
        subsampling=0,
        dpi=(dpi_int, dpi_int),
        optimize=True,
    )

def save_raster_pil(im, out_path, fmt_lower: str, dpi_int: int, log_cb=None):
    """
    Save via Pillow with DPI for JPG / TIFF; generic save for PNG, etc.
    """
    fmt_lower = (fmt_lower or "pdf").lower()
    if fmt_lower in ("jpg", "jpeg"):
        _save_jpg_with_dpi(im, out_path, dpi_int)
        return
    if fmt_lower in ("tif", "tiff"):
        if not PIL_AVAILABLE:
            raise RuntimeError("TIFF export requires Pillow. Install with: pip install Pillow")
        _save_tiff_with_retries(im, out_path, dpi_int, log_cb)
        return
    # default: try Pillow's generic save with DPI if supported
    try:
        im.save(str(out_path), dpi=(dpi_int, dpi_int))
    except Exception:
        im.save(str(out_path))


# ---------------------- Units & helpers ----------------------
PT_PER_MM = 72.0 / 25.4
MAX_MP = 150  # safety cap per render in megapixels (per panel)

def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM

def pt_to_mm(pt: float) -> float:
    return pt / PT_PER_MM

def force_page_boxes(page):
    r = page.rect
    for name in ("set_mediabox", "set_cropbox", "set_bleedbox", "set_trimbox", "set_artbox"):
        setter = getattr(page, name, None)
        if callable(setter):
            try:
                setter(r)
            except Exception:
                pass

def open_pdf_robust(p: Path):
    try:
        return fitz.open(str(p))
    except Exception:
        pass
    try:
        return fitz.open(p.as_posix())
    except Exception:
        pass
    try:
        with open(p, "rb") as fh:
            filetype = p.suffix.lstrip(".").lower() or "pdf"
            return fitz.open(stream=fh.read(), filetype=filetype)
    except Exception:
        pass
    raise RuntimeError("Failed to open stream or unsupported format")

def compute_scale_matrix(src_rect, target_w_pt, target_h_pt):
    sx = target_w_pt / float(src_rect.width)
    sy = target_h_pt / float(src_rect.height)
    return sx, sy

def estimate_pixels(w_pt, h_pt, dpi):
    w_in = w_pt / 72.0
    h_in = h_pt / 72.0
    return (w_in * dpi) * (h_in * dpi)

def fmt_mm(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.3f}".rstrip("0").rstrip(".")

def parse_widths_list(s: str):
    chunks = [c.strip() for c in s.replace(",", " ").split() if c.strip()]
    return [float(c) for c in chunks]

def compute_panel_layout(widths_mm, bleed_mm, overlap_mm):
    """
    Build per-panel horizontal extents so that:
      - bleed applies only to the outer edges (first/last panel)
      - overlaps are shared between adjacent panels without shrinking total width
    Returns (layout, total_width_mm, overlap_eff) where layout is a list of dicts:
      {"outer_left", "outer_right", "content_left", "content_right", "width"}
    """
    bleed_eff = max(0.0, float(bleed_mm))
    widths = [float(w) for w in widths_mm]

    if not widths:
        overlap_eff = max(0.0, float(overlap_mm))
        return [], 2 * bleed_eff, overlap_eff

    overlap_eff = max(0.0, float(overlap_mm))
    min_w = min(widths)
    if overlap_eff >= min_w:
        overlap_eff = max(0.0, min_w - 0.01)

    overlap_half = overlap_eff * 0.5
    layout = []
    cursor = bleed_eff  # running position at the start of each panel's content

    for idx, width in enumerate(widths):
        content_left = cursor
        content_right = cursor + width

        outer_left = content_left - (bleed_eff if idx == 0 else overlap_half)
        outer_right = content_right + (bleed_eff if idx == len(widths) - 1 else overlap_half)

        layout.append({
            "outer_left": max(0.0, outer_left),
            "outer_right": max(outer_left, outer_right),
            "content_left": content_left,
            "content_right": content_right,
            "width": width,
        })

        cursor = content_right

    total_width = layout[-1]["outer_right"]
    return layout, total_width, overlap_eff


# ---------------------- Core processing ----------------------
# Raster (non-uniform) path — now resamples to EXACT pixels & writes DPI
def export_artboards_streaming_from_src(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    base_name,
    outdir: Path,
    dpi: int,
    export_fmt: str = "pdf",
    log_cb=None,
):
    page = src_doc.load_page(0)
    src_rect = page.rect

    bleed_eff = max(0.0, float(bleed_mm))
    panel_layout, target_w_mm, overlap_mm = compute_panel_layout(widths_mm, bleed_eff, overlap_mm)
    target_h_mm = height_mm + 2 * bleed_eff
    target_w_pt = mm_to_pt(target_w_mm)
    target_h_pt = mm_to_pt(target_h_mm)

    sx, sy = compute_scale_matrix(src_rect, target_w_pt, target_h_pt)
    M = fitz.Matrix(sx, sy)
    clip_h_pt = mm_to_pt(target_h_mm)

    for idx, panel in enumerate(panel_layout):
        left_mm = panel["outer_left"]
        right_mm = panel["outer_right"]
        w_t_mm = right_mm - left_mm
        x0_t = mm_to_pt(left_mm)
        x1_t = mm_to_pt(right_mm)
        w_t = x1_t - x0_t
        h_t = clip_h_pt

        x0_s = x0_t / sx
        x1_s = x1_t / sx
        y0_s = 0.0 / sy
        y1_s = clip_h_pt / sy
        clip_src = fitz.Rect(x0_s, y0_s, x1_s, y1_s)

        total_pixels = estimate_pixels(w_t, h_t, dpi)
        eff_dpi = dpi
        if total_pixels > MAX_MP * 1e6:
            scale = (MAX_MP * 1e6 / total_pixels) ** 0.5
            eff_dpi = max(72, int(dpi * scale))
            if log_cb:
                mp = total_pixels / 1e6
                log_cb(f"[SAFE] {base_name}_{idx+1}: requested ~{mp:.1f} MP @ {dpi} dpi; using {eff_dpi} dpi")

        # Render this panel
        pix = page.get_pixmap(matrix=M, clip=clip_src, dpi=eff_dpi, alpha=False)

        # Convert to PIL and force exact pixel size that matches mm at eff_dpi
        # exact_px = round( (points / 72) * dpi )
        target_w_px = max(1, int(round((w_t / 72.0) * eff_dpi)))
        target_h_px = max(1, int(round((h_t / 72.0) * eff_dpi)))

        pil_im = None
        if PIL_AVAILABLE:
            pil_im = pixmap_to_pil(pix)
            if pil_im.size != (target_w_px, target_h_px):
                pil_im = pil_im.resize((target_w_px, target_h_px), resample=Image.BICUBIC)

        export_fmt_lc = (export_fmt or "pdf").lower()
        if export_fmt_lc == "pdf":
            out = fitz.open()
            out_page = out.new_page(width=w_t, height=h_t)
            force_page_boxes(out_page)
            out_page.insert_image(out_page.rect, pixmap=pix, keep_proportion=False)
            out_name = f"{base_name}_{idx+1}.pdf"
            out.save(outdir / out_name)
            out.close()
        else:
            ext = "jpg" if export_fmt_lc in ("jpg", "jpeg") else ("tif" if export_fmt_lc in ("tif", "tiff") else export_fmt_lc)
            out_name = f"{base_name}_{idx+1}.{ext}"
            out_path = outdir / out_name

            if pil_im is None:
                # Fallback without DPI control (Pillow not installed) — recommend installing Pillow
                pix.save(str(out_path))
            else:
                if export_fmt_lc in ("tif", "tiff"):
                    # Retry loop lowering DPI if encoder fails
                    trial_dpi = eff_dpi
                    while True:
                        try:
                            save_raster_pil(pil_im, out_path, export_fmt_lc, trial_dpi, log_cb)
                            break
                        except Exception as e:
                            if log_cb:
                                log_cb(f"[TIFF] save failed @ {trial_dpi} dpi: {e}")
                            next_dpi = int(trial_dpi * 0.85)
                            if next_dpi < 100 or next_dpi == trial_dpi:
                                raise
                            trial_dpi = next_dpi
                    if log_cb and trial_dpi != eff_dpi:
                        log_cb(f"[TIFF] succeeded after DPI fallback: {trial_dpi} dpi")
                else:
                    # JPG / PNG, etc — embed DPI explicitly
                    save_raster_pil(pil_im, out_path, export_fmt_lc, eff_dpi, log_cb)

        if log_cb:
            log_cb(
                f"[CROP] {out_name}: x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  dpi={eff_dpi}"
            )

# Vector (uniform) path with fit mode (unchanged)
def export_artboards_vector_uniform(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    base_name,
    outdir: Path,
    fit_mode: str = "height",  # "height" or "width"
    log_cb=None,
):
    page = src_doc.load_page(0)
    src_rect = page.rect

    bleed_eff = max(0.0, float(bleed_mm))
    panel_layout, target_w_mm, overlap_mm = compute_panel_layout(widths_mm, bleed_eff, overlap_mm)
    target_w_pt = mm_to_pt(target_w_mm)

    if fit_mode == "width":
        s = (target_w_pt / float(src_rect.width)) if src_rect.width else 1.0
        target_h_pt = s * float(src_rect.height)
    else:
        target_h_mm = height_mm + 2 * bleed_eff
        target_h_pt = mm_to_pt(target_h_mm)
        s = (target_h_pt / float(src_rect.height)) if src_rect.height else 1.0

    clip_h_pt = target_h_pt

    for idx, panel in enumerate(panel_layout):
        left_mm = panel["outer_left"]
        right_mm = panel["outer_right"]
        w_t_mm = right_mm - left_mm
        x0_t = mm_to_pt(left_mm)
        x1_t = mm_to_pt(right_mm)
        w_t = x1_t - x0_t
        h_t = clip_h_pt

        x0_s = x0_t / s
        x1_s = x1_t / s
        y0_s = 0.0
        y1_s = src_rect.height
        clip_src = fitz.Rect(x0_s, y0_s, x1_s, y1_s)

        out = fitz.open()
        out_page = out.new_page(width=w_t, height=h_t)
        force_page_boxes(out_page)
        out_page.show_pdf_page(out_page.rect, src_doc, 0, clip=clip_src)
        out_name = f"{base_name}_{idx+1}.pdf"
        out.save(outdir / out_name)
        out.close()

        if log_cb:
            log_cb(
                f"[CROP] {out_name} (VECTOR {fit_mode.upper()}): x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  scale={s:.6f}"
            )

def process_file(
    file_path: Path,
    bleed_mm: float,
    widths_mm,
    height_mm: float,
    overlap_mm: float,
    dpi: int,
    output_root: Path,
    export_fmt: str = "pdf",
    preserve_vectors: bool = False,
    vector_fit_mode: str = "height",  # "height" or "width"
    log_cb=None,
):
    try:
        src = open_pdf_robust(file_path)
    except Exception as e:
        if log_cb:
            log_cb(f"[ERROR] {file_path}: {e}")
            log_cb("Tip: If this is a OneDrive file, right-click → 'Always keep on this device'.")
        return

    try:
        bleed_eff = max(0.0, float(bleed_mm))
        n = len(widths_mm)
        panel_layout, target_w_mm, overlap_mm = compute_panel_layout(widths_mm, bleed_eff, overlap_mm)
        target_h_mm = height_mm + 2 * bleed_eff
        target_w_pt = mm_to_pt(target_w_mm)
        target_h_pt = mm_to_pt(target_h_mm)

        if preserve_vectors and export_fmt.lower() != "pdf":
            export_fmt = "pdf"
            if log_cb:
                log_cb("[NOTE] Preserve vectors is ON → forcing PDF output.")
        if log_cb:
            log_cb("")
            log_cb("=" * 60)
            log_cb(f"Input: {file_path}")
            log_cb(f"Bleed: {bleed_mm:.1f} mm   Overlap: {overlap_mm:.1f} mm   Height: {height_mm:.1f} mm   Artboards: {len(widths_mm)}")
            log_cb(f"Widths: {', '.join(str(int(w)) if float(w).is_integer() else str(w) for w in widths_mm)} mm")
            if preserve_vectors and vector_fit_mode == "width":
                page = src.load_page(0)
                s = (target_w_pt / float(page.rect.width)) if page.rect.width else 1.0
                calc_h_mm = pt_to_mm(s * float(page.rect.height))
                log_cb(f"Target full size (vector/fit WIDTH): {pt_to_mm(target_w_pt):.1f} x {calc_h_mm:.1f} mm")
            else:
                log_cb(f"Target full size: {pt_to_mm(target_w_pt):.1f} x {pt_to_mm(target_h_pt):.1f} mm")
            log_cb(f"Mode: {'VECTOR (uniform, fit '+vector_fit_mode+')' if preserve_vectors else 'RASTER (non-uniform)'}  Export as: {export_fmt.upper()}  Output dir: {output_root}")

        base_name = file_path.stem
        outdir = output_root
        outdir.mkdir(parents=True, exist_ok=True)

        if preserve_vectors:
            export_artboards_vector_uniform(
                src, widths_mm, height_mm, bleed_mm, overlap_mm, base_name, outdir,
                fit_mode=vector_fit_mode, log_cb=log_cb
            )
        else:
            export_artboards_streaming_from_src(
                src, widths_mm, height_mm, bleed_mm, overlap_mm, base_name, outdir, dpi, export_fmt, log_cb
            )

        if log_cb:
            log_cb(f"Done: {file_path.name}")
    finally:
        try:
            src.close()
        except Exception:
            pass


# ---------------------- THEME (Dark / Light) ----------------------
DARK = {
    "bg": "#1e1f22",
    "panel": "#232427",
    "fg": "#e6e6e6",
    "muted": "#b7b7b7",
    "accent": "#4da3ff",
    "entry_bg": "#2b2d31",
    "entry_fg": "#e6e6e6",
    "border": "#3a3b3f",
    "sel_bg": "#2d5a9b",
    "sel_fg": "#ffffff",
    "tree_bg": "#1f2124",
    "tree_alt": "#23262a",
    "tree_head_bg": "#2b2d31",
    "tree_head_fg": "#e6e6e6",
    "progress": "#4da3ff",
}

LIGHT = {
    "bg": "#f5f6f8",
    "panel": "#ffffff",
    "fg": "#202124",
    "muted": "#5f6368",
    "accent": "#1a73e8",
    "entry_bg": "#ffffff",
    "entry_fg": "#202124",
    "border": "#dfe1e5",
    "sel_bg": "#cde2ff",
    "sel_fg": "#0b2447",
    "tree_bg": "#ffffff",
    "tree_alt": "#f4f6f9",
    "tree_head_bg": "#f1f3f4",
    "tree_head_fg": "#202124",
    "progress": "#1a73e8",
}

def apply_theme(root: tk.Tk, style: ttk.Style, dark: bool):
    C = DARK if dark else LIGHT
    # base window + text
    root.configure(bg=C["bg"])
    root.option_clear()
    style.theme_use("clam")

    # General fonts/colors
    style.configure(".", background=C["panel"], foreground=C["fg"])

    # Containers / frames
    for elem in ("TFrame", "TLabelframe", "TLabelframe.Label"):
        style.configure(elem, background=C["panel"], foreground=C["fg"])

    # Labels
    style.configure("TLabel", background=C["panel"], foreground=C["fg"])

    # Buttons
    style.configure("TButton", background=C["panel"], foreground=C["fg"], bordercolor=C["border"], focusthickness=1)
    style.map("TButton",
              background=[("active", C["panel"])],
              foreground=[("disabled", C["muted"])],
              relief=[("pressed", "sunken")])

    # Entries / Combobox
    style.configure("TEntry", fieldbackground=C["entry_bg"], foreground=C["entry_fg"], bordercolor=C["border"])
    style.configure("TCombobox", fieldbackground=C["entry_bg"], foreground=C["entry_fg"], bordercolor=C["border"])
    style.map("TCombobox",
              fieldbackground=[("readonly", C["entry_bg"])],
              foreground=[("readonly", C["entry_fg"])])

    # Checkbuttons
    style.configure("TCheckbutton", background=C["panel"], foreground=C["fg"])

    # Progressbar
    style.configure("TProgressbar", background=C["progress"], troughcolor=C["panel"], bordercolor=C["border"])

    # Treeview
    style.configure("Treeview",
                    background=C["tree_bg"],
                    fieldbackground=C["tree_bg"],
                    foreground=C["fg"],
                    bordercolor=C["border"])
    style.map("Treeview",
              background=[("selected", C["sel_bg"])],
              foreground=[("selected", C["sel_fg"])])
    style.configure("Treeview.Heading",
                    background=C["tree_head_bg"],
                    foreground=C["tree_head_fg"],
                    bordercolor=C["border"])

    # Toplevel / overall bg patches
    root.tk_setPalette(background=C["panel"], foreground=C["fg"], activeBackground=C["panel"], activeForeground=C["fg"])

    # Patch Text widgets (manually)
    for child in root.winfo_children():
        _patch_text_colors(child, C, root)

def _patch_text_colors(widget, C, root):
    if isinstance(widget, tk.Text):
        widget.configure(bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["fg"])
    # Patch Canvas background to match theme panel
    if isinstance(widget, tk.Canvas):
        widget.configure(bg=C["panel"])
    for ch in widget.winfo_children():
        _patch_text_colors(ch, C, root)


# ---------------------- GUI ----------------------
class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("Artboard Cutter")
        self.geometry("1060x840")
        self.minsize(980, 740)

        self._style = ttk.Style(self)
        self.dark_mode = tk.BooleanVar(value=True)
        apply_theme(self, self._style, self.dark_mode.get())
        self.dark_mode.trace_add("write", self._on_theme_toggle)

        # state for aspect ratio sync
        self._src_w_mm = None
        self._src_h_mm = None
        self._src_ar = None
        self._syncing = False
        self._perfile = {}

        # Top bar (theme toggle)
        topbar = ttk.Frame(self)
        topbar.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Checkbutton(topbar, text="Dark mode", variable=self.dark_mode).pack(side="right")

        # Main top section
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # ---- Preview (left) ----
        preview_group = ttk.LabelFrame(top, text="Preview")
        preview_group.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        # Top status line
        self.preview_var = tk.StringVar(value="Target: —")
        ttk.Label(preview_group, textvariable=self.preview_var).pack(side="top", anchor="w", padx=6, pady=(6, 0))
        # Canvas (large) fills
        self.preview_canvas = tk.Canvas(preview_group, highlightthickness=0, width=520, height=520)
        self.preview_canvas.pack(side="top", fill="both", expand=True, padx=6, pady=6)
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())

        # Track preview background image
        self._bg_preview_im = None
        self._bg_preview_tk = None

        # Grid weights: make preview wider
        top.columnconfigure(0, weight=2)
        top.rowconfigure(0, weight=1)

        # ---- Files Tree ----
        files_frame = ttk.LabelFrame(top, text="Files")
        files_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        top.columnconfigure(1, weight=1)

        self.files_tree = ttk.Treeview(files_frame, columns=("path",), show="tree headings", selectmode="extended", height=12)
        self.files_tree.heading("#0", text="Process")
        self.files_tree.heading("path", text="Path")
        self.files_tree.column("#0", width=340, anchor="w")
        self.files_tree.column("path", width=680, anchor="w")
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        files_frame.rowconfigure(0, weight=1)
        files_frame.columnconfigure(0, weight=1)

        self._checked = {}
        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        btns = ttk.Frame(files_frame)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(btns, text="Add Files…", command=self.on_add_files).pack(side="left")
        ttk.Button(btns, text="Remove Selected", command=self.on_remove_selected).pack(side="left", padx=6)
        ttk.Button(btns, text="Clear", command=self.on_clear).pack(side="left", padx=6)
        ttk.Button(btns, text="Check Selected", command=self.on_check_selected).pack(side="left", padx=6)
        ttk.Button(btns, text="Uncheck Selected", command=self.on_uncheck_selected).pack(side="left", padx=6)
        ttk.Button(btns, text="Check All", command=self.on_check_all).pack(side="left", padx=6)
        ttk.Button(btns, text="Uncheck All", command=self.on_uncheck_all).pack(side="left", padx=6)

        self.files_tree.bind("<Button-1>", self.on_tree_click)
        self.files_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        if DND_AVAILABLE:
            self.files_tree.drop_target_register(DND_FILES)
            self.files_tree.dnd_bind("<<Drop>>", self.on_drop)

        # ---- Parameters ----
        params = ttk.LabelFrame(top, text="Parameters")
        params.grid(row=0, column=2, sticky="nsew")
        top.columnconfigure(2, weight=1)

        ttk.Label(params, text="Bleed (mm):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.bleed_var = tk.StringVar(value="")
        ttk.Entry(params, textvariable=self.bleed_var, width=12).grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(params, text="Overlap (mm):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.overlap_var = tk.StringVar(value="")
        ttk.Entry(params, textvariable=self.overlap_var, width=12).grid(row=1, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(params, text="Widths (mm):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.widths_var = tk.StringVar(value="")
        self.widths_entry = ttk.Entry(params, textvariable=self.widths_var, width=24)
        self.widths_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(params, text="Height (mm):").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.height_var = tk.StringVar(value="")
        self.height_entry = ttk.Entry(params, textvariable=self.height_var, width=12)
        self.height_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(params, text="DPI:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        self.dpi_var = tk.StringVar(value="")
        ttk.Entry(params, textvariable=self.dpi_var, width=12).grid(row=4, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(params, text="Export as:").grid(row=5, column=0, sticky="w", padx=6, pady=4)
        self.format_var = tk.StringVar(value="PDF")
        ttk.Combobox(params, textvariable=self.format_var, values=["PDF", "JPG", "TIFF"], state="readonly", width=10)\
            .grid(row=5, column=1, sticky="ew", padx=6, pady=4)

        self.preserve_vectors_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(params, text="Preserve vectors (uniform, PDF)", variable=self.preserve_vectors_var)\
            .grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 4))

        ttk.Label(params, text="Vector fit:").grid(row=7, column=0, sticky="w", padx=6, pady=4)
        self.fit_mode_var = tk.StringVar(value="height")  # "height" or "width"
        ttk.Combobox(params, textvariable=self.fit_mode_var, values=["height", "width"], state="readonly", width=10)\
            .grid(row=7, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(params, text='Output folder:').grid(row=8, column=0, sticky='w', padx=6, pady=4)
        self.outdir_var = tk.StringVar(value=str(Path.cwd() / "output"))
        out_row = ttk.Frame(params)
        out_row.grid(row=8, column=1, sticky="ew", padx=6, pady=4)
        ttk.Entry(out_row, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True)
        ttk.Button(out_row, text="Browse…", command=self.on_browse_outdir).pack(side="left", padx=(6, 0))

        for r in range(9):
            params.rowconfigure(r, weight=0)
        params.columnconfigure(1, weight=1)

        # Progress + Start
        run_bar = ttk.Frame(self)
        run_bar.pack(fill="x", padx=10, pady=(0, 6))
        self.progress = ttk.Progressbar(run_bar, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Button(run_bar, text="Start", command=self.on_start).pack(side="left", padx=8)

        # (Preview widgets moved to left column)

        # Log
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        # apply theme to Text, etc.
        apply_theme(self, self._style, self.dark_mode.get())

        try:
            self.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

        # aspect sync + live preview traces
        self.widths_var.trace_add("write", self._on_widths_changed)
        self.height_var.trace_add("write", self._on_height_changed)
        self.bleed_var.trace_add("write", self._update_preview)
        self.overlap_var.trace_add("write", self._update_preview)
        self.fit_mode_var.trace_add("write", self._fit_mode_changed)
        self.preserve_vectors_var.trace_add("write", self._update_preview)
        self.format_var.trace_add("write", self._update_preview)

    # ---------- Theme toggle ----------
    def _on_theme_toggle(self, *_):
        apply_theme(self, self._style, self.dark_mode.get())
        # Refresh preview to reflect theme colors
        self._update_preview()

    # ---------- Files tree helpers ----------
    def _add_file_item(self, path: str):
        for iid in self.files_tree.get_children(""):
            if self.files_tree.set(iid, "path") == path:
                return
        fname = Path(path).name
        iid = self.files_tree.insert("", "end", text=f"☐ {fname}", values=(path,))
        self._checked[iid] = False

    def _toggle_item(self, iid):
        new_state = not self._checked.get(iid, False)
        self._checked[iid] = new_state
        fname = Path(self.files_tree.set(iid, "path")).name
        self.files_tree.item(iid, text=(f"☑ {fname}" if new_state else f"☐ {fname}"))

    def on_tree_click(self, event):
        region = self.files_tree.identify("region", event.x, event.y)
        col = self.files_tree.identify_column(event.x)
        if region != "tree" or col != "#0":
            return
        iid = self.files_tree.identify_row(event.y)
        if not iid:
            return
        self._toggle_item(iid)

    def on_tree_select(self, _event=None):
        sel = self.files_tree.selection()
        if not sel:
            return
        iid = sel[-1]
        path_str = self.files_tree.set(iid, "path")
        self.autofill_dims_from_path(Path(path_str))

    def on_check_selected(self):
        for iid in self.files_tree.selection():
            if not self._checked.get(iid, False):
                self._toggle_item(iid)

    def on_uncheck_selected(self):
        for iid in self.files_tree.selection():
            if self._checked.get(iid, False):
                self._toggle_item(iid)

    def on_check_all(self):
        for iid in self.files_tree.get_children(""):
            if not self._checked.get(iid, False):
                self._toggle_item(iid)

    def on_uncheck_all(self):
        for iid in self.files_tree.get_children(""):
            if self._checked.get(iid, False):
                self._toggle_item(iid)

    # ---------- Drag & drop / file buttons ----------
    def on_drop(self, event):
        raw = self.tk.splitlist(event.data)
        last = None
        for p in raw:
            p = p.strip("{}").strip()
            if p.lower().endswith((".pdf", ".ai", ".jpg", ".jpeg", ".png", ".tif", ".tiff")):
                self._add_file_item(p)
                last = p
        if last:
            self.autofill_dims_from_path(Path(last))

    def on_add_files(self):
        files = filedialog.askopenfilenames(
            title="Select files",
            filetypes=[
                ("Supported files", "*.pdf *.ai *.jpg *.jpeg *.png *.tif *.tiff"),
                ("PDF files", "*.pdf"),
                ("AI files", "*.ai"),
                ("Images", "*.jpg *.jpeg *.png *.tif *.tiff"),
                ("All files", "*.*"),
            ]
        )
        last = None
        for f in files:
            self._add_file_item(f)
            last = f
        if last:
            self.autofill_dims_from_path(Path(last))

    def on_remove_selected(self):
        for iid in list(self.files_tree.selection()):
            path = self.files_tree.set(iid, "path")
            self.files_tree.delete(iid)
            self._checked.pop(iid, None)
            self._perfile.pop(path, None)

    def on_clear(self):
        for iid in list(self.files_tree.get_children("")):
            path = self.files_tree.set(iid, "path")
            self.files_tree.delete(iid)
            self._checked.pop(iid, None)
            self._perfile.pop(path, None)

    def on_browse_outdir(self):
        d = filedialog.askdirectory(title="Choose output folder", initialdir=self.outdir_var.get())
        if d:
            self.outdir_var.set(d)

    # ---------- Log & parsing ----------
    def log_print(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    # ---------- Auto-fill size & per-file presets ----------
    def autofill_dims_from_path(self, p: Path):
        # restore per-file preset if present
        if p.as_posix() in self._perfile:
            wh = self._perfile[p.as_posix()]
            self._syncing = True
            self.widths_var.set(wh.get("widths", ""))
            self.height_var.set(wh.get("height", ""))
            self._syncing = False
            self._update_preview()
        try:
            doc = open_pdf_robust(p)
        except Exception as e:
            self.log_print(f"[WARN] Cannot probe {p}: {e}")
            # Clear preview image if load fails
            self._bg_preview_im = None
            self._bg_preview_tk = None
            self._update_preview()
            return
        try:
            page = doc.load_page(0)
            rect = page.rect
            w_mm = pt_to_mm(rect.width)
            h_mm = pt_to_mm(rect.height)

            self._src_w_mm = float(w_mm)
            self._src_h_mm = float(h_mm)
            self._src_ar = (self._src_w_mm / self._src_h_mm) if self._src_h_mm else None

            if p.as_posix() not in self._perfile:
                self._syncing = True
                self.widths_var.set(fmt_mm(w_mm))
                self.height_var.set(fmt_mm(h_mm))
                self._syncing = False

            ar_txt = f"{self._src_ar:.6f}" if self._src_ar else "n/a"
            self.log_print(f"[INFO] Source size {p.name}: width={fmt_mm(w_mm)} mm, height={fmt_mm(h_mm)} mm (AR={ar_txt})")

            # Prepare low-res background preview image
            try:
                if PIL_AVAILABLE:
                    max_px = 1600.0
                    max_dim_pt = max(float(rect.width), float(rect.height)) or 1.0
                    scale = max(0.2, min(2.0, max_px / max_dim_pt))
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    self._bg_preview_im = pixmap_to_pil(pix)
                else:
                    self._bg_preview_im = None
                self._bg_preview_tk = None
            except Exception:
                self._bg_preview_im = None
                self._bg_preview_tk = None
        except Exception as e:
            self.log_print(f"[WARN] Could not read size: {p} ({e})")
        finally:
            try:
                doc.close()
            except Exception:
                pass
        self._update_preview()

    def _save_current_file_preset(self):
        sel = self.files_tree.selection()
        if not sel:
            return
        iid = sel[-1]
        path_str = self.files_tree.set(iid, "path")
        self._perfile[path_str] = {"widths": self.widths_var.get(), "height": self.height_var.get()}

    # ---------- Aspect sync (preserve vectors) ----------
    def _on_widths_changed(self, *_):
        self._save_current_file_preset()
        if self._syncing or not self.preserve_vectors_var.get():
            self._update_preview()
            return
        try:
            parts = parse_widths_list(self.widths_var.get())
        except Exception:
            self._update_preview()
            return
        if not self._src_ar or self._src_ar <= 0:
            self._update_preview()
            return
        if len(parts) == 1:
            try:
                new_w = float(parts[0])
            except Exception:
                self._update_preview()
                return
            new_h = new_w / self._src_ar
            self._syncing = True
            self.height_var.set(fmt_mm(new_h))
            self._syncing = False
        self._update_preview()

    def _on_height_changed(self, *_):
        self._save_current_file_preset()
        if self._syncing or not self.preserve_vectors_var.get():
            self._update_preview()
            return
        try:
            parts = parse_widths_list(self.widths_var.get())
        except Exception:
            self._update_preview()
            return
        if len(parts) != 1 or not self._src_ar or self._src_ar <= 0:
            self._update_preview()
            return
        try:
            new_h = float(self.height_var.get())
        except Exception:
            self._update_preview()
            return
        new_w = new_h * self._src_ar
        self._syncing = True
        self.widths_var.set(fmt_mm(new_w))
        self._syncing = False
        self._update_preview()

    def _fit_mode_changed(self, *_):
        self._on_widths_changed()

    # ---------- Preview ----------
    def _update_preview(self, *_):
        try:
            bleed = float(self.bleed_var.get())
        except Exception:
            bleed = 0.0
        try:
            overlap = self.overlap_var.get().strip()
            overlap = (2 * bleed) if overlap == "" else float(overlap)
        except Exception:
            overlap = 0.0

        try:
            widths = parse_widths_list(self.widths_var.get())
        except Exception:
            self.preview_var.set("Target: —")
            # Clear visual preview on parse error
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
            return
        try:
            height = float(self.height_var.get())
        except Exception:
            height = 0.0

        if not widths:
            self.preview_var.set("Target: —")
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
            return

        bleed_eff = max(0.0, bleed)
        panel_layout, total_w, overlap = compute_panel_layout(widths, bleed_eff, overlap)
        n = len(panel_layout)
        fit_mode = self.fit_mode_var.get()
        pv = bool(self.preserve_vectors_var.get())

        if pv and fit_mode == "width":
            h_txt = "(auto by width)"
            # Estimate page height by source aspect if available
            if self._src_w_mm and self._src_h_mm and self._src_w_mm > 0:
                page_h = (total_w / self._src_w_mm) * self._src_h_mm
            else:
                page_h = height + 2 * bleed_eff
        else:
            page_h = height + 2 * bleed_eff
            h_txt = fmt_mm(page_h)

        w_txt = fmt_mm(total_w)
        self.preview_var.set(f"Target: {w_txt} x {h_txt} mm   |   Panels: {n}   (Bleed {fmt_mm(bleed_eff)} / Overlap {fmt_mm(overlap)})")

        # Draw the visual preview on the canvas
        try:
            self._render_preview_canvas(panel_layout, bleed_eff, page_h, total_w)
        except Exception:
            # Ignore drawing errors in preview
            pass

    def _render_preview_canvas(self, panel_layout, bleed_mm, page_h_mm, total_w_mm):
        if not hasattr(self, "preview_canvas"):
            return
        cv = self.preview_canvas
        cv.delete("all")

        cw = max(1, int(cv.winfo_width()))
        ch = max(1, int(cv.winfo_height()))
        pad = 10
        if total_w_mm <= 0 or page_h_mm <= 0 or cw <= 2 * pad or ch <= 2 * pad:
            return

        # Theme colors
        C = DARK if self.dark_mode.get() else LIGHT
        border = C.get("border", "#888888")
        accent = C.get("accent", "#4da3ff")
        muted = C.get("muted", "#b7b7b7")

        # Scale to fit and center
        sx = (cw - 2 * pad) / float(total_w_mm)
        sy = (ch - 2 * pad) / float(page_h_mm)
        s = min(sx, sy)
        x0 = pad + (cw - 2 * pad - total_w_mm * s) / 2.0
        y0 = pad + (ch - 2 * pad - page_h_mm * s) / 2.0

        def xx(mm):
            return x0 + mm * s

        def yy(mm):
            return y0 + mm * s

        # Background graphic (if available)
        if IMAGE_TK_AVAILABLE and self._bg_preview_im is not None:
            try:
                dest_w = max(1, int(round(total_w_mm * s)))
                dest_h = max(1, int(round(page_h_mm * s)))
                # Resize background to page area
                bg_resized = self._bg_preview_im.resize((dest_w, dest_h), resample=Image.BILINEAR)
                self._bg_preview_tk = ImageTk.PhotoImage(bg_resized)
                cv.create_image(xx(0), yy(0), image=self._bg_preview_tk, anchor="nw")
            except Exception:
                self._bg_preview_tk = None

        # Page outline
        cv.create_rectangle(xx(0), yy(0), xx(total_w_mm), yy(page_h_mm), outline=border, width=1)

        # Panels
        for panel in panel_layout:
            outer_left = panel["outer_left"]
            outer_right = panel["outer_right"]
            cv.create_rectangle(xx(outer_left), yy(0), xx(outer_right), yy(page_h_mm), outline=accent, width=2)

            content_left = panel["content_left"]
            content_right = panel["content_right"]
            top_bleed = bleed_mm
            bottom_bleed = bleed_mm
            cv.create_rectangle(
                xx(content_left),
                yy(top_bleed),
                xx(content_right),
                yy(max(0.0, page_h_mm - bottom_bleed)),
                outline=muted,
                width=1,
            )

    # ---------- Run ----------
    def on_start(self):
        checked_paths = []
        for iid in self.files_tree.get_children(""):
            if self._checked.get(iid, False):
                checked_paths.append(self.files_tree.set(iid, "path"))
        if not checked_paths:
            messagebox.showwarning("No files selected", "Tick the checkbox next to the file(s) you want to process.")
            return

        try:
            bleed_mm = float(self.bleed_var.get())
            widths_mm = parse_widths_list(self.widths_var.get())
            height_mm = float(self.height_var.get())
            overlap_txt = self.overlap_var.get().strip()
            overlap_mm = (2 * bleed_mm) if overlap_txt == "" else float(overlap_txt)
            dpi = int(self.dpi_var.get())
            export_fmt = self.format_var.get().lower()
            preserve_vectors = bool(self.preserve_vectors_var.get())
            fit_mode = self.fit_mode_var.get()
        except Exception:
            messagebox.showerror("Invalid parameters", "Please check bleed, overlap, widths, height, DPI, and format.")
            return

        outdir = Path(self.outdir_var.get()).expanduser()
        outdir.mkdir(parents=True, exist_ok=True)

        self.progress["value"] = 0
        self.progress["maximum"] = len(checked_paths)

        def work():
            count = 0
            for i, f in enumerate(checked_paths, 1):
                try:
                    process_file(
                        Path(f),
                        bleed_mm=bleed_mm,
                        widths_mm=widths_mm,
                        height_mm=height_mm,
                        overlap_mm=overlap_mm,
                        dpi=dpi,
                        output_root=outdir,
                        export_fmt=export_fmt,
                        preserve_vectors=preserve_vectors,
                        vector_fit_mode=fit_mode,
                        log_cb=self.log_print,
                    )
                    count += 1
                except Exception as e:
                    self.log_print(f"[ERROR] {f}: {e}")
                finally:
                    self.progress["value"] = i
            self.log_print("")
            self.log_print(f"Done. Processed {count}/{len(checked_paths)} file(s). Outputs in: {outdir}")

        threading.Thread(target=work, daemon=True).start()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
