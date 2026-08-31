import unittest
import tkinter as tk
import tempfile
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from src.artboard_cutter_core.themes import THEME_NAMES, get_theme
from tests.helpers import is_windows, make_grid_pdf


class GuiSmokeTests(unittest.TestCase):
    def _make_app_or_skip(self):
        from artboard_cutter_gui_advanced import App

        try:
            app = App()
            app.withdraw()
            app.update_idletasks()
            return app
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable for interactive GUI smoke tests: {exc}")

    def test_interactive_app_can_launch_and_close(self):
        app = self._make_app_or_skip()
        try:
            self.assertEqual(app.title(), "Artboard Cutter")
            self.assertTrue(hasattr(app, "preview_canvas"))
            self.assertTrue(hasattr(app, "files_tree"))
            self.assertFalse(hasattr(app, "layout_template_combo"))
            self.assertEqual(app.panel_count_spin.cget("style"), "PanelCount.TSpinbox")
            self.assertEqual(
                app._style.lookup("PanelCount.TSpinbox", "fieldbackground").lower(),
                app._theme_tokens["input_bg"].lower(),
            )
            self.assertEqual(
                app._style.lookup("PanelCount.TSpinbox", "foreground").lower(),
                app._theme_tokens["text_primary"].lower(),
            )
        finally:
            app.destroy()

    def test_startup_job_argument_loads_saved_queue(self):
        from artboard_cutter_gui_advanced import App
        from src.artboard_cutter_core.jobs import save_job
        from src.artboard_cutter_core.profiles import ArtworkProfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.pdf"
            job = root / "My Saved Queue.artboard-job"
            make_grid_pdf(source, width_mm=100, height_mm=60)
            save_job(
                job,
                [
                    ArtworkProfile(
                        file_path=str(source),
                        output_name="ExplorerLaunch",
                        panel_widths="50 50",
                        height_mm="60",
                    )
                ],
            )

            try:
                with patch(
                    "artboard_cutter_gui_advanced.default_recovery_job_path",
                    return_value=root / "recovery.artboard-job.json",
                ):
                    app = App(startup_job=job)
                    app.withdraw()
            except tk.TclError as exc:
                self.skipTest(f"Tk unavailable for interactive GUI smoke tests: {exc}")
            try:
                deadline = time.monotonic() + 3
                while not app._profiles and time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.01)
                self.assertEqual(len(app._profiles), 1)
                profile = next(iter(app._profiles.values()))
                self.assertEqual(profile.output_name, "ExplorerLaunch")
                self.assertEqual(app.status_var.get(), "Loaded job: My Saved Queue.artboard-job")
            finally:
                app.destroy()

    def test_export_preset_does_not_change_artwork_size_or_output_folder(self):
        app = self._make_app_or_skip()
        try:
            from src.artboard_cutter_core.profiles import ArtworkProfile

            iid = app.files_tree.insert("", "end")
            app._profiles[iid] = ArtworkProfile(
                file_path="diagnostic.pdf",
                output_name="diagnostic",
                panel_widths="400 600",
                height_mm="800",
            )
            app._active_iid = iid
            app.widths_var.set("400 600")
            app.height_var.set("800")
            app.outdir_var.set("C:/CurrentOutput")
            app._settings.presets = {
                "Export only": {
                    "bleed_mm": "12",
                    "overlap_mm": "24",
                    "panel_widths": "1 2 3",
                    "height_mm": "4",
                    "last_output_dir": "C:/WrongOutput",
                    "dpi": "300",
                }
            }
            app.preset_var.set("Export only")
            app._update_preview = lambda *_args: None

            app.on_apply_preset()

            self.assertEqual(app.widths_var.get(), "400 600")
            self.assertEqual(app.height_var.get(), "800")
            self.assertEqual(app.outdir_var.get(), "C:/CurrentOutput")
            self.assertEqual(app.bleed_var.get(), "12")
            self.assertEqual(app.overlap_var.get(), "24")
            self.assertEqual(app.dpi_var.get(), "300")
        finally:
            app.destroy()

    def test_removing_a_multi_page_group_does_not_access_deleted_parent(self):
        app = self._make_app_or_skip()
        try:
            from src.artboard_cutter_core.profiles import ArtworkProfile

            parent = app.files_tree.insert("", "end", text="multi.pdf", values=("", "", "", "", "", "multi.pdf"))
            for page_index in range(2):
                child = app.files_tree.insert(parent, "end")
                app._profiles[child] = ArtworkProfile(
                    file_path="multi.pdf",
                    output_name=f"page{page_index + 1}",
                    source_page_index=page_index,
                    source_page_count=2,
                )
            app._file_groups["multi.pdf"] = parent
            app.files_tree.selection_set(parent)

            app.on_remove_selected()

            self.assertEqual(app.files_tree.get_children(""), ())
            self.assertEqual(app._profiles, {})
            self.assertNotIn("multi.pdf", app._file_groups)
        finally:
            app.destroy()

    def test_cancelled_batch_marks_unstarted_jobs_interrupted(self):
        app = self._make_app_or_skip()
        try:
            jobs = [SimpleNamespace(iid="one"), SimpleNamespace(iid="two"), SimpleNamespace(iid="three")]
            app._mark_jobs_interrupted(jobs, 1)
            events = [app._export_events.get_nowait(), app._export_events.get_nowait()]
            self.assertEqual(events[0], ("job_state", "two", "Interrupted", "pending"))
            self.assertEqual(events[1], ("job_state", "three", "Interrupted", "pending"))
        finally:
            app.destroy()

    def test_clear_invalidates_inflight_import_results(self):
        app = self._make_app_or_skip()
        try:
            from src.artboard_cutter_core.profiles import ArtworkProfile

            old_generation = app._import_generation
            app._pending_import_paths.add("late.pdf")
            app.on_clear()
            app._insert_imported_profiles(
                "late.pdf",
                [ArtworkProfile(file_path="late.pdf", output_name="late")],
                None,
                {},
                import_generation=old_generation,
            )

            self.assertEqual(app._profiles, {})
            self.assertEqual(app.files_tree.get_children(""), ())
        finally:
            app.destroy()

    def test_preview_handles_non_finite_input_without_callback_errors(self):
        app = self._make_app_or_skip()
        try:
            app.widths_var.set("100")
            app.height_var.set("100")
            app.bleed_var.set("nan")

            app._update_preview()

            self.assertIn("Invalid dimensions", app.preview_var.get())
            self.assertIsNone(app._preview_view)
        finally:
            app.destroy()

    def test_gui_batch_exports_every_tiff_panel(self):
        app = self._make_app_or_skip()
        with tempfile.TemporaryDirectory() as td:
            try:
                from src.artboard_cutter_core.profiles import ArtworkProfile

                root = Path(td)
                source_path = root / "gui-source.pdf"
                output_dir = root / "out"
                make_grid_pdf(source_path, width_mm=200, height_mm=100)
                profile = ArtworkProfile(
                    file_path=str(source_path),
                    output_name="GuiTiff",
                    original_width_mm=200,
                    original_height_mm=100,
                    panel_widths="100 100",
                    height_mm="100",
                    dpi="72",
                    export_format="TIFF",
                    raster_export_format="TIFF",
                    selected=True,
                )
                iid = app._insert_imported_profiles(str(source_path), [profile], None, {})
                app._active_iid = iid
                app._load_profile_into_settings(iid)
                app.outdir_var.set(str(output_dir))

                with patch("artboard_cutter_gui_advanced.messagebox.askyesno", return_value=True):
                    app.on_start()
                    deadline = time.monotonic() + 15
                    while app._export_running and time.monotonic() < deadline:
                        app.update()
                        time.sleep(0.01)

                self.assertFalse(app._export_running, "GUI export did not finish before the diagnostic timeout")
                self.assertEqual(profile.output_status, "Done")
                self.assertFalse((output_dir / "GuiTiff_1.pdf").exists())
                for panel_index in (1, 2):
                    output = output_dir / f"GuiTiff_{panel_index}.tif"
                    self.assertTrue(output.exists())
                    with Image.open(output) as image:
                        self.assertTrue(any(low != high for low, high in image.convert("RGB").getextrema()))
            finally:
                app.destroy()

    def test_clean_close_removes_recovery_file(self):
        app = self._make_app_or_skip()
        with tempfile.TemporaryDirectory() as td:
            recovery_path = Path(td) / "session-recovery.artboard-job.json"
            recovery_path.write_text("{}", encoding="utf-8")
            app._recovery_path = recovery_path
            app._save_settings = lambda: None

            app._close_cleanly()

            self.assertFalse(recovery_path.exists())

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
                if not any(lo != hi for lo, hi in extrema):
                    self.skipTest("Desktop screenshot capture returned a uniform frame.")
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
            if unique_snapshots == 1:
                self.skipTest("Desktop screenshot capture did not reflect theme changes.")
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

    def test_panel_count_spinbox_matches_each_theme(self):
        app = self._make_app_or_skip()
        try:
            for theme_name in THEME_NAMES:
                with self.subTest(theme=theme_name):
                    app.theme_var.set(theme_name)
                    app.update_idletasks()
                    colors = get_theme(theme_name).colors
                    self.assertEqual(
                        app._style.lookup("PanelCount.TSpinbox", "fieldbackground").lower(),
                        colors["input_bg"].lower(),
                    )
                    self.assertEqual(
                        app._style.lookup("PanelCount.TSpinbox", "foreground").lower(),
                        colors["text_primary"].lower(),
                    )
                    self.assertEqual(
                        app._style.lookup("PanelCount.TSpinbox", "arrowcolor").lower(),
                        colors["text_primary"].lower(),
                    )
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
