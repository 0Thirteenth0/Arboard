import unittest
from io import BytesIO

from src.artboard_cutter_core.themes import THEME_NAMES, get_theme
from tests.helpers import is_windows


class GuiSmokeTests(unittest.TestCase):
    def _make_app_or_skip(self):
        try:
            from artboard_cutter_gui_advanced import App

            app = App()
            app.withdraw()
            app.update_idletasks()
            return app
        except Exception as exc:
            self.skipTest(f"Tk unavailable for interactive GUI smoke tests: {exc}")

    def test_interactive_app_can_launch_and_close(self):
        app = self._make_app_or_skip()
        try:
            self.assertEqual(app.title(), "Artboard Cutter")
            self.assertTrue(hasattr(app, "preview_canvas"))
            self.assertTrue(hasattr(app, "files_tree"))
        finally:
            app.destroy()

    def test_preview_snapshot_across_themes(self):
        app = self._make_app_or_skip()
        try:
            try:
                from PIL import ImageChops, ImageGrab
            except Exception as exc:
                self.skipTest(f"Pillow ImageGrab unavailable for preview screenshots: {exc}")

            app.deiconify()
            app.geometry("1200x850")
            app.widths_var.set("100 100")
            app.height_var.set("120")
            app.bleed_var.set("10")
            app.overlap_var.set("20")
            app.export_mode_var.set("Raster")
            app.update_idletasks()

            snapshots = {}
            images = []
            for theme_name in THEME_NAMES:
                app.theme_var.set(theme_name)
                app.update_idletasks()
                app._update_preview()
                app.update_idletasks()
                item_count = len(app.preview_canvas.find_all())
                self.assertGreater(item_count, 8, f"{theme_name}: preview canvas looks blank")
                bbox = (
                    app.preview_canvas.winfo_rootx(),
                    app.preview_canvas.winfo_rooty(),
                    app.preview_canvas.winfo_rootx() + app.preview_canvas.winfo_width(),
                    app.preview_canvas.winfo_rooty() + app.preview_canvas.winfo_height(),
                )
                try:
                    image = ImageGrab.grab(bbox=bbox).convert("RGB")
                except Exception as exc:
                    self.skipTest(f"Preview screenshot capture unavailable: {exc}")
                extrema = image.getextrema()
                self.assertTrue(any(lo != hi for lo, hi in extrema), f"{theme_name}: screenshot is blank")
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                snapshots[theme_name] = buffer.getvalue()
                images.append(image)

                snapshot = app.preview_canvas.postscript(colormode="color")
                self.assertIn("%%BoundingBox", snapshot, f"{theme_name}: missing PostScript bounding box")
                self.assertGreater(len(snapshot), 1000, f"{theme_name}: preview snapshot is unexpectedly small")

                colors = get_theme(theme_name).colors
                bg = app.preview_canvas.cget("bg")
                self.assertEqual(bg.lower(), colors["preview_bg"].lower(), f"{theme_name}: preview background did not apply")

            unique_snapshots = len(set(snapshots.values()))
            self.assertGreater(unique_snapshots, 1, "theme preview snapshots did not change across themes")
            self.assertIsNotNone(ImageChops.difference(images[0], images[-1]).getbbox())
        finally:
            app.destroy()

    def test_high_dpi_windows_scaling_smoke(self):
        if not is_windows():
            self.skipTest("High-DPI Windows scaling check only applies on Windows.")
        app = self._make_app_or_skip()
        try:
            try:
                initial = float(app.tk.call("tk", "scaling"))
                app.tk.call("tk", "scaling", 1.5)
                adjusted = float(app.tk.call("tk", "scaling"))
            except Exception as exc:
                self.skipTest(f"Tk scaling command unavailable: {exc}")
            self.assertGreater(initial, 0.0)
            self.assertGreater(adjusted, 0.0)
            app._update_preview()
            app.update_idletasks()
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
