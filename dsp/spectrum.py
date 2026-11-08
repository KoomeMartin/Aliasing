"""Block-by-block power spectrogram (dB relative to max, noise-floor clipped)."""
import numpy as np

from .basis import forward_blocks, power, to_blocks

EPS = 1e-300


def spectrogram(x, fs, N=1024, floor_db=-45.0):
    """Returns dict: db (B, N/2+1), times (B,), freqs (N/2+1,), k (N/2+1,)."""
    if floor_db >= 0:
        raise ValueError("noise floor must be negative (dB)")
    blocks = to_blocks(x, N)
    P = power(forward_blocks(blocks))
    pmax = P.max()
    if pmax <= 0:                       # silence
        db = np.full(P.shape, floor_db)
    else:
        db = 10 * np.log10(np.maximum(P, EPS) / pmax)
        db = np.maximum(db, floor_db)
    k = np.arange(N // 2 + 1)
    return {
        "db": db,
        "times": (np.arange(len(blocks)) * N + N / 2) / fs,
        "freqs": k * fs / N,
        "k": k,
        "N": N,
        "fs": fs,
        "floor": floor_db,
    }
