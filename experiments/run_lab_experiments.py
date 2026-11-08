"""Regenerate the lab's evidence (PNGs + WAVs) into out/.

  python experiments/run_lab_experiments.py [music.wav]

Parts a-d need no input. Parts e-g need a ~10 s music clip (WAV, 8/16-bit).
Explanations are written by you; this only produces the figures/audio.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from audio.wavio import read_wav, write_wav
from dsp.blockfilter import lowpass_blocks
from dsp.resample import subsample
from dsp.spectrum import spectrogram
from dsp.tonegen import LAB_TONES, tone, write_lab_set
from ui.plots import plot_spectrogram

OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)


def save_spec(x, fs, title, fname, N=1024):
    fig = Figure(figsize=(9, 4), dpi=120)
    ax = fig.add_subplot(111)
    plot_spectrogram(fig, ax, spectrogram(x, fs, N), title)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname))
    print("wrote", fname)


def main():
    fs = 16000
    write_lab_set(os.path.join(OUT, "tones"), write_wav)                       # (a)
    print("wrote six tones to out/tones")
    save_spec(tone(2500, 5, fs), fs, "2500 Hz tone", "b_tone2500.png")         # (b)
    save_spec(tone(5000, 5, fs), fs, "5000 Hz tone", "c_tone5000.png")         # (c)
    sub = subsample(tone(5000, 5, fs), 2)                                      # (d)
    write_wav(os.path.join(OUT, "d_tone5000_sub2.wav"), sub, fs // 2, 16)
    save_spec(sub, fs // 2, "5000 Hz tone sub-sampled by 2 (no filter)", "d_tone5000_sub2.png")

    if len(sys.argv) > 1:
        x, mfs, bits = read_wav(sys.argv[1])
        save_spec(x, mfs, "music", "e_music.png", 2048)                        # (e)
        for M, fc in ((2, 4000), (4, 2000), (5, 1600)):
            y = subsample(x, M)                                                # (f)
            write_wav(os.path.join(OUT, f"f_music_sub{M}.wav"), y, mfs // M, bits)
            save_spec(y, mfs // M, f"music sub-sampled by {M} (no filter)", f"f_music_sub{M}.png", 2048)
            z = subsample(lowpass_blocks(x, mfs, 16384, fc), M)                # (g)
            write_wav(os.path.join(OUT, f"g_music_lp{fc}_sub{M}.wav"), z, mfs // M, bits)
            save_spec(z, mfs // M, f"music low-passed at {fc} Hz, then sub-sampled by {M}",
                      f"g_music_lp{fc}_sub{M}.png", 2048)
    else:
        print("no music file given: skipping parts e-g")


if __name__ == "__main__":
    main()
