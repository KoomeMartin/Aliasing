import os

import numpy as np

LAB_TONES = [500, 1000, 2500, 3000, 5000, 7000]


def tone(f, dur, fs, amp=0.8):
    n = np.arange(int(round(dur * fs)))
    return amp * np.sin(2 * np.pi * f * n / fs)


def write_lab_set(folder, wav_writer, fs=16000, dur=5.0, bits=16):
    os.makedirs(folder, exist_ok=True)
    paths = []
    for f in LAB_TONES:
        p = os.path.join(folder, f"tone_{f}Hz_{fs // 1000}k_{bits}bit.wav")
        wav_writer(p, tone(f, dur, fs), fs, bits)
        paths.append(p)
    return paths
