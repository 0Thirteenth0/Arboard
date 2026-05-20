#!/usr/bin/env python3
import threading
import os
import subprocess
import sys
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

from src.artboard_cutter_core import (
    ArtworkProfile,
    ExportOptions,
    compute_panel_layout as core_compute_panel_layout,
    compute_scale_matrix as core_compute_scale_matrix,
    create_artwork_profiles as core_create_artwork_profiles,
    estimate_pixels as core_estimate_pixels,
    fmt_mm as core_fmt_mm,
    force_page_boxes as core_force_page_boxes,
    mm_to_pt as core_mm_to_pt,
    open_pdf_robust as core_open_pdf_robust,
    parse_widths_list as core_parse_widths_list,
    process_file as core_process_file,
    pt_to_mm as core_pt_to_mm,
    validate_output_name as core_validate_output_name,
)
from src.artboard_cutter_core.layout import compute_preview_page_height
from src.artboard_cutter_core.illustrator_integration import get_illustrator_artboard_names
from src.artboard_cutter_core.profiles import sanitize_output_name
from src.artboard_cutter_core.raster_export import export_artboards_streaming_from_src as core_export_raster
from src.artboard_cutter_core.settings import AppSettings, load_settings, save_settings
from src.artboard_cutter_core.themes import THEME_NAMES, get_theme, normalize_theme_name
from src.artboard_cutter_core.vector_export import export_artboards_vector_uniform as core_export_vector

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
    return core_mm_to_pt(mm)

def pt_to_mm(pt: float) -> float:
    return core_pt_to_mm(pt)

def force_page_boxes(page):
    return core_force_page_boxes(page)

def open_pdf_robust(p: Path):
    return core_open_pdf_robust(p)

def compute_scale_matrix(src_rect, target_w_pt, target_h_pt):
    return core_compute_scale_matrix(src_rect, target_w_pt, target_h_pt)

def estimate_pixels(w_pt, h_pt, dpi):
    return core_estimate_pixels(w_pt, h_pt, dpi)

def fmt_mm(v: float) -> str:
    return core_fmt_mm(v)

def parse_widths_list(s: str):
    return core_parse_widths_list(s)

def validate_output_name(name: str) -> str:
    return core_validate_output_name(name)

def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path

def normalize_overlap_mode(mode: str) -> str:
    return "Left" if (mode or "").strip().lower().startswith("left") else "Shared"

def overlap_mode_key(mode: str) -> str:
    return "left" if normalize_overlap_mode(mode) == "Left" else "shared"

def compute_panel_layout(widths_mm, bleed_mm, overlap_mm, overlap_mode="Shared"):
    """
    Build per-panel horizontal extents so that:
      - bleed applies only to the outer edges (first/last panel)
      - shared mode overlaps are split equally between adjacent panels
      - left mode places full internal overlap on the right-hand panel's left edge
    Returns (layout, total_width_mm, overlap_eff) where layout is a list of dicts:
      {"outer_left", "outer_right", "content_left", "content_right", "width"}
    """
    layout, total_width, overlap_eff = core_compute_panel_layout(widths_mm, bleed_mm, overlap_mm, overlap_mode_key(overlap_mode))
    return [panel.to_legacy_dict() for panel in layout], total_width, overlap_eff


# ---------------------- Core processing ----------------------
# Raster path resamples to exact pixels and writes DPI metadata.
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
    overlap_mode="Shared",
):
    return core_export_raster(
        src_doc,
        widths_mm,
        height_mm,
        bleed_mm,
        overlap_mm,
        overlap_mode_key(overlap_mode),
        base_name,
        outdir,
        dpi,
        export_fmt,
        log_cb=log_cb,
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
    overlap_mode="Shared",
):
    return core_export_vector(
        src_doc,
        widths_mm,
        height_mm,
        bleed_mm,
        overlap_mm,
        overlap_mode_key(overlap_mode),
        base_name,
        outdir,
        fit_mode,
        log_cb=log_cb,
    )

def process_file(
    file_path: Path,
    bleed_mm: float,
    widths_mm,
    height_mm: float,
    overlap_mm: float,
    dpi: int,
    output_root: Path,
    overlap_mode: str = "Shared",
    export_fmt: str = "pdf",
    preserve_vectors: bool = False,
    vector_fit_mode: str = "stretch",  # "stretch", "height", or "width"
    page_index: int = 0,
    output_name: str | None = None,
    log_cb=None,
):
    return core_process_file(
        file_path,
        ExportOptions(
            bleed_mm=bleed_mm,
            widths_mm=list(widths_mm),
            height_mm=height_mm,
            overlap_mm=overlap_mm,
            overlap_mode=overlap_mode_key(overlap_mode),
            dpi=dpi,
            output_root=output_root,
            export_fmt=export_fmt,
            preserve_vectors=preserve_vectors,
            vector_fit_mode=vector_fit_mode,
            page_index=page_index,
            output_name=output_name,
        ),
        log_cb=log_cb,
    )


# ---------------------- THEME ----------------------
def apply_theme(root: tk.Tk, style: ttk.Style, theme_name: str):
    theme = get_theme(theme_name)
    C = theme.colors
    root._theme_tokens = C
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
    style.configure("Title.TLabel", background=C["panel"], foreground=C["fg"], font=("Segoe UI", 15, "bold"))
    style.configure("Muted.TLabel", background=C["panel"], foreground=C["muted"])

    # Buttons
    button_hover = C.get("tree_head_bg", C["entry_bg"])
    style.configure("TButton", background=C["panel"], foreground=C["fg"], bordercolor=C["border"], focusthickness=1)
    style.configure("Accent.TButton", background=C["accent"], foreground="#ffffff", bordercolor=C["accent"], focusthickness=1)
    style.map("TButton",
              background=[("disabled", C["panel"]), ("active", button_hover), ("pressed", C["sel_bg"])],
              foreground=[("disabled", C["muted"]), ("active", C["fg"]), ("pressed", C["sel_fg"])],
              bordercolor=[("active", C["accent"]), ("pressed", C["accent"])],
              relief=[("pressed", "sunken")])
    style.map("Accent.TButton",
              background=[("disabled", C["panel"]), ("active", C["sel_bg"]), ("pressed", C["accent"])],
              foreground=[("disabled", C["muted"]), ("active", C["sel_fg"]), ("pressed", "#ffffff")],
              bordercolor=[("active", C["sel_fg"]), ("pressed", C["accent"])])

    # Entries / Combobox
    style.configure("TEntry", fieldbackground=C["entry_bg"], foreground=C["entry_fg"], bordercolor=C["border"], insertcolor=C["entry_fg"])
    style.configure(
        "TCombobox",
        fieldbackground=C["entry_bg"],
        foreground=C["entry_fg"],
        bordercolor=C["border"],
        selectbackground=C["entry_bg"],
        selectforeground=C["entry_fg"],
    )
    style.map("TEntry",
              fieldbackground=[("disabled", C["panel"]), ("readonly", C["entry_bg"])],
              foreground=[("disabled", C["muted"])])
    style.map("TCombobox",
              fieldbackground=[("disabled", C["panel"]), ("readonly", C["entry_bg"]), ("active", C["entry_bg"])],
              background=[("disabled", C["panel"]), ("readonly", C["entry_bg"]), ("active", C["entry_bg"])],
              foreground=[("disabled", C["muted"]), ("readonly", C["entry_fg"]), ("active", C["entry_fg"])])

    # Toggle controls. Explicit active/selected maps prevent native ttk from
    # painting radio/check labels with a bright platform highlight.
    for toggle_style in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            toggle_style,
            background=C["panel"],
            foreground=C["fg"],
            indicatorbackground=C["entry_bg"],
            indicatorforeground=C["fg"],
            focuscolor=C["panel"],
            bordercolor=C["border"],
        )
        style.map(
            toggle_style,
            background=[
                ("disabled", C["panel"]),
                ("pressed", C["panel"]),
                ("active", C["panel"]),
                ("selected", C["panel"]),
            ],
            foreground=[
                ("disabled", C["muted"]),
                ("pressed", C["fg"]),
                ("active", C["fg"]),
                ("selected", C["fg"]),
            ],
            indicatorbackground=[
                ("disabled", C["panel"]),
                ("selected", C["entry_bg"]),
                ("active", C["entry_bg"]),
            ],
        )

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
    style.map("Treeview.Heading",
              background=[("active", C["tree_head_bg"]), ("pressed", C["tree_head_bg"])],
              foreground=[("active", C["tree_head_fg"]), ("pressed", C["tree_head_fg"])],
              bordercolor=[("active", C["border"]), ("pressed", C["border"])],
              relief=[("pressed", "flat")])

    # Patch Text widgets (manually)
    for child in root.winfo_children():
        _patch_text_colors(child, C, root)

def _patch_text_colors(widget, C, root):
    if isinstance(widget, tk.Text):
        widget.configure(
            bg=C["entry_bg"],
            fg=C["entry_fg"],
            insertbackground=C["fg"],
            selectbackground=C["sel_bg"],
            selectforeground=C["sel_fg"],
        )
    # Patch Canvas background to match theme panel
    if isinstance(widget, tk.Canvas):
        widget.configure(bg=C.get("preview_bg", C["panel"]))
    for ch in widget.winfo_children():
        _patch_text_colors(ch, C, root)


# ---------------------- GUI ----------------------
class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("Artboard Cutter")
        icon_path = resource_path("assets/artboard_cutter.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        self._settings = load_settings()
        self.geometry(self._settings.window_geometry or "1060x840")
        self.minsize(980, 740)

        self._style = ttk.Style(self)
        self.theme_var = tk.StringVar(value=normalize_theme_name(self._settings.theme))
        self.dark_mode = tk.BooleanVar(value=get_theme(self.theme_var.get()).is_dark)
        apply_theme(self, self._style, self.theme_var.get())
        self.theme_var.trace_add("write", self._on_theme_changed)

        # state for aspect ratio sync
        self._src_w_mm = None
        self._src_h_mm = None
        self._src_ar = None
        self._syncing = False
        self._profiles = {}
        self._file_groups = {}
        self._active_iid = None
        self._loading_profile = False
        self._build_modern_ui()

    # ---------- Settings persistence ----------
    def _selected_or_recent_file_path(self) -> str:
        sel = self.files_tree.selection()
        if sel:
            profile = self._profiles.get(sel[-1])
            if profile:
                return profile.file_path
        children = self.files_tree.get_children("")
        if children:
            leaf = self._first_profile_iid(children[-1]) or children[-1]
            profile = self._profiles.get(leaf)
            if profile:
                return profile.file_path
        return self._settings.last_input_path

    def _collect_settings(self) -> AppSettings:
        self._save_selected_profile_settings()
        return AppSettings(
            last_input_path=self._selected_or_recent_file_path(),
            last_output_dir=self.outdir_var.get(),
            bleed_mm=self.bleed_var.get(),
            overlap_mm=self.overlap_var.get(),
            overlap_mode=self.overlap_mode_var.get(),
            dpi=self.dpi_var.get(),
            export_format=self.format_var.get(),
            export_mode=self.export_mode_var.get(),
            recent_files=self._settings.recent_files or [],
            recent_output_dirs=self._settings.recent_output_dirs or [],
            theme=self.theme_var.get(),
            window_geometry=self.geometry(),
        )

    def _save_settings(self):
        self._settings = self._collect_settings()
        try:
            save_settings(self._settings)
        except Exception as e:
            if hasattr(self, "log"):
                self.log_print(f"[WARN] Could not save settings: {e}")

    def _on_close(self):
        self._save_settings()
        self.destroy()

    def _build_modern_ui(self):
        topbar = ttk.Frame(self)
        topbar.pack(fill="x", padx=14, pady=(12, 8))

        title_col = ttk.Frame(topbar)
        title_col.pack(side="left", fill="x", expand=True)
        ttk.Label(title_col, text="Artboard Cutter", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_col,
            text="Split production artwork into raster or vector-stretched panel exports.",
            style="Muted.TLabel",
        ).pack(anchor="w")
        theme_box = ttk.Combobox(topbar, textvariable=self.theme_var, values=THEME_NAMES, state="readonly", width=22, takefocus=False)
        theme_box.pack(side="right")
        self._bind_combobox_clear_selection(theme_box)
        ttk.Label(topbar, text="Theme", style="Muted.TLabel").pack(side="right", padx=(0, 8))

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        preview_group = ttk.LabelFrame(main, text="Live Preview")
        side = ttk.Frame(main)
        main.add(preview_group, weight=4)
        main.add(side, weight=2)

        self.preview_var = tk.StringVar(value="Target: -")
        preview_header = ttk.Frame(preview_group)
        preview_header.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(preview_header, textvariable=self.preview_var).pack(side="left", fill="x", expand=True)
        ttk.Button(preview_header, text="Fit", width=6, command=self._preview_fit).pack(side="right", padx=(4, 0))
        ttk.Button(preview_header, text="+", width=3, command=lambda: self._preview_zoom_by(1.2)).pack(side="right", padx=(4, 0))
        ttk.Button(preview_header, text="-", width=3, command=lambda: self._preview_zoom_by(1 / 1.2)).pack(side="right")

        self.preview_canvas = tk.Canvas(preview_group, highlightthickness=0, width=720, height=560)
        self.preview_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self._preview_pan_start)
        self.preview_canvas.bind("<B1-Motion>", self._preview_pan_move)
        self.preview_canvas.bind("<MouseWheel>", self._preview_mousewheel)
        self._bg_preview_im = None
        self._bg_preview_tk = None
        self._preview_zoom = 1.0
        self._preview_pan = [0.0, 0.0]
        self._preview_drag = None

        files_frame = ttk.LabelFrame(side, text="Artwork Queue")
        files_frame.pack(fill="both", expand=True, pady=(0, 8))
        queue_columns = ("select", "original_size", "current_size", "status", "actions", "path")
        self.files_tree = ttk.Treeview(files_frame, columns=queue_columns, show="tree headings", selectmode="extended", height=10)
        headings = {
            "select": "Select",
            "name": "File Name",
            "original_size": "Original Size",
            "current_size": "Current Size",
            "status": "Output Status",
            "actions": "Actions",
            "path": "Path",
        }
        widths = {
            "select": 58,
            "name": 210,
            "original_size": 130,
            "current_size": 170,
            "status": 120,
            "actions": 70,
            "path": 0,
        }
        self.files_tree.heading("#0", text=headings["name"])
        self.files_tree.column("#0", width=widths["name"], minwidth=120, anchor="w", stretch=True)
        for col in queue_columns:
            self.files_tree.heading(col, text=headings[col])
            self.files_tree.column(col, width=widths[col], minwidth=0 if col == "path" else 40, anchor="center" if col in ("select", "actions") else "w", stretch=(col != "path"))
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        files_frame.rowconfigure(0, weight=1)
        files_frame.columnconfigure(0, weight=1)
        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        btns = ttk.Frame(files_frame)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 4))
        ttk.Button(btns, text="Add Files...", command=self.on_add_files).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        ttk.Button(btns, text="Remove", command=self.on_remove_selected).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(btns, text="Clear", command=self.on_clear).grid(row=0, column=2, sticky="ew", padx=(4, 0), pady=2)
        ttk.Button(btns, text="Check All", command=self.on_check_all).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=2)
        ttk.Button(btns, text="Uncheck All", command=self.on_uncheck_all).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(btns, text="Check Selected", command=self.on_check_selected).grid(row=1, column=2, sticky="ew", padx=(4, 0), pady=2)
        for c in range(3):
            btns.columnconfigure(c, weight=1)

        self.files_tree.bind("<Button-1>", self.on_tree_click)
        self.files_tree.bind("<Double-1>", self.on_tree_double_click)
        self.files_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        if DND_AVAILABLE:
            self.files_tree.drop_target_register(DND_FILES)
            self.files_tree.dnd_bind("<<Drop>>", self.on_drop)

        params = ttk.LabelFrame(side, text="Export Settings")
        params.pack(fill="x", pady=(0, 8))
        self._settings_widgets = []

        def make_param_row(label_text, top_pad=False, bottom_pad=False):
            row = ttk.Frame(params)
            row.pack(fill="x", padx=8, pady=((8 if top_pad else 4), (8 if bottom_pad else 4)))
            ttk.Label(row, text=label_text, width=17, anchor="w").pack(side="left", padx=(0, 8))
            return row

        mode_row = ttk.Frame(params)
        mode_row.pack(fill="x", padx=8, pady=(8, 4))
        mode_row.columnconfigure(1, weight=1)
        mode_row.columnconfigure(3, weight=1)

        saved_mode = self._settings.export_mode if self._settings.export_mode in ("Raster", "Vector") else "Raster"
        self.export_mode_var = tk.StringVar(value=saved_mode)
        ttk.Label(mode_row, text="Export Mode", width=12, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 8))
        export_mode_choices = ttk.Frame(mode_row)
        export_mode_choices.grid(row=0, column=1, sticky="w")
        self.export_mode_raster = ttk.Radiobutton(export_mode_choices, text="Raster", variable=self.export_mode_var, value="Raster")
        self.export_mode_vector = ttk.Radiobutton(export_mode_choices, text="Vector", variable=self.export_mode_var, value="Vector")
        self.export_mode_raster.pack(side="left", padx=(0, 10))
        self.export_mode_vector.pack(side="left")
        self._settings_widgets.extend([self.export_mode_raster, self.export_mode_vector])

        saved_overlap_mode = normalize_overlap_mode(getattr(self._settings, "overlap_mode", "Shared"))
        self.overlap_mode_var = tk.StringVar(value=saved_overlap_mode)
        ttk.Label(mode_row, text="Overlap Mode", width=13, anchor="w").grid(row=0, column=2, sticky="w", padx=(18, 8))
        overlap_mode_choices = ttk.Frame(mode_row)
        overlap_mode_choices.grid(row=0, column=3, sticky="w")
        self.overlap_mode_shared = ttk.Radiobutton(overlap_mode_choices, text="Shared", variable=self.overlap_mode_var, value="Shared")
        self.overlap_mode_left = ttk.Radiobutton(overlap_mode_choices, text="Left", variable=self.overlap_mode_var, value="Left")
        self.overlap_mode_shared.pack(side="left", padx=(0, 10))
        self.overlap_mode_left.pack(side="left")
        self._settings_widgets.extend([self.overlap_mode_shared, self.overlap_mode_left])

        self.preserve_vectors_var = tk.BooleanVar(value=(saved_mode == "Vector"))
        self.fit_mode_var = tk.StringVar(value="stretch")

        row = make_param_row("Bleed (mm)", top_pad=True)
        self.bleed_var = tk.StringVar(value=self._settings.bleed_mm)
        self.bleed_entry = ttk.Entry(row, textvariable=self.bleed_var, width=12)
        self.bleed_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.bleed_entry)

        row = make_param_row("Overlap (mm)")
        self.overlap_var = tk.StringVar(value=self._settings.overlap_mm)
        self.overlap_entry = ttk.Entry(row, textvariable=self.overlap_var, width=12)
        self.overlap_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.overlap_entry)

        row = make_param_row("Panel Widths (mm)")
        self.widths_var = tk.StringVar(value="")
        self.widths_entry = ttk.Entry(row, textvariable=self.widths_var, width=24)
        self.widths_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.widths_entry)

        row = make_param_row("Height (mm)")
        self.height_var = tk.StringVar(value="")
        self.height_entry = ttk.Entry(row, textvariable=self.height_var, width=12)
        self.height_entry.pack(side="left", fill="x", expand=True)
        self.reset_size_button = ttk.Button(row, text="Reset Size", command=self.on_reset_size)
        self.reset_size_button.pack(side="left", padx=(6, 0))
        self._settings_widgets.extend([self.height_entry, self.reset_size_button])

        row = make_param_row("DPI")
        self.dpi_var = tk.StringVar(value=self._settings.dpi)
        self.dpi_entry = ttk.Entry(row, textvariable=self.dpi_var, width=12)
        self.dpi_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.dpi_entry)

        row = make_param_row("Export Format")
        saved_format = self._settings.export_format if self._settings.export_format in ("PDF", "JPG", "TIFF") else "PDF"
        self.format_var = tk.StringVar(value=saved_format)
        self.format_combo = ttk.Combobox(row, textvariable=self.format_var, values=["PDF", "JPG", "TIFF"], state="readonly", width=10)
        self.format_combo.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.format_combo)

        row = make_param_row("Output Folder", bottom_pad=True)
        self.outdir_var = tk.StringVar(value=self._settings.last_output_dir or str(Path.cwd() / "output"))
        ttk.Entry(row, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.on_browse_outdir).pack(side="left", padx=(6, 0))

        status_frame = ttk.LabelFrame(side, text="Run")
        status_frame.pack(fill="x", pady=(0, 8))
        self.status_var = tk.StringVar(value="Add files, check items to process, then start export.")
        ttk.Label(status_frame, textvariable=self.status_var, style="Muted.TLabel", wraplength=360).pack(fill="x", padx=8, pady=(8, 6))
        self.progress = ttk.Progressbar(status_frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(status_frame, text="Start Export", command=self.on_start, style="Accent.TButton").pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(status_frame, text="Open Logs Folder", command=self.on_open_logs_folder).pack(fill="x", padx=8, pady=(0, 8))

        log_frame = ttk.LabelFrame(self, text="Activity Log")
        log_frame.pack(fill="both", expand=False, padx=14, pady=(0, 12))
        self.log = tk.Text(log_frame, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        apply_theme(self, self._style, self.theme_var.get())
        self._disable_combobox_wheel_changes()
        self._create_checkbox_images()

        try:
            self.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

        self.widths_var.trace_add("write", self._on_widths_changed)
        self.height_var.trace_add("write", self._on_height_changed)
        self.bleed_var.trace_add("write", self._on_profile_setting_changed)
        self.overlap_var.trace_add("write", self._on_profile_setting_changed)
        self.overlap_mode_var.trace_add("write", self._on_profile_setting_changed)
        self.dpi_var.trace_add("write", self._on_profile_setting_changed)
        self.export_mode_var.trace_add("write", self._on_export_mode_changed)
        self.format_var.trace_add("write", self._on_profile_setting_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_settings_enabled(False)

    def _create_checkbox_images(self):
        colors = getattr(self, "_theme_tokens", get_theme(self.theme_var.get()).colors)
        self._checkbox_images = {}
        for state, checked in (("checked", True), ("unchecked", False)):
            image = tk.PhotoImage(width=16, height=16)
            border = colors.get("fg", "#000000")
            bg = colors.get("tree_bg", colors.get("panel", "#ffffff"))
            fill = colors.get("accent", "#357abd")
            image.put(bg, to=(0, 0, 16, 16))
            image.put(border, to=(2, 2, 14, 3))
            image.put(border, to=(2, 13, 14, 14))
            image.put(border, to=(2, 2, 3, 14))
            image.put(border, to=(13, 2, 14, 14))
            if checked:
                for x, y in [(5, 8), (6, 9), (7, 10), (8, 9), (9, 8), (10, 7), (11, 6)]:
                    image.put(fill, to=(x, y, x + 2, y + 2))
            self._checkbox_images[state] = image

    def _checkbox_text(self, selected: bool) -> str:
        return "☑" if selected else "☐"

    def _disable_combobox_wheel_changes(self):
        def block_scroll(_event):
            return "break"

        self.bind_class("TCombobox", "<MouseWheel>", block_scroll)
        self.bind_class("TCombobox", "<Button-4>", block_scroll)
        self.bind_class("TCombobox", "<Button-5>", block_scroll)

    def _bind_combobox_clear_selection(self, combo):
        def clear_selection(_event=None):
            try:
                combo.selection_clear()
            except Exception:
                pass

        combo.bind("<FocusIn>", clear_selection, add="+")
        combo.bind("<ButtonRelease-1>", lambda _event: self.after_idle(clear_selection), add="+")
        combo.bind("<<ComboboxSelected>>", lambda _event: self.after_idle(clear_selection), add="+")

    def on_open_logs_folder(self):
        log_dir = Path("logs").resolve()
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(log_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(log_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(log_dir)], check=False)
            self.status_var.set(f"Opened logs folder: {log_dir}")
        except Exception as exc:
            messagebox.showerror("Could not open logs folder", f"{log_dir}\n\n{exc}")

    # ---------- Theme ----------
    def _on_theme_changed(self, *_):
        normalized = normalize_theme_name(self.theme_var.get())
        if normalized != self.theme_var.get():
            self.theme_var.set(normalized)
            return
        self.dark_mode.set(get_theme(self.theme_var.get()).is_dark)
        apply_theme(self, self._style, self.theme_var.get())
        if hasattr(self, "files_tree"):
            self._create_checkbox_images()
            for iid in self.files_tree.get_children(""):
                self._update_profile_row(iid)
        self._update_preview()

    def _on_export_mode_changed(self, *_):
        is_vector = self.export_mode_var.get() == "Vector"
        self.preserve_vectors_var.set(is_vector)
        if is_vector and self.format_var.get() != "PDF":
            self.format_var.set("PDF")
        if hasattr(self, "status_var"):
            self.status_var.set("Vector mode stretches PDF artwork to the requested total size." if is_vector else "Raster mode renders panels at the selected DPI.")
        self._save_selected_profile_settings()
        self._update_preview()

    # ---------- Files tree helpers ----------
    def _profile_iids(self):
        return list(self._profiles.keys())

    def _first_profile_iid(self, iid):
        if iid in self._profiles:
            return iid
        for child in self.files_tree.get_children(iid):
            found = self._first_profile_iid(child)
            if found:
                return found
        return None

    def _child_profile_iids(self, iid):
        if iid in self._profiles:
            return [iid]
        return [child for child in self.files_tree.get_children(iid) if child in self._profiles]

    def _add_file_item(self, path: str):
        path = str(Path(path))
        if path in self._file_groups:
            iid = self._file_groups[path]
            self.files_tree.selection_set(iid)
            self.files_tree.focus(iid)
            self.files_tree.see(iid)
            return iid
        try:
            profiles = self._create_profiles(Path(path))
        except Exception as e:
            self.log_print(f"[WARN] Cannot probe {path}: {e}")
            profiles = [
                ArtworkProfile(
                    file_path=path,
                    output_name=Path(path).stem,
                    bleed_mm=self.bleed_var.get(),
                    overlap_mm=self.overlap_var.get(),
                    overlap_mode=self.overlap_mode_var.get(),
                    dpi=self.dpi_var.get(),
                    export_format=self.format_var.get(),
                    export_mode=self.export_mode_var.get(),
                    output_status="Probe failed",
                    validation_state="error",
                )
            ]

        parent = ""
        if len(profiles) > 1:
            parent = self.files_tree.insert(
                "",
                "end",
                text=Path(path).name,
                values=(self._checkbox_text(False), "", "", f"0/{len(profiles)} selected", "Get Names", path),
                open=True,
            )
            self._file_groups[path] = parent
        last_iid = None
        for profile in profiles:
            iid = self.files_tree.insert(parent, "end")
            self._profiles[iid] = profile
            self._update_profile_row(iid)
            last_iid = iid
        if len(profiles) == 1 and last_iid:
            self._file_groups[path] = last_iid
        if last_iid:
            first_new = self.files_tree.get_children(parent)[0] if parent else last_iid
            self.files_tree.selection_set(first_new)
            self.files_tree.focus(first_new)
            self.files_tree.see(first_new)
        return last_iid

    def _create_profiles(self, p: Path) -> list[ArtworkProfile]:
        profiles = core_create_artwork_profiles(
            p,
            bleed_mm=self.bleed_var.get(),
            overlap_mm=self.overlap_var.get(),
            overlap_mode=self.overlap_mode_var.get(),
            dpi=self.dpi_var.get(),
            export_format=self.format_var.get(),
            export_mode=self.export_mode_var.get(),
        )
        for profile in profiles:
            if profile.source_page_count > 1:
                self.log_print(
                    f"[INFO] Source size {p.name} page {profile.source_page_index + 1}/{profile.source_page_count}: "
                    f"width={fmt_mm(profile.original_width_mm)} mm, "
                    f"height={fmt_mm(profile.original_height_mm)} mm"
                )
            else:
                self.log_print(
                    f"[INFO] Source size {p.name}: width={fmt_mm(profile.original_width_mm)} mm, "
                    f"height={fmt_mm(profile.original_height_mm)} mm"
                )
        return profiles

    def _update_profile_row(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            return
        self.files_tree.item(
            iid,
            text=profile.file_name,
            values=(
                self._checkbox_text(profile.selected),
                profile.original_size_label(),
                profile.current_size_label(),
                profile.output_status,
                "Remove",
                profile.file_path,
            ),
        )

    def _update_group_row(self, group_iid):
        children = self._child_profile_iids(group_iid)
        if not children:
            return
        path = self._profiles[children[0]].file_path
        selected = sum(1 for child in children if self._profiles[child].selected)
        status = f"{selected}/{len(children)} selected"
        all_selected = selected == len(children)
        self.files_tree.item(
            group_iid,
            text=Path(path).name,
            values=(self._checkbox_text(all_selected), "", "", status, "Get Names", path),
        )

    def _toggle_item(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            return
        profile.selected = not profile.selected
        self._update_profile_row(iid)
        parent = self.files_tree.parent(iid)
        if parent:
            self._update_group_row(parent)

    def _toggle_group(self, iid):
        children = self._child_profile_iids(iid)
        if not children:
            return
        new_state = not all(self._profiles[child].selected for child in children)
        for child in children:
            self._profiles[child].selected = new_state
            self._update_profile_row(child)
        self._update_group_row(iid)

    def on_tree_click(self, event):
        region = self.files_tree.identify("region", event.x, event.y)
        col = self.files_tree.identify_column(event.x)
        iid = self.files_tree.identify_row(event.y)
        if not iid:
            return None
        if region == "cell" and col == "#1":
            if iid in self._profiles:
                self._toggle_item(iid)
            else:
                self._toggle_group(iid)
            return "break"
        if region == "cell" and col == "#5":
            if iid in self._profiles:
                self._remove_iid(iid)
            else:
                self._apply_illustrator_names_to_group(iid)
            return "break"
        return None

    def on_tree_double_click(self, event):
        region = self.files_tree.identify("region", event.x, event.y)
        col = self.files_tree.identify_column(event.x)
        iid = self.files_tree.identify_row(event.y)
        if region != "tree" or col != "#0" or not iid or iid not in self._profiles:
            return None
        self._begin_name_edit(iid)
        return "break"

    def _begin_name_edit(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            return
        bbox = self.files_tree.bbox(iid, "#0")
        if not bbox:
            return
        x, y, w, h = bbox
        editor = ttk.Entry(self.files_tree)
        editor.insert(0, profile.file_name)
        editor.select_range(0, "end")
        editor.focus_set()
        editor.place(x=x, y=y, width=w, height=h)

        def commit(_event=None):
            try:
                new_name = validate_output_name(editor.get())
            except Exception as exc:
                messagebox.showerror("Invalid output name", str(exc))
                editor.focus_set()
                return "break"
            profile.output_name = new_name
            self._update_profile_row(iid)
            editor.destroy()
            return "break"

        def cancel(_event=None):
            editor.destroy()
            return "break"

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", cancel)

    def _apply_illustrator_names_to_group(self, group_iid):
        children = self._child_profile_iids(group_iid)
        if not children:
            return
        source_path = Path(self._profiles[children[0]].file_path)
        if source_path.suffix.lower() != ".ai":
            messagebox.showinfo("Artboard names", "Illustrator artboard names are only available for .ai files.")
            return
        self.status_var.set(f"Reading Illustrator artboard names from {source_path.name}...")
        self.files_tree.set(group_iid, "actions", "Loading...")

        def finish(names):
            if group_iid not in self.files_tree.get_children("") and not self.files_tree.exists(group_iid):
                return
            if not names:
                self.files_tree.set(group_iid, "actions", "Get Names")
                messagebox.showwarning(
                    "Artboard names unavailable",
                    "Could not read artboard names from Adobe Illustrator. Open Illustrator first, make sure it is responsive, then try again. Numbered queue names were kept.",
                )
                self.status_var.set("Could not read Illustrator artboard names.")
                return
            seen = {}
            current_children = self._child_profile_iids(group_iid)
            for idx, child in enumerate(current_children):
                profile = self._profiles[child]
                fallback = f"{source_path.stem}{profile.source_page_index + 1}" if profile.source_page_count > 1 else source_path.stem
                raw_name = names[idx] if idx < len(names) else fallback
                name = sanitize_output_name(raw_name, fallback)
                count = seen.get(name, 0) + 1
                seen[name] = count
                profile.output_name = name if count == 1 else f"{name}{count}"
                self._update_profile_row(child)
            self._update_group_row(group_iid)
            self.status_var.set(f"Loaded Illustrator artboard names for {source_path.name}.")

        def work():
            names = get_illustrator_artboard_names(source_path, timeout_seconds=20, require_running=True)
            self.after(0, lambda: finish(names))

        threading.Thread(target=work, daemon=True).start()

    def on_tree_select(self, _event=None):
        sel = self.files_tree.selection()
        if not sel:
            self._save_selected_profile_settings()
            self._active_iid = None
            self._set_settings_enabled(False)
            self._bg_preview_im = None
            self._bg_preview_tk = None
            self._update_preview()
            return
        iid = sel[-1]
        if iid not in self._profiles:
            leaf = self._first_profile_iid(iid)
            if not leaf:
                return
            iid = leaf
            self.files_tree.selection_set(iid)
            self.files_tree.focus(iid)
            return
        if iid == self._active_iid:
            return
        self._save_selected_profile_settings()
        self._active_iid = iid
        self._load_profile_into_settings(iid)

    def on_check_selected(self):
        for iid in self.files_tree.selection():
            for child in self._child_profile_iids(iid):
                self._profiles[child].selected = True
                self._update_profile_row(child)
                parent = self.files_tree.parent(child)
                if parent:
                    self._update_group_row(parent)

    def on_uncheck_selected(self):
        for iid in self.files_tree.selection():
            for child in self._child_profile_iids(iid):
                self._profiles[child].selected = False
                self._update_profile_row(child)
                parent = self.files_tree.parent(child)
                if parent:
                    self._update_group_row(parent)

    def on_check_all(self):
        for iid in self._profile_iids():
            profile = self._profiles.get(iid)
            if profile:
                profile.selected = True
                self._update_profile_row(iid)
        for group in self.files_tree.get_children(""):
            if group not in self._profiles:
                self._update_group_row(group)

    def on_uncheck_all(self):
        for iid in self._profile_iids():
            profile = self._profiles.get(iid)
            if profile:
                profile.selected = False
                self._update_profile_row(iid)
        for group in self.files_tree.get_children(""):
            if group not in self._profiles:
                self._update_group_row(group)
    # ---------- Drag & drop / file buttons ----------
    def on_drop(self, event):
        raw = self.tk.splitlist(event.data)
        last = None
        for p in raw:
            p = p.strip("{}").strip()
            if p.lower().endswith((".pdf", ".ai", ".jpg", ".jpeg", ".png", ".tif", ".tiff")):
                last = self._add_file_item(p)
        if last:
            self.files_tree.selection_set(last)

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
            last = self._add_file_item(f)
        if last:
            self.files_tree.selection_set(last)

    def on_remove_selected(self):
        for iid in list(self.files_tree.selection()):
            self._remove_iid(iid)

    def on_clear(self):
        for iid in list(self.files_tree.get_children("")):
            self._remove_iid(iid, select_next=False)
        self._active_iid = None
        self._profiles.clear()
        self._file_groups.clear()
        self._set_settings_enabled(False)
        self._bg_preview_im = None
        self._bg_preview_tk = None
        self._update_preview()

    def _remove_iid(self, iid, select_next=True):
        if iid not in self._profiles:
            for child in list(self.files_tree.get_children(iid)):
                self._remove_iid(child, select_next=False)
            path = self.files_tree.set(iid, "path")
            self._file_groups.pop(path, None)
            try:
                self.files_tree.delete(iid)
            except Exception:
                pass
            return
        if iid == self._active_iid:
            self._active_iid = None
        profile = self._profiles.pop(iid, None)
        parent = self.files_tree.parent(iid)
        try:
            self.files_tree.delete(iid)
        except Exception:
            pass
        if parent:
            if self.files_tree.get_children(parent):
                self._update_group_row(parent)
            else:
                path = self.files_tree.set(parent, "path")
                self._file_groups.pop(path, None)
                self.files_tree.delete(parent)
        elif profile:
            self._file_groups.pop(profile.file_path, None)
        if not select_next:
            return
        children = self._profile_iids()
        if children:
            next_iid = children[0]
            self.files_tree.selection_set(next_iid)
            self.files_tree.focus(next_iid)
        else:
            self._set_settings_enabled(False)
            self._bg_preview_im = None
            self._bg_preview_tk = None
            self._update_preview()

    def on_browse_outdir(self):
        initial = Path(self.outdir_var.get()).expanduser()
        if not initial.exists():
            initial = Path.cwd()
        d = filedialog.askdirectory(title="Choose output folder", initialdir=str(initial))
        if d:
            self.outdir_var.set(d)
            self._save_settings()

    # ---------- Log & parsing ----------
    def log_print(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    # ---------- Artwork profile state ----------
    def _set_settings_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        combo_state = "readonly" if enabled else "disabled"
        for widget in getattr(self, "_settings_widgets", []):
            try:
                if isinstance(widget, ttk.Combobox):
                    widget.configure(state=combo_state)
                else:
                    widget.configure(state=state)
            except Exception:
                pass
        if hasattr(self, "reset_size_button"):
            can_reset = enabled and self._active_profile_has_original_size()
            self.reset_size_button.configure(state=("normal" if can_reset else "disabled"))

    def _active_profile_has_original_size(self) -> bool:
        profile = self._profiles.get(self._active_iid)
        return bool(profile and profile.original_width_mm is not None and profile.original_height_mm is not None)

    def _load_profile_into_settings(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            self._set_settings_enabled(False)
            return
        self._loading_profile = True
        self._syncing = True
        try:
            self.bleed_var.set(profile.bleed_mm)
            self.overlap_var.set(profile.overlap_mm)
            self.overlap_mode_var.set(normalize_overlap_mode(profile.overlap_mode))
            self.widths_var.set(profile.panel_widths)
            self.height_var.set(profile.height_mm)
            self.dpi_var.set(profile.dpi)
            self.format_var.set(profile.export_format)
            self.export_mode_var.set(profile.export_mode)
            self.preserve_vectors_var.set(profile.preserve_vectors)
            self.fit_mode_var.set(profile.vector_fit_mode)
            self._src_w_mm = profile.original_width_mm
            self._src_h_mm = profile.original_height_mm
            self._src_ar = (self._src_w_mm / self._src_h_mm) if self._src_w_mm and self._src_h_mm else None
            self._load_preview_image(Path(profile.file_path), profile.source_page_index)
        finally:
            self._syncing = False
            self._loading_profile = False
        self._set_settings_enabled(True)
        self._update_preview()

    def _load_preview_image(self, p: Path, page_index: int = 0):
        try:
            doc = open_pdf_robust(p)
        except Exception as e:
            self.log_print(f"[WARN] Cannot load preview {p}: {e}")
            self._bg_preview_im = None
            self._bg_preview_tk = None
            return
        try:
            page = doc.load_page(page_index)
            rect = page.rect
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
            self.log_print(f"[WARN] Could not render preview: {p} ({e})")
        finally:
            try:
                doc.close()
            except Exception:
                pass

    def _save_selected_profile_settings(self):
        if self._loading_profile:
            return
        profile = self._profiles.get(self._active_iid)
        if not profile:
            return
        profile.panel_widths = self.widths_var.get()
        profile.height_mm = self.height_var.get()
        profile.bleed_mm = self.bleed_var.get()
        profile.overlap_mm = self.overlap_var.get()
        profile.overlap_mode = normalize_overlap_mode(self.overlap_mode_var.get())
        profile.dpi = self.dpi_var.get()
        profile.export_format = self.format_var.get()
        profile.export_mode = self.export_mode_var.get()
        profile.apply_export_mode_rules()
        self._update_profile_row(self._active_iid)

    def on_reset_size(self):
        profile = self._profiles.get(self._active_iid)
        if not profile or not profile.reset_size_to_original():
            return
        self._loading_profile = True
        self._syncing = True
        try:
            self.widths_var.set(profile.panel_widths)
            self.height_var.set(profile.height_mm)
        finally:
            self._syncing = False
            self._loading_profile = False
        self._update_profile_row(self._active_iid)
        self._update_preview()
    # ---------- Aspect sync (preserve vectors) ----------
    def _on_widths_changed(self, *_):
        self._save_selected_profile_settings()
        self._update_preview()

    def _on_height_changed(self, *_):
        self._save_selected_profile_settings()
        self._update_preview()

    def _on_profile_setting_changed(self, *_):
        self._save_selected_profile_settings()
        self._update_preview()

    def _preview_fit(self):
        self._preview_zoom = 1.0
        self._preview_pan = [0.0, 0.0]
        self._update_preview()

    def _preview_zoom_by(self, factor: float):
        self._preview_zoom = max(0.25, min(8.0, self._preview_zoom * factor))
        self._update_preview()

    def _preview_mousewheel(self, event):
        self._preview_zoom_by(1.12 if event.delta > 0 else 1 / 1.12)

    def _preview_pan_start(self, event):
        self._preview_drag = (event.x, event.y, self._preview_pan[0], self._preview_pan[1])

    def _preview_pan_move(self, event):
        if not self._preview_drag:
            return
        x0, y0, pan_x, pan_y = self._preview_drag
        self._preview_pan = [pan_x + event.x - x0, pan_y + event.y - y0]
        self._update_preview()

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
            self.preview_var.set("Target: -")
            # Clear visual preview on parse error
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
            return
        try:
            height = float(self.height_var.get())
        except Exception:
            height = 0.0

        if not widths:
            self.preview_var.set("Target: -")
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
            return

        bleed_eff = max(0.0, bleed)
        overlap_mode = normalize_overlap_mode(self.overlap_mode_var.get())
        panel_layout, total_w, overlap = compute_panel_layout(widths, bleed_eff, overlap, overlap_mode)
        n = len(panel_layout)
        fit_mode = "stretch"
        pv = self.export_mode_var.get() == "Vector"
        page_h = compute_preview_page_height(total_w, height, bleed_eff, pv, fit_mode, self._src_w_mm, self._src_h_mm)

        if pv and fit_mode == "width":
            h_txt = "(auto by width)"
        else:
            h_txt = fmt_mm(page_h)

        w_txt = fmt_mm(total_w)
        self.preview_var.set(
            f"Target: {w_txt} x {h_txt} mm   |   Panels: {n}   "
            f"(Bleed {fmt_mm(bleed_eff)} / Overlap {fmt_mm(overlap)} {overlap_mode})"
        )

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
        pad = 24
        if total_w_mm <= 0 or page_h_mm <= 0 or cw <= 2 * pad or ch <= 2 * pad:
            return

        # Theme colors
        C = getattr(self, "_theme_tokens", get_theme(self.theme_var.get()).colors)
        border = C.get("preview_border", C.get("border", "#888888"))
        accent = C.get("preview_panel", C.get("accent", "#4da3ff"))
        muted = C.get("preview_content", C.get("muted", "#b7b7b7"))
        overlap_fill = C.get("preview_overlap", "#f5b642")
        bleed_fill = C.get("preview_bleed", "#d64a4a")
        label_bg = C.get("panel", "#222222")
        label_fg = C.get("fg", "#ffffff")

        # Scale to fit and center
        sx = (cw - 2 * pad) / float(total_w_mm)
        sy = (ch - 2 * pad) / float(page_h_mm)
        s = min(sx, sy) * self._preview_zoom
        x0 = pad + (cw - 2 * pad - total_w_mm * s) / 2.0 + self._preview_pan[0]
        y0 = pad + (ch - 2 * pad - page_h_mm * s) / 2.0 + self._preview_pan[1]

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

        # Bleed bands
        if bleed_mm > 0:
            cv.create_rectangle(xx(0), yy(0), xx(bleed_mm), yy(page_h_mm), fill=bleed_fill, stipple="gray25", outline="")
            cv.create_rectangle(xx(max(0.0, total_w_mm - bleed_mm)), yy(0), xx(total_w_mm), yy(page_h_mm), fill=bleed_fill, stipple="gray25", outline="")
            cv.create_rectangle(xx(0), yy(0), xx(total_w_mm), yy(bleed_mm), fill=bleed_fill, stipple="gray25", outline="")
            cv.create_rectangle(xx(0), yy(max(0.0, page_h_mm - bleed_mm)), xx(total_w_mm), yy(page_h_mm), fill=bleed_fill, stipple="gray25", outline="")

        # Shared overlap zones
        for left_panel, right_panel in zip(panel_layout, panel_layout[1:]):
            overlap_left = right_panel["outer_left"]
            overlap_right = left_panel["outer_right"]
            if overlap_right > overlap_left:
                cv.create_rectangle(
                    xx(overlap_left),
                    yy(0),
                    xx(overlap_right),
                    yy(page_h_mm),
                    fill=overlap_fill,
                    stipple="gray25",
                    outline=overlap_fill,
                )

        # Page outline / final full artwork size
        cv.create_rectangle(xx(0), yy(0), xx(total_w_mm), yy(page_h_mm), outline=border, width=2)

        # Panels
        for idx, panel in enumerate(panel_layout, 1):
            outer_left = panel["outer_left"]
            outer_right = panel["outer_right"]
            cv.create_rectangle(xx(outer_left), yy(0), xx(outer_right), yy(page_h_mm), outline=accent, width=2)
            mid_x = (outer_left + outer_right) / 2.0
            label_y = 12 / max(s, 0.01)
            label = f"Panel {idx}"
            text_id = cv.create_text(xx(mid_x), yy(label_y), text=label, fill=label_fg, font=("Segoe UI", 10, "bold"))
            bx0, by0, bx1, by1 = cv.bbox(text_id)
            cv.create_rectangle(bx0 - 5, by0 - 3, bx1 + 5, by1 + 3, fill=label_bg, outline=accent)
            cv.tag_raise(text_id)

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
            cv.create_line(xx(outer_left), yy(0), xx(outer_left), yy(page_h_mm), fill=accent, width=1)
            cv.create_line(xx(outer_right), yy(0), xx(outer_right), yy(page_h_mm), fill=accent, width=1)

    # ---------- Run ----------
    def _validate_profile_for_export(self, profile: ArtworkProfile):
        profile.validate_output_name()
        bleed_mm = float(profile.bleed_mm)
        widths_mm = parse_widths_list(profile.panel_widths)
        height_mm = float(profile.height_mm)
        overlap_txt = profile.overlap_mm.strip()
        overlap_mm = (2 * bleed_mm) if overlap_txt == "" else float(overlap_txt)
        overlap_mode = normalize_overlap_mode(profile.overlap_mode)
        export_fmt = profile.export_format.lower()
        preserve_vectors = profile.export_mode == "Vector"
        dpi_txt = profile.dpi.strip()
        if preserve_vectors:
            try:
                dpi = int(dpi_txt) if dpi_txt else 72
            except ValueError:
                dpi = 72
        else:
            if not dpi_txt:
                raise ValueError("DPI is required for Raster export.")
            dpi = int(dpi_txt)
        if bleed_mm < 0:
            raise ValueError("Bleed must be 0 or greater.")
        if overlap_mm < 0:
            raise ValueError("Overlap must be 0 or greater.")
        if not widths_mm or any(w <= 0 for w in widths_mm):
            raise ValueError("Panel widths must contain one or more positive numbers.")
        if height_mm <= 0:
            raise ValueError("Height must be greater than 0.")
        if not preserve_vectors and dpi <= 0:
            raise ValueError("DPI must be greater than 0.")
        if preserve_vectors:
            export_fmt = "pdf"
        return bleed_mm, widths_mm, height_mm, overlap_mm, overlap_mode, dpi, export_fmt, preserve_vectors

    def on_start(self):
        self._save_selected_profile_settings()
        checked_items = [(iid, p) for iid, p in self._profiles.items() if p.selected]
        if not checked_items:
            msg = "Tick the checkbox next to the file(s) you want to process."
            self.status_var.set(msg)
            messagebox.showwarning("No files selected", msg)
            return

        export_jobs = []
        try:
            for iid, profile in checked_items:
                values = self._validate_profile_for_export(profile)
                export_jobs.append((iid, profile, values))
                profile.validation_state = "valid"
                self._update_profile_row(iid)
        except Exception as e:
            msg = str(e) if str(e) else "Please check bleed, overlap, panel widths, height, DPI, and format."
            self.status_var.set(msg)
            messagebox.showerror("Invalid parameters", msg)
            return

        outdir = Path(self.outdir_var.get()).expanduser()
        outdir.mkdir(parents=True, exist_ok=True)
        self._save_settings()

        self.progress["value"] = 0
        self.progress["maximum"] = len(export_jobs)
        self.status_var.set(f"Exporting {len(export_jobs)} file(s)...")

        def work():
            count = 0
            errors = 0
            for i, (iid, profile, values) in enumerate(export_jobs, 1):
                bleed_mm, widths_mm, height_mm, overlap_mm, overlap_mode, dpi, export_fmt, preserve_vectors = values
                try:
                    profile.output_status = "Processing"
                    self._update_profile_row(iid)
                    self.status_var.set(f"Processing {profile.file_name} ({i}/{len(export_jobs)})")
                    process_file(
                        Path(profile.file_path),
                        bleed_mm=bleed_mm,
                        widths_mm=widths_mm,
                        height_mm=height_mm,
                        overlap_mm=overlap_mm,
                        overlap_mode=overlap_mode,
                        dpi=dpi,
                        output_root=outdir,
                        export_fmt=export_fmt,
                        preserve_vectors=preserve_vectors,
                        vector_fit_mode="stretch",
                        page_index=profile.source_page_index,
                        output_name=profile.file_name,
                        log_cb=self.log_print,
                    )
                    profile.output_status = "Done"
                    profile.validation_state = "valid"
                    count += 1
                except Exception as e:
                    errors += 1
                    profile.output_status = "Error"
                    profile.validation_state = "error"
                    self.log_print(f"[ERROR] {profile.file_path}: {e}")
                finally:
                    self._update_profile_row(iid)
                    self.progress["value"] = i
            self.log_print("")
            self.log_print(f"Done. Processed {count}/{len(export_jobs)} file(s). Outputs in: {outdir}")
            self.status_var.set(f"Done. {count} succeeded, {errors} failed. Outputs: {outdir}")

        threading.Thread(target=work, daemon=True).start()

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()




