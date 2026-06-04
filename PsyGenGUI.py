#!/usr/bin/env python3
"""
PsyGenGUI — a desktop front-end for PsyGenADV.py

A dependency-light Tkinter GUI that drives the pattern/distortion generator.
Designed to be bundled into a standalone executable (e.g. with PyInstaller)
so it runs on Windows, macOS and Linux without a Python install.

Requires: numpy, pillow  (Tkinter ships with the standard library)
The file PsyGenADV.py must sit next to this script.
"""

import os
import sys
import json
import random
import threading
import subprocess
from queue import Queue, Empty
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk

# --------------------------------------------------------------------------- #
# Import the generator module living alongside this file
# --------------------------------------------------------------------------- #
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import PsyGenADV as pg
except ImportError as exc:  # pragma: no cover - defensive
    raise SystemExit(
        "Could not import PsyGenADV.py — make sure it sits next to PsyGenGUI.py.\n"
        f"Original error: {exc}"
    )

APP_NAME = "PsyGenADV"
PREVIEW_MAX_RENDER = 1024   # cap preview render size for responsiveness
PREVIEW_BOX = 480           # on-screen preview dimensions (px)
ZOOM_MIN, ZOOM_MAX = 0.5, 8.0

# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
COLORS = {
    "bg":      "#14101f",
    "panel":   "#1d1730",
    "field":   "#272040",
    "text":    "#e8e3f5",
    "muted":   "#8a82a8",
    "accent":  "#ff3ea5",
    "accent2": "#36e0d0",
    "ok":      "#5ee08a",
    "warn":    "#ffb454",
}


# --------------------------------------------------------------------------- #
# Core generation (mirrors generate_batch in PsyGenADV, with progress hooks)
# --------------------------------------------------------------------------- #
def render_one(size, p_name, d_name, p_zoom, d_zoom, seed=None):
    """Render a single image. Returns (array, pattern_name, distort_name, seed).

    Seeding order matches PsyGenADV.generate_batch so any image is reproducible
    from the seed embedded in its filename.
    """
    if seed is None:
        seed = random.randint(0, 2**31)
    random.seed(seed)
    np.random.seed(seed)

    pattern_name = p_name or random.choice(list(pg.PATTERNS.keys()))
    distort_name = d_name or random.choice(list(pg.DISTORTIONS.keys()))

    arr = pg.PATTERNS[pattern_name](size, zoom=p_zoom)
    arr = pg.DISTORTIONS[distort_name](arr, zoom=d_zoom)
    return arr, pattern_name, distort_name, seed


# --------------------------------------------------------------------------- #
# Config persistence (per-user, platform-appropriate)
# --------------------------------------------------------------------------- #
def config_dir():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", str(Path.home()))
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = config_dir() / "gui_settings.json"


def load_settings():
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save_settings(data):
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass  # never let a settings failure crash the app


def open_in_file_manager(path):
    path = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: type
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:
        messagebox.showinfo("Open folder", f"Couldn't open the folder automatically:\n{path}\n\n{exc}")


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
class PsyGenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PsyGenADV — Pattern Generator")
        self.configure(bg=COLORS["bg"])
        self.minsize(900, 640)

        self.queue = Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.preview_photo = None  # keep a reference so Tk doesn't GC it

        self._build_style()
        self._build_vars()
        self._build_layout()
        self._apply_saved_settings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._poll_queue)

    # ----- styling -------------------------------------------------------- #
    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")  # consistent across platforms, themeable

        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"],
                        fieldbackground=COLORS["field"], font=("Helvetica", 11))
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"],
                        font=("Helvetica", 9))
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["accent"],
                        font=("Helvetica", 20, "bold"))
        style.configure("Sub.TLabel", background=COLORS["bg"], foreground=COLORS["muted"],
                        font=("Helvetica", 10))

        style.configure("TLabelframe", background=COLORS["panel"], foreground=COLORS["accent2"],
                        bordercolor=COLORS["field"], relief="flat")
        style.configure("TLabelframe.Label", background=COLORS["panel"],
                        foreground=COLORS["accent2"], font=("Helvetica", 10, "bold"))

        style.configure("TButton", background=COLORS["field"], foreground=COLORS["text"],
                        bordercolor=COLORS["field"], focuscolor=COLORS["accent"], padding=8)
        style.map("TButton", background=[("active", "#34294f")])

        style.configure("Accent.TButton", background=COLORS["accent"], foreground="#15101e",
                        font=("Helvetica", 11, "bold"), padding=10)
        style.map("Accent.TButton",
                  background=[("active", "#ff6cbb"), ("disabled", COLORS["field"])],
                  foreground=[("disabled", COLORS["muted"])])

        style.configure("TRadiobutton", background=COLORS["panel"], foreground=COLORS["text"])
        style.map("TRadiobutton", background=[("active", COLORS["panel"])])

        style.configure("TCombobox", fieldbackground=COLORS["field"], background=COLORS["field"],
                        foreground=COLORS["text"], arrowcolor=COLORS["accent2"], padding=4)
        style.configure("TSpinbox", fieldbackground=COLORS["field"], foreground=COLORS["text"],
                        arrowcolor=COLORS["accent2"], padding=4)
        style.configure("TEntry", fieldbackground=COLORS["field"], foreground=COLORS["text"], padding=4)

        style.configure("Horizontal.TScale", background=COLORS["panel"])
        style.configure("Accent.Horizontal.TProgressbar", background=COLORS["accent2"],
                        troughcolor=COLORS["field"], bordercolor=COLORS["field"])

    # ----- variables ------------------------------------------------------ #
    def _build_vars(self):
        pattern_opts = ["All (random)"] + list(pg.PATTERNS.keys())
        distort_opts = ["All (random)"] + list(pg.DISTORTIONS.keys())
        self._pattern_opts = pattern_opts
        self._distort_opts = distort_opts

        self.var_pattern = tk.StringVar(value=pattern_opts[0])
        self.var_distort = tk.StringVar(value=distort_opts[0])
        self.var_size = tk.StringVar(value="1024")
        self.var_custom_size = tk.StringVar(value="1024")
        self.var_count = tk.IntVar(value=10)
        self.var_pzoom = tk.DoubleVar(value=1.0)
        self.var_dzoom = tk.DoubleVar(value=1.0)
        self.var_output = tk.StringVar(value=str(Path.cwd() / "backgrounds"))
        self.var_status = tk.StringVar(value="Ready.")
        self.var_pzoom_label = tk.StringVar(value="1.0x")
        self.var_dzoom_label = tk.StringVar(value="1.0x")

    # ----- layout --------------------------------------------------------- #
    def _build_layout(self):
        header = ttk.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill="x")
        ttk.Label(header, text="PsyGenADV", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Randomised psychedelic pattern generator",
                  style="Sub.TLabel").pack(anchor="w")

        body = ttk.Frame(self, padding=(20, 8, 20, 8))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        controls = ttk.Frame(body, style="Panel.TFrame", padding=16)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self._build_controls(controls)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_preview(right)

        # status / progress bar
        footer = ttk.Frame(self, padding=(20, 4, 20, 14))
        footer.pack(fill="x")
        self.progress = ttk.Progressbar(footer, style="Accent.Horizontal.TProgressbar",
                                        mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(footer, textvariable=self.var_status, style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

    def _build_controls(self, parent):
        row = 0

        def section(text):
            nonlocal row
            ttk.Label(parent, text=text, style="Muted.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(10, 2))
            row += 1

        # Pattern
        section("BASE PATTERN")
        cb = ttk.Combobox(parent, textvariable=self.var_pattern, values=self._pattern_opts,
                          state="readonly", width=24)
        cb.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1

        # Distortion
        section("DISTORTION")
        cb = ttk.Combobox(parent, textvariable=self.var_distort, values=self._distort_opts,
                          state="readonly", width=24)
        cb.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1

        # Size
        section("IMAGE SIZE (px)")
        size_cb = ttk.Combobox(parent, textvariable=self.var_size,
                               values=["512", "1024", "2048", "4096", "Custom…"],
                               state="readonly", width=24)
        size_cb.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1
        size_cb.bind("<<ComboboxSelected>>", lambda e: self._sync_custom_size())
        self.custom_entry = ttk.Entry(parent, textvariable=self.var_custom_size, width=24)
        self.custom_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0)); row += 1

        # Count
        section("NUMBER OF IMAGES")
        ttk.Spinbox(parent, from_=1, to=10000, textvariable=self.var_count, width=22).grid(
            row=row, column=0, columnspan=2, sticky="ew"); row += 1

        # Zoom — pattern and distortion are now independent
        section("PATTERN ZOOM")
        pz_row = ttk.Frame(parent, style="Panel.TFrame")
        pz_row.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1
        ttk.Scale(pz_row, from_=ZOOM_MIN, to=ZOOM_MAX, variable=self.var_pzoom,
                  orient="horizontal", command=self._on_pzoom_change).pack(
                      side="left", fill="x", expand=True)
        ttk.Label(pz_row, textvariable=self.var_pzoom_label, style="Panel.TLabel",
                  width=6).pack(side="left", padx=(8, 0))

        section("DISTORTION ZOOM")
        dz_row = ttk.Frame(parent, style="Panel.TFrame")
        dz_row.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1
        ttk.Scale(dz_row, from_=ZOOM_MIN, to=ZOOM_MAX, variable=self.var_dzoom,
                  orient="horizontal", command=self._on_dzoom_change).pack(
                      side="left", fill="x", expand=True)
        ttk.Label(dz_row, textvariable=self.var_dzoom_label, style="Panel.TLabel",
                  width=6).pack(side="left", padx=(8, 0))

        # Output
        section("OUTPUT FOLDER")
        out_row = ttk.Frame(parent, style="Panel.TFrame")
        out_row.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1
        ttk.Entry(out_row, textvariable=self.var_output).pack(side="left", fill="x", expand=True)
        ttk.Button(out_row, text="Browse", command=self._browse_output, width=8).pack(
            side="left", padx=(6, 0))

        # Action buttons
        parent.grid_rowconfigure(row, minsize=14)
        row += 1
        btns = ttk.Frame(parent, style="Panel.TFrame")
        btns.grid(row=row, column=0, columnspan=2, sticky="ew"); row += 1
        self.btn_preview = ttk.Button(btns, text="Preview", command=self.on_preview)
        self.btn_preview.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_generate = ttk.Button(btns, text="Generate", style="Accent.TButton",
                                       command=self.on_generate)
        self.btn_generate.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.btn_cancel = ttk.Button(parent, text="Cancel", command=self.on_cancel, state="disabled")
        self.btn_cancel.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0)); row += 1

        self._sync_custom_size()
        self._on_pzoom_change()
        self._on_dzoom_change()

    def _build_preview(self, parent):
        wrap = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="PREVIEW", style="Muted.TLabel").pack(anchor="w")

        self.preview_canvas = tk.Canvas(wrap, width=PREVIEW_BOX, height=PREVIEW_BOX,
                                        bg=COLORS["field"], highlightthickness=0)
        self.preview_canvas.pack(pady=(8, 8))
        self._preview_placeholder()

        self.var_preview_info = tk.StringVar(value="Press Preview to render a sample.")
        ttk.Label(wrap, textvariable=self.var_preview_info, style="Muted.TLabel").pack(anchor="w")

        self.btn_open = ttk.Button(wrap, text="Open output folder",
                                   command=lambda: open_in_file_manager(self.var_output.get()))
        self.btn_open.pack(anchor="w", pady=(10, 0))

    def _preview_placeholder(self):
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            PREVIEW_BOX // 2, PREVIEW_BOX // 2, text="no preview yet",
            fill=COLORS["muted"], font=("Helvetica", 12))

    # ----- small UI helpers ---------------------------------------------- #
    def _on_pzoom_change(self, *_):
        self.var_pzoom_label.set(f"{self.var_pzoom.get():.1f}x")

    def _on_dzoom_change(self, *_):
        self.var_dzoom_label.set(f"{self.var_dzoom.get():.1f}x")

    def _sync_custom_size(self):
        is_custom = self.var_size.get() == "Custom…"
        self.custom_entry.configure(state="normal" if is_custom else "disabled")

    def _browse_output(self):
        d = filedialog.askdirectory(initialdir=self.var_output.get() or str(Path.cwd()))
        if d:
            self.var_output.set(d)

    def _resolve_size(self):
        if self.var_size.get() == "Custom…":
            raw = self.var_custom_size.get().strip()
        else:
            raw = self.var_size.get()
        try:
            size = int(raw)
        except ValueError:
            raise ValueError(f"'{raw}' is not a valid pixel size.")
        if size < 16:
            raise ValueError("Size must be at least 16 px.")
        if size > 8192:
            raise ValueError("Size above 8192 px is not allowed (memory limits).")
        return size

    def _selected_pattern(self):
        v = self.var_pattern.get()
        return None if v == "All (random)" else v

    def _selected_distort(self):
        v = self.var_distort.get()
        return None if v == "All (random)" else v

    def _zooms(self):
        return round(self.var_pzoom.get(), 1), round(self.var_dzoom.get(), 1)

    # ----- actions -------------------------------------------------------- #
    def on_preview(self):
        try:
            size = min(self._resolve_size(), PREVIEW_MAX_RENDER)
        except ValueError as e:
            messagebox.showwarning("Invalid size", str(e))
            return
        p_zoom, d_zoom = self._zooms()
        self._set_running(True)
        self.var_status.set("Rendering preview…")
        self.cancel_event.clear()
        self.worker = threading.Thread(
            target=self._worker, daemon=True,
            kwargs=dict(count=1, size=size, save=False, out_dir=None,
                        p_name=self._selected_pattern(), d_name=self._selected_distort(),
                        p_zoom=p_zoom, d_zoom=d_zoom))
        self.worker.start()

    def on_generate(self):
        try:
            size = self._resolve_size()
        except ValueError as e:
            messagebox.showwarning("Invalid size", str(e))
            return
        count = max(1, int(self.var_count.get()))
        out_dir = self.var_output.get().strip()
        if not out_dir:
            messagebox.showwarning("No output folder", "Please choose an output folder.")
            return

        if size >= 4096:
            if not messagebox.askyesno(
                "Large image warning",
                f"Rendering at {size}×{size} can be slow and memory-hungry "
                "(the 'voronoi' pattern in particular). Continue?"):
                return

        p_zoom, d_zoom = self._zooms()
        self._set_running(True)
        self.progress.configure(maximum=count, value=0)
        self.var_status.set("Starting…")
        self.cancel_event.clear()
        self.worker = threading.Thread(
            target=self._worker, daemon=True,
            kwargs=dict(count=count, size=size, save=True, out_dir=out_dir,
                        p_name=self._selected_pattern(), d_name=self._selected_distort(),
                        p_zoom=p_zoom, d_zoom=d_zoom))
        self.worker.start()

    def on_cancel(self):
        self.cancel_event.set()
        self.var_status.set("Cancelling…")

    # ----- worker thread (no Tk calls here) ------------------------------ #
    def _worker(self, count, size, save, out_dir, p_name, d_name, p_zoom, d_zoom):
        try:
            if save:
                out_path = Path(out_dir)
                out_path.mkdir(parents=True, exist_ok=True)

            for i in range(1, count + 1):
                if self.cancel_event.is_set():
                    self.queue.put(("status", "Cancelled."))
                    break

                arr, pname, dname, seed = render_one(size, p_name, d_name, p_zoom, d_zoom)
                img = Image.fromarray(arr, mode="L")

                if save:
                    fname = out_path / f"bg_{i:03d}_{pname}_{dname}_seed{seed}.png"
                    img.save(fname)
                    self.queue.put(("saved", str(fname)))
                    self.queue.put(("progress", i, count))

                # send a downscaled thumbnail for the preview pane
                thumb = img.copy()
                thumb.thumbnail((PREVIEW_BOX, PREVIEW_BOX), Image.LANCZOS)
                self.queue.put(("thumb", thumb, f"{pname} · {dname} · seed {seed}"))

            else:  # loop completed without break
                if save:
                    self.queue.put(("status", f"Done — {count} image(s) saved."))
                else:
                    self.queue.put(("status", "Preview ready."))
        except MemoryError:
            self.queue.put(("error", "Ran out of memory — try a smaller size or a different pattern."))
        except Exception as exc:  # surface anything else cleanly
            self.queue.put(("error", f"{type(exc).__name__}: {exc}"))
        finally:
            self.queue.put(("finished",))

    # ----- queue polling on the main thread ------------------------------ #
    def _poll_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "status":
                    self.var_status.set(msg[1])
                elif kind == "progress":
                    i, total = msg[1], msg[2]
                    self.progress.configure(value=i)
                    self.var_status.set(f"Generating… {i}/{total}")
                elif kind == "saved":
                    pass  # filename already reflected via progress/status
                elif kind == "thumb":
                    self._show_thumb(msg[1], msg[2])
                elif kind == "error":
                    self.var_status.set("Error.")
                    messagebox.showerror("Generation error", msg[1])
                elif kind == "finished":
                    self._set_running(False)
        except Empty:
            pass
        self.after(80, self._poll_queue)

    def _show_thumb(self, pil_img, info):
        self.preview_photo = ImageTk.PhotoImage(pil_img)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(PREVIEW_BOX // 2, PREVIEW_BOX // 2,
                                         image=self.preview_photo)
        self.var_preview_info.set(info)

    # ----- running state -------------------------------------------------- #
    def _set_running(self, running):
        state = "disabled" if running else "normal"
        self.btn_generate.configure(state=state)
        self.btn_preview.configure(state=state)
        self.btn_cancel.configure(state="normal" if running else "disabled")
        if not running:
            self.progress.configure(value=0)

    # ----- settings + lifecycle ------------------------------------------ #
    def _apply_saved_settings(self):
        s = load_settings()
        if not s:
            return
        try:
            if s.get("pattern") in self._pattern_opts:
                self.var_pattern.set(s["pattern"])
            if s.get("distort") in self._distort_opts:
                self.var_distort.set(s["distort"])
            if "size" in s:
                self.var_size.set(s["size"])
            if "custom_size" in s:
                self.var_custom_size.set(s["custom_size"])
            if "count" in s:
                self.var_count.set(int(s["count"]))
            if "pzoom" in s:
                self.var_pzoom.set(float(s["pzoom"]))
            if "dzoom" in s:
                self.var_dzoom.set(float(s["dzoom"]))
            if s.get("output"):
                self.var_output.set(s["output"])
        except Exception:
            pass
        self._sync_custom_size()
        self._on_pzoom_change()
        self._on_dzoom_change()

    def _collect_settings(self):
        return {
            "pattern": self.var_pattern.get(),
            "distort": self.var_distort.get(),
            "size": self.var_size.get(),
            "custom_size": self.var_custom_size.get(),
            "count": int(self.var_count.get()),
            "pzoom": round(self.var_pzoom.get(), 1),
            "dzoom": round(self.var_dzoom.get(), 1),
            "output": self.var_output.get(),
        }

    def _on_close(self):
        self.cancel_event.set()
        save_settings(self._collect_settings())
        self.destroy()


def main():
    app = PsyGenApp()
    app.mainloop()


if __name__ == "__main__":
    main()
