from __future__ import annotations

try:
    from PIL import Image

    PIL_AVAILABLE = True
    try:
        Image.MAX_IMAGE_PIXELS = None
    except Exception:
        pass
except Exception:
    Image = None
    PIL_AVAILABLE = False


def pixmap_to_pil(pix):
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for this raster operation.")
    if pix.alpha:
        im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        return im.convert("RGB")
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _save_tiff_with_retries(im, out_path, dpi_int: int, log_cb=None):
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
    for big in (True, False):
        for label, extra in compressions:
            kwargs = dict(extra)
            kwargs["dpi"] = (dpi_int, dpi_int)
            if big:
                kwargs["bigtiff"] = True

            try:
                im.save(str(out_path), format="TIFF", **kwargs)
                if log_cb:
                    log_cb(f"[TIFF] saved with {label}{' + BigTIFF' if big else ''}")
                return
            except TypeError as e:
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
    fmt_lower = (fmt_lower or "pdf").lower()
    if fmt_lower in ("jpg", "jpeg"):
        _save_jpg_with_dpi(im, out_path, dpi_int)
        return
    if fmt_lower in ("tif", "tiff"):
        if not PIL_AVAILABLE:
            raise RuntimeError("TIFF export requires Pillow. Install with: pip install Pillow")
        _save_tiff_with_retries(im, out_path, dpi_int, log_cb)
        return
    try:
        im.save(str(out_path), dpi=(dpi_int, dpi_int))
    except Exception:
        im.save(str(out_path))

