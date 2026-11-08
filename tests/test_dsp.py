import os
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audio.wavio import read_wav, write_wav
from dsp.basis import (basis_matrix, forward_blocks, freq_index, inverse_blocks,
                       power)
from dsp.blockfilter import lowpass_blocks
from dsp.resample import subsample, upsample
from dsp.spectrum import spectrogram
from dsp.tonegen import LAB_TONES, tone, write_lab_set


def peak_hz(sg):
    return sg["freqs"][sg["db"].mean(axis=0).argmax()]


@pytest.mark.parametrize("N", [8, 64, 256, 1024])
def test_basis_orthonormal_and_fft_matches_matrix(N):
    U = basis_matrix(N)
    assert np.abs(U @ U.T - np.eye(N)).max() < 1e-10
    blocks = np.random.default_rng(0).standard_normal((5, N))
    X = forward_blocks(blocks)
    assert np.abs(X - blocks @ U.T).max() < 1e-9
    assert np.abs(inverse_blocks(X) - blocks).max() < 1e-9


def test_slide_u2_and_uN2():
    N = 64
    n = np.arange(N)
    U = basis_matrix(N)
    assert np.allclose(U[2], np.sqrt(2 / N) * np.cos(2 * np.pi * 2 * n / N))
    assert np.allclose(U[N - 2], np.sqrt(2 / N) * np.sin(2 * np.pi * 2 * n / N))


def test_odd_n_rejected():
    with pytest.raises(ValueError):
        forward_blocks(np.zeros((1, 7)))


def test_sine_peak_and_phase_independence():
    fs, N = 8000, 1024
    n = np.arange(fs * 2)
    p = []
    for ph in (0, np.pi / 2, 1.0):
        sg = spectrogram(np.sin(2 * np.pi * 1000 * n / fs + ph), fs, N)
        assert abs(peak_hz(sg) - 1000) <= fs / N
        assert sg["db"].max() == pytest.approx(0.0)
        p.append(power(forward_blocks(np.sin(2 * np.pi * 1000 * n[:N] / fs + ph)[None])).sum())
    assert np.allclose(p, p[0], rtol=1e-6)      # sine+cosine combined => same power


def test_floor_clipping():
    sg = spectrogram(np.sin(2 * np.pi * 1000 * np.arange(16000) / 8000), 8000, 256, -45)
    assert sg["db"].min() >= -45 and sg["db"].min() == pytest.approx(-45)


def test_wav_roundtrip(tmp_path):
    x = np.random.default_rng(1).uniform(-0.9, 0.9, 1000)
    p = str(tmp_path / "a.wav")
    write_wav(p, x, 16000, 16)
    y, fs, bits = read_wav(p)
    assert (fs, bits) == (16000, 16) and np.abs(x - y).max() <= 1 / 32768
    write_wav(p, x, 8000, 8)
    with wave.open(p) as w:
        assert w.getsampwidth() == 1
        raw = np.frombuffer(w.readframes(w.getnframes()), "u1")
    assert raw.min() >= 0 and abs(raw.mean() - 128) < 10    # unsigned, mid = 128
    y, fs, bits = read_wav(p)
    assert bits == 8 and np.abs(x - y).max() <= 1 / 128


def test_alias_5k_sub2():
    fs = 16000
    y = subsample(tone(5000, 5, fs), 2)
    sg = spectrogram(y, fs // 2, 1024)
    assert abs(peak_hz(sg) - 3000) <= (fs // 2) / 1024


def test_upsample_rate_and_length():
    y = np.sin(2 * np.pi * 500 * np.arange(4000) / 4000)
    u = upsample(y, 4)
    assert len(u) == 4 * len(y)
    sg = spectrogram(u, 16000, 1024)
    assert abs(peak_hz(sg) - 500) <= 16


def test_lowpass_blocks():
    rng = np.random.default_rng(2)
    fs, N = 16000, 1024
    x = rng.standard_normal(N * 30)          # whole blocks: no zero-pad edge effects
    y = lowpass_blocks(x, fs, N, 1000)
    assert len(y) == len(x)
    assert len(lowpass_blocks(x[:-123], fs, N, 1000)) == len(x) - 123   # length preserved
    sg = spectrogram(y, fs, N, -300)
    jc = int(1000 * N / fs)
    assert sg["db"][:, jc + 1:].max() < -250            # nothing above cutoff
    X, Y = forward_blocks(x[:N][None]), forward_blocks(y[:N][None])
    keep = freq_index(N) <= jc
    assert np.allclose(X[:, keep], Y[:, keep])           # kept sine & cosine intact


def test_filter_then_subsample_removes_alias():
    fs, N = 16000, 1024
    x = tone(5000, 2, fs)[: N * 31]                       # whole blocks
    e_plain = np.sum(subsample(x, 2) ** 2)                # alias at 3 kHz, full energy
    e_filt = np.sum(subsample(lowpass_blocks(x, fs, N, 3900), 2) ** 2)
    assert e_filt < 1e-9 * e_plain                        # 5 kHz removed before decimation


def test_tone_batch(tmp_path):
    paths = write_lab_set(str(tmp_path), write_wav)
    assert len(paths) == 6
    for f, p in zip(LAB_TONES, paths):
        x, fs, bits = read_wav(p)
        assert (fs, bits, len(x)) == (16000, 16, 80000)
        assert abs(peak_hz(spectrogram(x, fs, 1024)) - f) <= fs / 1024


def test_large_block_fast():
    import time
    x = np.random.default_rng(3).standard_normal(48000 * 10)
    t = time.time()
    spectrogram(x, 48000, 16384)
    lowpass_blocks(x, 48000, 16384, 4000)
    assert time.time() - t < 5
