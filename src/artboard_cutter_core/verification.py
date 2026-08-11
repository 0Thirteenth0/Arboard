from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore
from PIL import Image


@dataclass(frozen=True)
class VerificationResult:
    path: Path
    width: int | None
    height: int | None
    dpi: float | None
    color_mode: str
    uniform: bool
    warnings: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        dimensions = f"{self.width}x{self.height}" if self.width and self.height else "PDF"
        dpi = f" @ {self.dpi:.1f} DPI" if self.dpi else ""
        warning = f"; {'; '.join(self.warnings)}" if self.warnings else ""
        return f"Verified {self.path.name}: {dimensions}{dpi}, {self.color_mode}{warning}"


def _thumbnail_is_uniform(path: Path) -> bool:
    if Path(path).suffix.lower() in {".tif", ".tiff"}:
        try:
            import numpy as np
            import tifffile

            first_pixel = None
            with tifffile.TiffFile(str(path)) as tif:
                for segment, _indices, _shape in tif.pages[0].segments():
                    pixels = np.asarray(segment).reshape(-1, segment.shape[-1])
                    if not pixels.size:
                        continue
                    if first_pixel is None:
                        first_pixel = pixels[0].copy()
                    if np.any(pixels != first_pixel):
                        return False
            return True
        except Exception:
            # Fall back to the generic low-resolution renderer if the TIFF
            # decoder is unavailable.
            pass
    doc = fitz.open(str(path))
    try:
        page = doc.load_page(0)
        scale = min(1.0, 128.0 / max(1.0, float(page.rect.width)))
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        value = getattr(pix, "is_unicolor", False)
        return bool(value() if callable(value) else value)
    finally:
        doc.close()


def verify_raster_output(
    path: Path,
    *,
    expected_size: tuple[int, int],
    expected_dpi: int,
    expected_mode: str,
    source_varies: bool,
    expect_icc: bool = False,
) -> VerificationResult:
    output_path = Path(path)
    with Image.open(output_path) as image:
        image.verify()
    with Image.open(output_path) as image:
        actual_size = image.size
        actual_mode = image.mode
        dpi_info = image.info.get("dpi")
        actual_dpi = float(dpi_info[0]) if isinstance(dpi_info, tuple) and dpi_info else None
        icc_profile = image.info.get("icc_profile")

    if actual_size != expected_size:
        raise RuntimeError(f"Output verification failed for {output_path.name}: expected {expected_size}, got {actual_size}.")
    if actual_mode != expected_mode:
        raise RuntimeError(
            f"Output verification failed for {output_path.name}: expected {expected_mode}, got {actual_mode}."
        )
    if actual_dpi is None or abs(actual_dpi - expected_dpi) > 1.0:
        raise RuntimeError(
            f"Output verification failed for {output_path.name}: expected {expected_dpi} DPI, got {actual_dpi}."
        )
    uniform = _thumbnail_is_uniform(output_path)
    if source_varies and uniform:
        raise RuntimeError(
            f"Output verification failed for {output_path.name}: output is blank/uniform but the source crop contains artwork."
        )
    warnings = () if icc_profile or not expect_icc else ("no embedded ICC profile",)
    return VerificationResult(output_path, actual_size[0], actual_size[1], actual_dpi, actual_mode, uniform, warnings)


def verify_pdf_output(path: Path, *, expected_size_pt: tuple[float, float]) -> VerificationResult:
    output_path = Path(path)
    doc = fitz.open(str(output_path))
    try:
        if doc.page_count != 1:
            raise RuntimeError(f"Output verification failed for {output_path.name}: expected one page.")
        page = doc.load_page(0)
        width, height = float(page.rect.width), float(page.rect.height)
        if abs(width - expected_size_pt[0]) > 0.1 or abs(height - expected_size_pt[1]) > 0.1:
            raise RuntimeError(
                f"Output verification failed for {output_path.name}: unexpected PDF page dimensions."
            )
        scale = min(1.0, 128.0 / max(1.0, width))
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        value = getattr(pix, "is_unicolor", False)
        uniform = bool(value() if callable(value) else value)
    finally:
        doc.close()
    return VerificationResult(output_path, None, None, None, "PDF", uniform)
