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

# ---------------------- Units & helpers ----------------------

PT_PER_MM = 72.0 / 25.4
MAX_MP = 150  # safety cap per render in megapixels (adjust if needed)


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


# ---------------------- Core processing ----------------------
# Raster (non-uniform) path
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

    n = len(widths_mm)
    min_w_t_mm = min((w + 2 * bleed_mm) for w in widths_mm)
    if overlap_mm < 0:
        overlap_mm = 0.0
    if overlap_mm >= min_w_t_mm:
        overlap_mm = max(0.0, min_w_t_mm - 0.01)

    target_w_mm = sum(w + 2 * bleed_mm for w in widths_mm) - overlap_mm * (n - 1)
    target_h_mm = height_mm + 2 * bleed_mm
    target_w_pt = mm_to_pt(target_w_mm)
    target_h_pt = mm_to_pt(target_h_mm)

    sx, sy = compute_scale_matrix(src_rect, target_w_pt, target_h_pt)
    M = fitz.Matrix(sx, sy)
    clip_h_pt = mm_to_pt(target_h_mm)

    x_cursor_mm = 0.0
    for idx, w_mm in enumerate(widths_mm):
        w_t_mm = w_mm + 2 * bleed_mm
        x0_t = mm_to_pt(x_cursor_mm)
        x1_t = mm_to_pt(x_cursor_mm + w_t_mm)
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

        pix = page.get_pixmap(matrix=M, clip=clip_src, dpi=eff_dpi, alpha=False)

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
            pix.save(outdir / out_name)

        if log_cb:
            log_cb(
                f"[CROP] {out_name}: x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  dpi={eff_dpi}"
            )

        x_cursor_mm += w_t_mm - overlap_mm


# Vector (uniform) path
def export_artboards_vector_uniform(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    base_name,
    outdir: Path,
    log_cb=None,
):
    page = src_doc.load_page(0)
    src_rect = page.rect

    n = len(widths_mm)
    min_w_t_mm = min((w + 2 * bleed_mm) for w in widths_mm)
    if overlap_mm < 0:
        overlap_mm = 0.0
    if overlap_mm >= min_w_t_mm:
        overlap_mm = max(0.0, min_w_t_mm - 0.01)

    target_w_mm = sum(w + 2 * bleed_mm for w in widths_mm) - overlap_mm * (n - 1)
    target_h_mm = height_mm + 2 * bleed_mm
    target_h_pt = mm_to_pt(target_h_mm)

    s = target_h_pt / float(src_rect.height) if src_rect.height else 1.0
    clip_h_pt = target_h_pt

    x_cursor_mm = 0.0
    for idx, w_mm in enumerate(widths_mm):
        w_t_mm = w_mm + 2 * bleed_mm
        x0_t = mm_to_pt(x_cursor_mm)
        x1_t = mm_to_pt(x_cursor_mm + w_t_mm)
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
                f"[CROP] {out_name} (VECTOR): x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  scale={s:.6f}"
            )

        x_cursor_mm += w_t_mm - overlap_mm


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
        n = len(widths_mm)
        target_w_mm = sum(w + 2 * bleed_mm for w in widths_mm) - overlap_mm * (n - 1)
        target_h_mm = height_mm + 2 * bleed_mm
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
            log_cb(f"Target full size: {pt_to_mm(target_w_pt):.1f} × {pt_to_mm(target_h_pt):.1f} mm")
            log_cb(f"Mode: {'VECTOR (uniform)' if preserve_vectors else 'RASTER (non-uniform)'}  Export as: {export_fmt.upper()}  Output dir: {output_root}")

        base_name = file_path.stem
        outdir = output_root
        outdir.mkdir(parents=True, exist_ok=True)

        if preserve_vectors:
            export_artboards_vector_uniform(
                src, widths_mm, height_mm, bleed_mm, overlap_mm, base_name, outdir, log_cb
            )
        else:
            export_artboards_streaming_from_src(
                src, widths_mm, height_mm, bleed_mm, overlap_mm, base_name, outdir, dpi, export_fmt, log_cb
            )

        if log_cb:
            log_cb(f"✔ Done: {file_path.name}")
    finally:
        try:
            src.close()
        except Exception:
            pass


# ---------------------- GUI ----------------------

class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("Artboard Cutter")
        self.geometry("1020x760")
        self.minsize(940, 680)

        # state for aspect ratio sync
        self._src_w_mm = None
        self._src_h_mm = None
        self._src_ar = None
        self._syncing = False  # guard for trace

        # Top frame
        top = ttk.Frame(self)
        top.pack(fill="both", expand=False, padx=10, pady=(10, 6))

        # ---- Files Tree (checkbox via Unicode) ----
        files_frame = ttk.LabelFrame(top, text="Files")
        files_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)

        # First column (#0) will show "☐ filename" / "☑ filename"
        self.files_tree = ttk.Treeview(files_frame, columns=("path",), show="tree headings", selectmode="extended", height=10)
        self.files_tree.heading("#0", text="Process")
        self.files_tree.heading("path", text="Path")
        self.files_tree.column("#0", width=320, anchor="w")
        self.files_tree.column("path", width=640, anchor="w")
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        files_frame.rowconfigure(0, weight=1)
        files_frame.columnconfigure(0, weight=1)

        # checkbox state: iid -> bool
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

        # click handlers
        self.files_tree.bind("<Button-1>", self.on_tree_click)     # toggle checkbox
        self.files_tree.bind("<<TreeviewSelect>>", self.on_tree_select)  # autofill

        if DND_AVAILABLE:
            self.files_tree.drop_target_register(DND_FILES)
            self.files_tree.dnd_bind("<<Drop>>", self.on_drop)

        # ---- Parameters ----
        params = ttk.LabelFrame(top, text="Parameters")
        params.grid(row=0, column=1, sticky="nsew")

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

        ttk.Label(params, text='Output folder:').grid(row=7, column=0, sticky='w', padx=6, pady=4)
        self.outdir_var = tk.StringVar(value=str(Path.cwd() / "output"))
        out_row = ttk.Frame(params)
        out_row.grid(row=7, column=1, sticky="ew", padx=6, pady=4)
        ttk.Entry(out_row, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True)
        ttk.Button(out_row, text="Browse…", command=self.on_browse_outdir).pack(side="left", padx=(6, 0))

        for r in range(8):
            params.rowconfigure(r, weight=0)
        params.columnconfigure(1, weight=1)

        # Progress + Start
        run_bar = ttk.Frame(self)
        run_bar.pack(fill="x", padx=10, pady=(0, 6))
        self.progress = ttk.Progressbar(run_bar, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Button(run_bar, text="Start", command=self.on_start).pack(side="left", padx=8)

        # Log
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        try:
            self.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

        # Aspect sync traces
        self.widths_var.trace_add("write", self._on_widths_changed)
        self.height_var.trace_add("write", self._on_height_changed)

    # ---------- Files tree helpers ----------
    def _add_file_item(self, path: str):
        # avoid duplicates
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
        # toggle checkbox only if clicking the first (tree) column
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
                self._add_file_item(p)  # add unchecked
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
            self._add_file_item(f)  # add unchecked
            last = f
        if last:
            self.autofill_dims_from_path(Path(last))

    def on_remove_selected(self):
        for iid in list(self.files_tree.selection()):
            self.files_tree.delete(iid)
            self._checked.pop(iid, None)

    def on_clear(self):
        for iid in list(self.files_tree.get_children("")):
            self.files_tree.delete(iid)
        self._checked.clear()

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

    def parse_widths(self, s: str):
        chunks = [c.strip() for c in s.replace(",", " ").split() if c.strip()]
        return [float(c) for c in chunks]

    # ---------- Auto-fill size ----------
    def autofill_dims_from_path(self, p: Path):
        try:
            doc = open_pdf_robust(p)
        except Exception as e:
            self.log_print(f"[WARN] Cannot probe {p}: {e}")
            return
        try:
            page = doc.load_page(0)
            rect = page.rect
            w_mm = pt_to_mm(rect.width)
            h_mm = pt_to_mm(rect.height)

            self._src_w_mm = float(w_mm)
            self._src_h_mm = float(h_mm)
            self._src_ar = (self._src_w_mm / self._src_h_mm) if self._src_h_mm else None

            self._syncing = True
            self.widths_var.set(fmt_mm(w_mm))   # single width by default
            self.height_var.set(fmt_mm(h_mm))   # page height
            self._syncing = False

            ar_txt = f"{self._src_ar:.6f}" if self._src_ar else "n/a"
            self.log_print(f"[INFO] Auto-filled from {p.name}: width={fmt_mm(w_mm)} mm, height={fmt_mm(h_mm)} mm (AR={ar_txt})")
        except Exception as e:
            self.log_print(f"[WARN] Could not read size: {p} ({e})")
        finally:
            try:
                doc.close()
            except Exception:
                pass

    # ---------- Aspect sync (preserve vectors) ----------
    def _on_widths_changed(self, *_):
        if self._syncing or not self.preserve_vectors_var.get():
            return
        try:
            parts = self.parse_widths(self.widths_var.get())
        except Exception:
            return
        if len(parts) != 1 or not self._src_ar or self._src_ar <= 0:
            return
        try:
            new_w = float(parts[0])
        except Exception:
            return
        new_h = new_w / self._src_ar
        self._syncing = True
        self.height_var.set(fmt_mm(new_h))
        self._syncing = False

    def _on_height_changed(self, *_):
        if self._syncing or not self.preserve_vectors_var.get():
            return
        try:
            parts = self.parse_widths(self.widths_var.get())
        except Exception:
            return
        if len(parts) != 1 or not self._src_ar or self._src_ar <= 0:
            return
        try:
            new_h = float(self.height_var.get())
        except Exception:
            return
        new_w = new_h * self._src_ar
        self._syncing = True
        self.widths_var.set(fmt_mm(new_w))
        self._syncing = False

    # ---------- Run ----------
    def on_start(self):
        # Only process CHECKED items
        checked_paths = []
        for iid in self.files_tree.get_children(""):
            if self._checked.get(iid, False):
                checked_paths.append(self.files_tree.set(iid, "path"))
        if not checked_paths:
            messagebox.showwarning("No files selected", "Tick the checkbox next to the file(s) you want to process.")
            return

        try:
            bleed_mm = float(self.bleed_var.get())
            widths_mm = self.parse_widths(self.widths_var.get())
            height_mm = float(self.height_var.get())
            overlap_txt = self.overlap_var.get().strip()
            overlap_mm = (2 * bleed_mm) if overlap_txt == "" else float(overlap_txt)
            dpi = int(self.dpi_var.get())
            export_fmt = self.format_var.get().lower()
            preserve_vectors = bool(self.preserve_vectors_var.get())
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
