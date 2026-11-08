"""Matplotlib helpers: blue->red colormap, spectrogram and block-spectrum plots."""
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# Straight fade: pure blue at the noise floor -> pure red at 0 dB.
BLUE_RED = LinearSegmentedColormap.from_list("bluered", [(0, 0, 1), (1, 0, 0)])


def _maxpool(a, axis, target):
    """Reduce `a` along `axis` to <= target cells by taking the max of each group,
    so narrow peaks (one-bin tones) are never dropped by image down-sampling."""
    n = a.shape[axis]
    if n <= target:
        return a
    g = int(np.ceil(n / target))
    pad = (-n) % g
    if pad:
        widths = [(0, 0)] * a.ndim
        widths[axis] = (0, pad)
        a = np.pad(a, widths, mode="edge")
    shape = list(a.shape)
    shape[axis:axis + 1] = [a.shape[axis] // g, g]
    return a.reshape(shape).max(axis=axis + 1)


def plot_spectrogram(fig, ax, sg, title=""):
    db = sg["db"]
    fs = sg["fs"]
    duration = len(db) * sg["N"] / fs
    bbox = ax.get_window_extent()                       # axes size in pixels
    rows = max(int(bbox.height * 0.6), 32)              # 0.6: room for tight_layout/colorbar
    cols = max(int(bbox.width * 0.6), 32)
    db = _maxpool(_maxpool(db, 1, rows), 0, cols)       # (blocks, freq) -> display size
    # pcolormesh draws each cell as a quad covering >= 1 pixel, so thin lines survive
    t_edges = np.linspace(0, duration, db.shape[0] + 1)
    f_edges = np.linspace(0, fs / 2, db.shape[1] + 1)
    im = ax.pcolormesh(t_edges, f_edges, db.T, cmap=BLUE_RED, vmin=sg["floor"], vmax=0,
                       shading="flat", rasterized=True)
    ax.set_xlim(0, duration)
    ax.set_ylim(0, fs / 2)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title(f"{title}  (N={sg['N']}, fs={fs} Hz)" if title else f"N={sg['N']}, fs={fs} Hz")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("Power (dB rel. max)")
    return im


def plot_block_spectrum(ax, sg, b, title=""):
    N, fs = sg["N"], sg["fs"]
    ax.plot(sg["freqs"], sg["db"][b], color="tab:blue")
    ax.set_ylim(sg["floor"] - 2, 2)
    ax.set_xlim(0, fs / 2)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power (dB rel. max)")
    ax.set_title(f"{title} block {b} (t = {sg['times'][b]:.2f} s)")
    ax.grid(alpha=0.3)
    sec = ax.secondary_xaxis("top", functions=(lambda f: f * N / fs, lambda k: k * fs / N))
    sec.set_xlabel("Coefficient index k")
