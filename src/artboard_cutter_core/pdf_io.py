from __future__ import annotations

from pathlib import Path

import fitz


def force_page_boxes(page: fitz.Page) -> None:
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


def page_box_snapshot(page: fitz.Page) -> dict[str, list[float] | int]:
    def rect_values(rect):
        return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]

    data: dict[str, list[float] | int] = {
        "rotation": int(page.rotation),
        "rect": rect_values(page.rect),
    }
    for name in ("mediabox", "cropbox", "bleedbox", "trimbox", "artbox"):
        try:
            data[name] = rect_values(getattr(page, name))
        except Exception:
            pass
    return data

