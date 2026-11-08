import numpy as np
from scipy.signal import resample_poly


def subsample(x, M):
    """Keep every M-th sample. Deliberately NO anti-alias filtering."""
    if int(M) != M or M < 2:
        raise ValueError("M must be an integer >= 2")
    return np.asarray(x)[::int(M)].copy()


def upsample(y, M):
    """Zero-stuff by M + Kaiser polyphase low-pass (anti-imaging), gain M."""
    if int(M) != M or M < 2:
        raise ValueError("M must be an integer >= 2")
    return resample_poly(np.asarray(y, float), up=int(M), down=1,
                         window=("kaiser", 8.0))
