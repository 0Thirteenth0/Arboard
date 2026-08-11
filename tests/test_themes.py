import unittest

from src.artboard_cutter_core.themes import THEME_NAMES, get_theme, normalize_theme_name


def _hex_to_rgb(color: str):
    color = color.strip().lstrip("#")
    if len(color) != 6:
        raise ValueError(f"Only #RRGGBB colors are supported in theme tests: {color!r}")
    return tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _linearize(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def contrast_ratio(foreground: str, background: str) -> float:
    fr, fg, fb = (_linearize(c) for c in _hex_to_rgb(foreground))
    br, bg, bb = (_linearize(c) for c in _hex_to_rgb(background))
    lum_f = 0.2126 * fr + 0.7152 * fg + 0.0722 * fb
    lum_b = 0.2126 * br + 0.7152 * bg + 0.0722 * bb
    lighter, darker = sorted((lum_f, lum_b), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class ThemeTests(unittest.TestCase):
    def test_required_themes_exist(self):
        for name in [
            "Soft Blue",
            "Minimal Light",
            "Dark Pro",
            "Industrial Gray",
            "Blueprint",
            "Professional Dark",
            "Professional Light",
            "Graphite",
            "Midnight",
            "Neutral Gray",
            "High Contrast",
            "Soft Blue",
            "Warm Dark",
        ]:
            self.assertIn(name, THEME_NAMES)

    def test_legacy_and_invalid_theme_fallback(self):
        self.assertEqual(normalize_theme_name("dark"), "Dark Pro")
        self.assertEqual(normalize_theme_name("light"), "Minimal Light")
        self.assertEqual(normalize_theme_name("missing"), "Soft Blue")

    def test_design_tokens_are_defined(self):
        required = [
            "app_bg",
            "background",
            "card_bg",
            "card_border",
            "canvas_bg",
            "surface",
            "surface_raised",
            "border",
            "text_primary",
            "text_secondary",
            "text_muted",
            "accent",
            "accent_hover",
            "button_bg",
            "button_hover",
            "primary_button_bg",
            "primary_button_hover",
            "input_bg",
            "input_border",
            "table_header_bg",
            "table_row_bg",
            "table_selected_bg",
            "scrollbar",
            "selection_bg",
            "warning",
            "error",
            "success",
        ]
        for name in THEME_NAMES:
            colors = get_theme(name).colors
            for token in required:
                self.assertIn(token, colors, f"{name} missing token {token}")

    def test_preview_tokens_are_defined(self):
        for name in THEME_NAMES:
            colors = get_theme(name).colors
            for token in [
                "preview_bg",
                "preview_border",
                "preview_panel",
                "preview_content",
                "preview_bleed",
                "preview_overlap",
                "preview_label_bg",
                "preview_label_fg",
            ]:
                self.assertIn(token, colors)

    def test_theme_text_contrast_ratios(self):
        pairs = [
            ("fg", "panel", 4.5),
            ("fg", "bg", 4.5),
            ("muted", "panel", 4.5),
            ("entry_fg", "entry_bg", 4.5),
            ("tree_head_fg", "tree_head_bg", 4.5),
            ("fg", "tree_bg", 4.5),
            ("sel_fg", "sel_bg", 4.5),
            ("text_primary", "card_bg", 4.5),
            ("text_muted", "card_bg", 4.5),
            ("text_primary", "button_bg", 4.5),
            ("text_primary", "input_bg", 4.5),
            ("text_primary", "table_header_bg", 4.5),
            ("table_selected_fg", "table_selected_bg", 4.5),
            ("preview_label_fg", "preview_label_bg", 4.5),
        ]
        for name in THEME_NAMES:
            colors = get_theme(name).colors
            for foreground, background, minimum in pairs:
                ratio = contrast_ratio(colors[foreground], colors[background])
                self.assertGreaterEqual(
                    ratio,
                    minimum,
                    (
                        f"{name}: {foreground} on {background} contrast ratio "
                        f"{ratio:.2f} is below {minimum:.1f}"
                    ),
                )

    def test_preview_overlay_contrast_ratios(self):
        pairs = [
            ("preview_border", "preview_bg", 3.0),
            ("preview_panel", "preview_bg", 3.0),
            ("preview_content", "preview_bg", 3.0),
            ("preview_bleed", "preview_bg", 3.0),
            ("preview_overlap", "preview_bg", 3.0),
        ]
        for name in THEME_NAMES:
            colors = get_theme(name).colors
            for foreground, background, minimum in pairs:
                ratio = contrast_ratio(colors[foreground], colors[background])
                self.assertGreaterEqual(
                    ratio,
                    minimum,
                    (
                        f"{name}: {foreground} on {background} preview contrast "
                        f"ratio {ratio:.2f} is below {minimum:.1f}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
