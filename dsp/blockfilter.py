"""Block-by-block low-pass in the orthonormal-transform domain."""
import numpy as np

from .basis import forward_blocks, freq_index, inverse_blocks, to_blocks


def cutoff_index(fc, N, fs):
    return int(np.floor(fc * N / fs))


def lowpass_blocks(x, fs, N, fc):
    if not (0 < fc <= fs / 2):
        raise ValueError("cutoff must satisfy 0 < fc <= fs/2")
    jc = cutoff_index(fc, N, fs)
    X = forward_blocks(to_blocks(x, N))
    X *= (freq_index(N) <= jc)          # zeroes cosine AND sine above cutoff
    return inverse_blocks(X).reshape(-1)[:len(x)]
