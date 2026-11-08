"""Lab 2 front-end (file-based layout).

Tab "Lab 2": Part 1 capture, Part 2 spectrograph, Part 3 subsampling,
Part 4 block-by-block filtering, plus a log. Tab "misc": tone generator.
Spectrographs open in their own window (with matplotlib toolbar = Save PNG).
"""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from audio import device, wavio
from dsp.blockfilter import lowpass_blocks
from dsp.resample import subsample, upsample
from dsp.spectrum import spectrogram
from dsp.tonegen import LAB_TONES, tone, write_lab_set
from ui.plots import plot_block_spectrum, plot_spectrogram

RATES = [8000, 16000, 48000]
BLOCKS = [256, 512, 1024, 2048, 4096, 8192, 16384]


def suffix_path(path, tag):
    base, ext = os.path.splitext(path)
    return f"{base}{tag}{ext or '.wav'}"


class SpecWindow(tk.Toplevel):
    """One or more spectrographs stacked, with a block-spectrum mode."""

    def __init__(self, master, sgs):
        super().__init__(master)
        self.title("Spectrograph - " + ", ".join(n for n, _ in sgs))
        self.geometry("900x620")
        self.sgs = sgs
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")
        self.mode = tk.StringVar(value="spectrogram")
        for t, v in (("Spectrogram", "spectrogram"), ("Block spectrum (dB vs Hz)", "block")):
            ttk.Radiobutton(bar, text=t, value=v, variable=self.mode, command=self.draw).pack(side="left")
        self.block = 0
        ttk.Label(bar, text="  block:").pack(side="left")
        n_blocks = len(sgs[0][1]["db"])
        self.slider = ttk.Scale(bar, from_=0, to=max(n_blocks - 1, 0), command=self._slide)
        self.slider.pack(side="left", fill="x", expand=True, padx=6)
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        NavigationToolbar2Tk(self.canvas, self).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.draw()

    def _slide(self, v):
        self.block = int(float(v))
        if self.mode.get() == "block":
            self.draw()

    def draw(self):
        self.fig.clear()
        n = len(self.sgs)
        for i, (name, sg) in enumerate(self.sgs):
            ax = self.fig.add_subplot(n, 1, i + 1)
            if self.mode.get() == "spectrogram":
                plot_spectrogram(self.fig, ax, sg, name)
            else:
                plot_block_spectrum(ax, sg, min(self.block, len(sg["db"]) - 1), name)
        self.fig.tight_layout()
        self.canvas.draw_idle()


class App:
    def __init__(self, root):
        self.root = root
        root.title("Lab 2: Capture, Spectrograph, Subsampling, Filtering")
        root.geometry("840x870")
        self._jobs = queue.Queue()
        self.recorder = None
        self.windows = []

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=4, pady=4)
        main = ttk.Frame(nb, padding=6)
        misc = ttk.Frame(nb, padding=6)
        nb.add(main, text="Lab 2")
        nb.add(misc, text="misc")

        self.build_part1(main)
        self.build_part2(main)
        self.build_part3(main)
        self.build_part4(main)
        self.build_misc(misc)

        logf = ttk.LabelFrame(root, text="Log", padding=4)
        logf.pack(fill="both", padx=6, pady=(0, 6))
        self.logbox = tk.Text(logf, height=7, state="disabled", font=("Consolas", 9))
        sb = ttk.Scrollbar(logf, command=self.logbox.yview)
        self.logbox.config(yscrollcommand=sb.set)
        self.logbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.log("Ready.")
        self.root.after(100, self._poll)

    # ---------------------------------------------------------- helpers
    def log(self, msg):
        self.logbox.config(state="normal")
        self.logbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.logbox.see("end")
        self.logbox.config(state="disabled")

    def error(self, msg):
        self.log("ERROR: " + msg)
        messagebox.showerror("Error", msg)

    def guard(self, fn):
        def wrapped(*a):
            try:
                fn(*a)
            except Exception as e:                      # noqa: BLE001
                self.error(str(e))
        return wrapped

    def run_bg(self, label, work, done):
        """Run work() on a thread; done(result) runs on the Tk thread."""
        self.log(label + " ...")
        def target():
            try:
                self._jobs.put((done, work(), None))
            except Exception as e:                      # noqa: BLE001
                self._jobs.put((done, None, e))
        threading.Thread(target=target, daemon=True).start()

    def _poll(self):
        while not self._jobs.empty():
            done, res, err = self._jobs.get()
            if err:
                self.error(str(err))
            else:
                try:
                    done(res)
                except Exception as e:                  # noqa: BLE001
                    self.error(str(e))
        self.root.after(100, self._poll)

    def file_row(self, parent, label, var, save=False, width=11):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, width=width).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=2)
        def browse():
            kw = dict(filetypes=[("WAV", "*.wav")])
            p = (filedialog.asksaveasfilename(defaultextension=".wav", **kw) if save
                 else filedialog.askopenfilename(**kw))
            if p:
                var.set(p)
        ttk.Button(row, text="Browse...", command=browse).pack(side="left")
        return row

    @staticmethod
    def num(var, kind, name, lo=None, hi=None):
        try:
            v = kind(str(var.get()).strip())
        except ValueError:
            raise ValueError(f"{name} must be a valid {kind.__name__}.") from None
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise ValueError(f"{name} must be between {lo} and {hi}.")
        return v

    @staticmethod
    def need_file(var, name):
        p = var.get().strip()
        if not p:
            raise ValueError(f"{name}: choose a file first.")
        if not os.path.isfile(p):
            raise ValueError(f"{name}: file not found:\n{p}")
        return p

    @staticmethod
    def need_out(var, name):
        p = var.get().strip()
        if not p:
            raise ValueError(f"{name}: choose where to save the file.")
        return p

    def block_size(self, var, name="Transform size N"):
        N = self.num(var, int, name, 4)
        if N % 2:
            raise ValueError(f"{name} must be even.")
        return N

    # ------------------------------------------------------ Part 1
    def build_part1(self, parent):
        f = ttk.LabelFrame(parent, text="Part 1: Audio capture", padding=6)
        f.pack(fill="x", pady=3)
        r = ttk.Frame(f)
        r.pack(fill="x")
        self.rate, self.bits, self.secs = tk.StringVar(value="16000"), tk.StringVar(value="16"), tk.StringVar(value="5")
        ttk.Label(r, text="Sample rate (Hz):").pack(side="left")
        ttk.Combobox(r, textvariable=self.rate, values=RATES, width=7, state="readonly").pack(side="left", padx=3)
        ttk.Label(r, text="  Bits per sample:").pack(side="left")
        ttk.Combobox(r, textvariable=self.bits, values=[8, 16], width=4, state="readonly").pack(side="left", padx=3)
        ttk.Label(r, text="  Seconds:").pack(side="left")
        ttk.Entry(r, textvariable=self.secs, width=7).pack(side="left", padx=3)
        ttk.Label(r, text="(0 = until Stop)", foreground="gray").pack(side="left")
        self.rec_path, self.play1 = tk.StringVar(), tk.StringVar()
        self.file_row(f, "Save to:", self.rec_path, save=True)
        self.file_row(f, "Play file:", self.play1)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=3)
        self.rec_btn = ttk.Button(b, text="Start", command=self.guard(self.toggle_record))
        self.rec_btn.pack(side="left")
        ttk.Button(b, text="Play", command=self.guard(lambda: self.play_file(self.play1))).pack(side="left", padx=4)
        ttk.Button(b, text="Stop", command=self.stop_audio).pack(side="left")
        self.prog = ttk.Progressbar(b, maximum=1.0)
        self.prog.pack(side="left", fill="x", expand=True, padx=6)

    def toggle_record(self):
        if self.recorder is not None:
            return self.finish_record()
        path = self.need_out(self.rec_path, "Save to")
        secs = self.num(self.secs, float, "Seconds", 0)
        rec = device.Recorder(int(self.rate.get()))
        rec.start()                                     # PortAudioError -> shown, no silent fallback
        self.recorder, self.rec_limit, self.rec_dest = rec, secs, path
        self.rec_btn.config(text="Stop")
        self.log(f"Recording at {rec.fs} Hz, {self.bits.get()}-bit"
                 + (f" for {secs:g} s" if secs else " until Stop") + " ...")
        self._tick_record()

    def _tick_record(self):
        if self.recorder is None:
            return
        el = self.recorder.elapsed()
        if self.rec_limit:
            self.prog["value"] = min(el / self.rec_limit, 1.0)
            if el >= self.rec_limit:
                return self.guard(self.finish_record)()
        else:
            self.prog["value"] = (el % 5) / 5
        self.root.after(100, self._tick_record)

    def finish_record(self):
        rec, self.recorder = self.recorder, None
        self.rec_btn.config(text="Start")
        x = rec.stop()
        bits = int(self.bits.get())
        wavio.write_wav(self.rec_dest, x, rec.fs, bits)
        self.play1.set(self.rec_dest)
        self.prog["value"] = 0
        self.log(f"Saved {len(x)} samples ({len(x) / rec.fs:.2f} s, {rec.fs} Hz, {bits}-bit): {self.rec_dest}")

    def play_file(self, var):
        p = self.need_file(var, "Play file")
        x, fs, bits = wavio.read_wav(p)
        device.play(x, fs)
        self.log(f"Playing {os.path.basename(p)} ({fs} Hz, {len(x) / fs:.2f} s)")
        self._play_t0, self._play_dur = time.time(), len(x) / fs
        self._tick_play()

    def _tick_play(self):
        el = time.time() - self._play_t0
        if el < self._play_dur and self.recorder is None:
            self.prog["value"] = el / self._play_dur
            self.root.after(100, self._tick_play)
        elif self.recorder is None:
            self.prog["value"] = 0

    def stop_audio(self):
        device.stop()
        self._play_dur = 0
        self.log("Stopped.")

    # ------------------------------------------------------ Part 2
    def build_part2(self, parent):
        f = ttk.LabelFrame(parent, text="Part 2: Spectrograph", padding=6)
        f.pack(fill="x", pady=3)
        self.sg_file, self.N, self.floor = tk.StringVar(), tk.StringVar(value="512"), tk.StringVar(value="-45")
        self.file_row(f, "WAV file:", self.sg_file)
        r = ttk.Frame(f)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Transform size N:").pack(side="left")
        ttk.Combobox(r, textvariable=self.N, values=BLOCKS, width=7).pack(side="left", padx=3)
        ttk.Label(r, text="  dB floor:").pack(side="left")
        ttk.Entry(r, textvariable=self.floor, width=6).pack(side="left", padx=3)
        ttk.Button(r, text="Graph", command=self.guard(
            lambda: self.show_spectrographs([self.need_file(self.sg_file, "WAV file")]))).pack(side="left", padx=8)

    def show_spectrographs(self, paths, N=None):
        N = N or self.block_size(self.N)
        floor = self.num(self.floor, float, "dB floor", None, -0.001)
        def work():
            out = []
            for p in paths:
                x, fs, _ = wavio.read_wav(p)
                out.append((os.path.basename(p), spectrogram(x, fs, N, floor)))
            return out
        def done(sgs):
            self.windows.append(SpecWindow(self.root, sgs))
            self.log("Spectrograph: " + ", ".join(n for n, _ in sgs) + f" (N={N}, floor={floor:g} dB)")
        self.run_bg("Computing spectrograph", work, done)

    # ------------------------------------------------------ Part 3
    def build_part3(self, parent):
        f = ttk.LabelFrame(parent, text="Part 3: Subsampling", padding=6)
        f.pack(fill="x", pady=3)
        self.s_in, self.s_out, self.s_M, self.play3 = (tk.StringVar() for _ in range(4))
        self.s_M.set("4")
        self.s_up = tk.BooleanVar(value=False)
        self.file_row(f, "Input file:", self.s_in)
        self.file_row(f, "Output file:", self.s_out, save=True)
        r = ttk.Frame(f)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Subsample factor M:").pack(side="left")
        ttk.Entry(r, textvariable=self.s_M, width=5).pack(side="left", padx=3)
        ttk.Button(r, text="Start", command=self.guard(self.do_subsample)).pack(side="left", padx=6)
        ttk.Checkbutton(r, text="also up-sample by M (<output>_up.wav)", variable=self.s_up).pack(side="left")
        self.file_row(f, "Play file:", self.play3)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=2)
        ttk.Button(b, text="Play", command=self.guard(lambda: self.play_file(self.play3))).pack(side="left")
        ttk.Button(b, text="Spectrograph", command=self.guard(self.spec3)).pack(side="left", padx=4)
        ttk.Label(b, text="(input vs output; uses N / floor from Part 2)", foreground="gray").pack(side="left")

    def do_subsample(self):
        src = self.need_file(self.s_in, "Input file")
        dst = self.need_out(self.s_out, "Output file")
        M = self.num(self.s_M, int, "Subsample factor M", 2)
        up = self.s_up.get()
        def work():
            x, fs, bits = wavio.read_wav(src)
            y = subsample(x, M)                         # NO anti-alias filter, by design
            if len(y) < 8:
                raise ValueError("M is too large: fewer than 8 samples would remain.")
            fs_out = int(round(fs / M))
            wavio.write_wav(dst, y, fs_out, bits)
            up_path = None
            if up:
                up_path = suffix_path(dst, "_up")
                wavio.write_wav(up_path, upsample(y, M), fs_out * M, bits)
            return fs, fs_out, len(y), up_path
        def done(res):
            fs, fs_out, n, up_path = res
            self.play3.set(dst)
            self.log(f"Subsampled by {M} (no filter): {fs} -> {fs_out} Hz, {n} samples: {dst}")
            if up_path:
                self.log(f"Up-sampled by {M} back to {fs_out * M} Hz: {up_path}")
        self.run_bg("Subsampling", work, done)

    def spec3(self):
        paths = [self.need_file(self.s_in, "Input file")]
        out = self.s_out.get().strip()
        if os.path.isfile(out):
            paths.append(out)
            if os.path.isfile(suffix_path(out, "_up")) and self.s_up.get():
                paths.append(suffix_path(out, "_up"))
        self.show_spectrographs(paths)

    # ------------------------------------------------------ Part 4
    def build_part4(self, parent):
        f = ttk.LabelFrame(parent, text="Part 4: Block-by-block filtering", padding=6)
        f.pack(fill="x", pady=3)
        self.f_in, self.f_out, self.play4 = (tk.StringVar() for _ in range(3))
        self.f_fc, self.f_N = tk.StringVar(value="1000"), tk.StringVar(value="16384")
        self.f_sim = tk.BooleanVar(value=False)
        self.file_row(f, "Input file:", self.f_in)
        self.file_row(f, "Output file:", self.f_out, save=True)
        r = ttk.Frame(f)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text="Upper cutoff frequency (Hz):").pack(side="left")
        ttk.Entry(r, textvariable=self.f_fc, width=7).pack(side="left", padx=3)
        ttk.Label(r, text="Block N:").pack(side="left")
        ttk.Combobox(r, textvariable=self.f_N, values=BLOCKS, width=6).pack(side="left", padx=3)
        ttk.Button(r, text="Start", command=self.guard(self.do_filter)).pack(side="left", padx=6)
        ttk.Checkbutton(r, text="simulate part 3 down/up sampling", variable=self.f_sim).pack(side="left")
        self.file_row(f, "Play file:", self.play4)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=2)
        ttk.Button(b, text="Play", command=self.guard(lambda: self.play_file(self.play4))).pack(side="left")
        ttk.Button(b, text="Spectrograph", command=self.guard(self.spec4)).pack(side="left", padx=4)
        ttk.Label(b, text="(simulate: filter, then sub-sample by Part 3's M [+ up-sample])",
                  foreground="gray").pack(side="left")

    def do_filter(self):
        src = self.need_file(self.f_in, "Input file")
        dst = self.need_out(self.f_out, "Output file")
        fc = self.num(self.f_fc, float, "Cutoff", 0)
        N = self.block_size(self.f_N, "Block N")
        sim = self.f_sim.get()
        M = self.num(self.s_M, int, "Subsample factor M (Part 3)", 2) if sim else None
        def work():
            x, fs, bits = wavio.read_wav(src)
            if not 0 < fc <= fs / 2:
                raise ValueError(f"Cutoff must be in (0, {fs / 2:g}] Hz for a {fs} Hz file.")
            y = lowpass_blocks(x, fs, N, fc)
            if not sim:
                wavio.write_wav(dst, y, fs, bits)
                return fs, None
            z = subsample(y, M)
            fs_out = int(round(fs / M))
            wavio.write_wav(dst, z, fs_out, bits)
            up_path = suffix_path(dst, "_up")
            wavio.write_wav(up_path, upsample(z, M), fs_out * M, bits)
            return fs, (M, fs_out, up_path)
        def done(res):
            fs, extra = res
            self.play4.set(dst)
            self.log(f"Low-passed at {fc:g} Hz, block size {N}: {dst}")
            if extra:
                M, fs_out, up_path = extra
                self.log(f"  then sub-sampled by {M} ({fs} -> {fs_out} Hz); up-sampled copy: {up_path}")
        self.run_bg("Filtering", work, done)

    def spec4(self):
        paths = [self.need_file(self.f_in, "Input file")]
        out = self.f_out.get().strip()
        if os.path.isfile(out):
            paths.append(out)
            if self.f_sim.get() and os.path.isfile(suffix_path(out, "_up")):
                paths.append(suffix_path(out, "_up"))
        self.show_spectrographs(paths)

    # ------------------------------------------------------- misc tab
    def build_misc(self, parent):
        f = ttk.LabelFrame(parent, text="Tone generator", padding=8)
        f.pack(fill="x", pady=3)
        self.t_f, self.t_d = tk.StringVar(value="1000"), tk.StringVar(value="5")
        self.t_fs, self.t_bits = tk.StringVar(value="16000"), tk.StringVar(value="16")
        self.t_path, self.t_folder = tk.StringVar(), tk.StringVar()
        r = ttk.Frame(f)
        r.pack(fill="x")
        for lab, var, w in (("Frequency (Hz):", self.t_f, 7), ("  Seconds:", self.t_d, 5)):
            ttk.Label(r, text=lab).pack(side="left")
            ttk.Entry(r, textvariable=var, width=w).pack(side="left", padx=3)
        ttk.Label(r, text="  Rate:").pack(side="left")
        ttk.Combobox(r, textvariable=self.t_fs, values=RATES, width=7).pack(side="left", padx=3)
        ttk.Label(r, text="  Bits:").pack(side="left")
        ttk.Combobox(r, textvariable=self.t_bits, values=[8, 16], width=4, state="readonly").pack(side="left")
        self.file_row(f, "Save to:", self.t_path, save=True)
        ttk.Button(f, text="Generate tone", command=self.guard(self.gen_tone)).pack(anchor="w", pady=4)
        ttk.Separator(f).pack(fill="x", pady=6)
        self.file_row(f, "Folder:", self.t_folder)
        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Button(row, text=f"Generate lab set ({len(LAB_TONES)} tones: 16 kHz, 16-bit, 5 s)",
                   command=self.guard(self.gen_lab_set)).pack(side="left", pady=4)
        ttk.Label(f, text="Lab set: " + ", ".join(map(str, LAB_TONES)) + " Hz. For the folder, "
                  "pick any file inside it, or type the folder path.", foreground="gray",
                  wraplength=560, justify="left").pack(anchor="w")

    def gen_tone(self):
        fr = self.num(self.t_f, float, "Frequency", 1)
        d = self.num(self.t_d, float, "Seconds", 0.01)
        fs = self.num(self.t_fs, int, "Rate", 1000)
        if fr >= fs / 2:
            raise ValueError("Frequency must be below fs/2.")
        path = self.need_out(self.t_path, "Save to")
        bits = int(self.t_bits.get())
        wavio.write_wav(path, tone(fr, d, fs), fs, bits)
        self.log(f"Wrote {fr:g} Hz tone, {d:g} s, {fs} Hz, {bits}-bit: {path}")

    def gen_lab_set(self):
        p = self.t_folder.get().strip()
        if not p:
            raise ValueError("Folder: choose or type a folder path.")
        folder = p if os.path.isdir(p) or not os.path.splitext(p)[1] else os.path.dirname(p)
        paths = write_lab_set(folder, wavio.write_wav)
        self.log(f"Wrote {len(paths)} tone files to {folder}")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
