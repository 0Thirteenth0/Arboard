from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PNG_PATH = ASSETS / "artboard_cutter_icon.png"
ICO_PATH = ASSETS / "artboard_cutter.ico"


def rounded_rectangle_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def make_icon(size: int = 1024) -> Image.Image:
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    bg = Image.new("RGBA", (size, size), (24, 31, 43, 255))
    bg_mask = rounded_rectangle_mask(size, int(190 * scale))
    image.alpha_composite(Image.composite(bg, Image.new("RGBA", (size, size)), bg_mask))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (int(-120 * scale), int(-140 * scale), int(680 * scale), int(620 * scale)),
        fill=(58, 183, 255, 72),
    )
    glow_draw.ellipse(
        (int(400 * scale), int(360 * scale), int(1140 * scale), int(1120 * scale)),
        fill=(28, 222, 185, 64),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(int(60 * scale)))
    image.alpha_composite(glow)

    draw = ImageDraw.Draw(image)

    # Three staggered production panels.
    panels = [
        ((160, 260, 392, 760), (78, 177, 255, 245)),
        ((388, 206, 622, 706), (34, 215, 179, 245)),
        ((616, 150, 848, 650), (112, 136, 255, 245)),
    ]
    for box, color in panels:
        scaled = tuple(int(v * scale) for v in box)
        shadow = tuple(int((v + 18) * scale) for v in box)
        draw.rounded_rectangle(shadow, radius=int(26 * scale), fill=(0, 0, 0, 80))
        draw.rounded_rectangle(scaled, radius=int(26 * scale), fill=color, outline=(238, 246, 255, 255), width=max(3, int(9 * scale)))
        inset = int(28 * scale)
        draw.line(
            (scaled[0] + inset, scaled[1] + inset, scaled[2] - inset, scaled[1] + inset),
            fill=(255, 255, 255, 135),
            width=max(2, int(7 * scale)),
        )

    # Cutter path through the panels.
    blade = [(250, 810), (790, 220), (880, 306), (342, 900)]
    blade = [(int(x * scale), int(y * scale)) for x, y in blade]
    draw.polygon(blade, fill=(245, 248, 252, 255))
    edge = [(790, 220), (880, 306), (832, 356), (744, 270)]
    edge = [(int(x * scale), int(y * scale)) for x, y in edge]
    draw.polygon(edge, fill=(64, 76, 91, 255))
    draw.line(
        (int(298 * scale), int(812 * scale), int(806 * scale), int(258 * scale)),
        fill=(23, 31, 43, 130),
        width=max(3, int(12 * scale)),
    )

    # Registration dot.
    draw.ellipse(
        (int(142 * scale), int(792 * scale), int(222 * scale), int(872 * scale)),
        fill=(255, 255, 255, 255),
        outline=(58, 183, 255, 255),
        width=max(3, int(9 * scale)),
    )

    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    base = make_icon()
    base.save(PNG_PATH)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(ICO_PATH, sizes=sizes)
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICO_PATH}")


if __name__ == "__main__":
    main()
