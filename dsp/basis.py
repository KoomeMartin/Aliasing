"""Real orthonormal Fourier basis (the lab's transform).

Row u_k of U (N even):
  k = 0            : 1/sqrt(N)
  k = 1..N/2-1     : sqrt(2/N) cos(2 pi k n / N)
  k = N/2          : cos(pi n)/sqrt(N)
  k = N/2+1..N-1   : sqrt(2/N) sin(2 pi (N-k) n / N)

`basis_matrix` is the reference; `forward_blocks` / `inverse_blocks` are the
FFT-based production implementation (same numbers, O(N log N)).
"""
from functools import lru_cache

import numpy as np


def _check_n(N):
    if N < 4 or N % 2:
        raise ValueError("block size N must be an even integer >= 4")


@lru_cache(maxsize=8)
def basis_matrix(N):
    _check_n(N)
    n = np.arange(N)
    U = np.empty((N, N))
    U[0] = 1 / np.sqrt(N)
    for k in range(1, N // 2):
        U[k] = np.sqrt(2 / N) * np.cos(2 * np.pi * k * n / N)
    U[N // 2] = np.cos(np.pi * n) / np.sqrt(N)
    for k in range(N // 2 + 1, N):
        U[k] = np.sqrt(2 / N) * np.sin(2 * np.pi * (N - k) * n / N)
    return U


def forward_blocks(blocks):
    """blocks: (B, N) -> coefficients X (B, N), via rfft."""
    blocks = np.atleast_2d(blocks)
    N = blocks.shape[1]
    _check_n(N)
    h = N // 2
    F = np.fft.rfft(blocks, axis=1)
    s = np.sqrt(2.0 / N)
    X = np.empty(blocks.shape)
    X[:, 0] = F[:, 0].real / np.sqrt(N)
    X[:, 1:h] = s * F[:, 1:h].real
    X[:, h] = F[:, h].real / np.sqrt(N)
    X[:, h + 1:] = -s * F[:, h - 1:0:-1].imag   # X[N-j] pairs with j
    return X


def inverse_blocks(X):
    """X (B, N) -> time blocks (B, N), via irfft."""
    X = np.atleast_2d(X)
    N = X.shape[1]
    _check_n(N)
    h = N // 2
    c = np.sqrt(N / 2.0)
    F = np.empty((X.shape[0], h + 1), dtype=complex)
    F[:, 0] = np.sqrt(N) * X[:, 0]
    F[:, h] = np.sqrt(N) * X[:, h]
    F[:, 1:h] = c * X[:, 1:h] - 1j * c * X[:, h + 1:][:, ::-1]
    return np.fft.irfft(F, n=N, axis=1)


def freq_index(N):
    """Frequency index j (0..N/2) represented by each coefficient k (0..N-1)."""
    k = np.arange(N)
    return np.where(k <= N // 2, k, N - k)


def freq_of_index(k, N, fs):
    """Frequency in Hz of coefficient k: (j/N)*fs."""
    return freq_index(N)[k] * fs / N


def power(X):
    """Power per frequency j=0..N/2 from coefficients (B, N) -> (B, N/2+1).
    Sine and cosine at the same frequency are combined; DC/Nyquist stand alone."""
    N = X.shape[1]
    h = N // 2
    P = np.empty((X.shape[0], h + 1))
    P[:, 0] = X[:, 0] ** 2
    P[:, h] = X[:, h] ** 2
    P[:, 1:h] = X[:, 1:h] ** 2 + X[:, h + 1:][:, ::-1] ** 2
    return P


def to_blocks(x, N):
    """Zero-pad x to a multiple of N and reshape to (B, N)."""
    x = np.asarray(x, dtype=float)
    pad = (-len(x)) % N
    if pad:
        x = np.concatenate([x, np.zeros(pad)])
    return x.reshape(-1, N)
