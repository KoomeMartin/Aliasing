"""UI smoke test: drives the real App through Parts 2-4 + tone generator.
Run:  python tests/smoke_ui.py   (saves out/smoke_*.png and a window screenshot)
"""
import ctypes
import os
import sys
import tempfile
import time
import tkinter as tk
import tkinter.messagebox as mb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
SMOKE = os.path.join(ROOT, "out", "smoke")
os.makedirs(SMOKE, exist_ok=True)

from audio.wavio import read_wav
from ui.app import App


def pump(root, secs):
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.02)


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:  # noqa: BLE001
    pass

errors = []
mb.showerror = lambda t, m: errors.append(m)

root = tk.Tk()
app = App(root)
tmp = tempfile.mkdtemp()
p = lambda n: os.path.join(tmp, n)

# misc: tone generator
app.t_f.set("5000"); app.t_path.set(p("t5000.wav")); app.gen_tone()
app.t_folder.set(p("lab")); app.gen_lab_set()
assert len(os.listdir(p("lab"))) == 6

# Part 3: subsample (+ upsample)
app.s_in.set(p("t5000.wav")); app.s_out.set(p("t5000_sub2.wav")); app.s_M.set("2"); app.s_up.set(True)
app.do_subsample(); pump(root, 1)
x, fs, bits = read_wav(p("t5000_sub2.wav")); assert fs == 8000 and bits == 16
assert read_wav(p("t5000_sub2_up.wav"))[1] == 16000
app.spec3(); pump(root, 2)
assert len(app.windows) == 1 and len(app.windows[0].sgs) == 3
app.windows[0].fig.savefig(os.path.join(SMOKE, "smoke_spectrogram.png"))

# Part 2: single graph
app.sg_file.set(p("t5000.wav")); app.show_spectrographs([p("t5000.wav")]); pump(root, 1.5)
app.windows[-1].mode.set("block"); app.windows[-1].draw(); pump(root, 0.5)

# Part 4: filter, with and without simulate
app.f_in.set(p("t5000.wav")); app.f_out.set(p("t5000_lp.wav")); app.f_fc.set("4000"); app.f_N.set("1024")
app.do_filter(); pump(root, 1); assert os.path.isfile(p("t5000_lp.wav"))
app.f_sim.set(True); app.f_out.set(p("t5000_lp_sub2.wav")); app.s_M.set("2")
app.do_filter(); pump(root, 1)
assert read_wav(p("t5000_lp_sub2.wav"))[1] == 8000 and os.path.isfile(p("t5000_lp_sub2_up.wav"))

# validation errors become dialogs/log lines, not crashes
for fn, setup in ((app.do_filter, lambda: app.f_fc.set("99999")),
                  (app.do_subsample, lambda: app.s_in.set(p("missing.wav"))),
                  (app.toggle_record, lambda: app.rec_path.set(""))):
    setup(); app.guard(fn)(); pump(root, 0.5)
assert len(errors) == 3, errors

root.attributes('-topmost', True); root.lift(); root.focus_force(); pump(root, 1.0)
try:
    from PIL import ImageGrab
    x0, y0 = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab((x0, y0, x0 + root.winfo_width(), y0 + root.winfo_height())).save(
        os.path.join(SMOKE, "smoke_window.png"))
except Exception as e:                                  # noqa: BLE001
    print("screenshot skipped:", e)
print("UI smoke OK;", len(errors), "validation errors surfaced as expected")
root.destroy()
