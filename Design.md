# Design — Lab 2 Audio Analysis App

Implements `Requirements_v2.md`. IDs like (R-2.4) trace back to requirements.

## 1. Architecture

Layered, so DSP is testable without the UI.

```
Lab 2/
├── main.py                 # entry point: creates tk root, App
├── requirements.txt        # numpy scipy matplotlib sounddevice
├── dsp/
│   ├── basis.py            # real orthonormal basis matrix, fwd/inv, freq maps
│   ├── spectrum.py         # block power, dB, noise floor, spectrogram array
│   ├── resample.py         # decimate (no filter), upsample (resample_poly)
│   ├── blockfilter.py      # block-wise low-pass in transform domain
│   └── tonegen.py          # pure tones + batch of the lab's six tones
├── experiments/
│   └── run_lab_experiments.py  # optional: scripted parts a–g, saves PNG/WAV to out/
├── audio/
│   ├── wavio.py            # read/write wav, 8-bit unsigned / 16-bit signed
│   └── device.py           # record (stream, arbitrary length) and playback
├── ui/
│   ├── app.py              # main window (Lab 2 + misc tabs), SpecWindow
│   └── plots.py            # matplotlib canvas helpers, blue→red colormap
└── tests/
    ├── test_basis.py
    ├── test_spectrum.py
    ├── test_resample.py
    ├── test_blockfilter.py
    └── test_wavio.py
```

Rule: `dsp/` and `audio/wavio.py` import no tkinter.

## 2. Data model

```python
@dataclass
class Signal:
    name: str
    samples: np.ndarray   # float64, mono, in [-1, 1)
    fs: int               # Hz
    bits: int             # 8 or 16 (format used when saving)
```

`AppState` holds a dict of `Signal`s: `original`, `subsampled`, `upsampled`, `filtered`, plus settings (N, noise floor, M, fc). Tabs read/write it and use a "source signal" combo box (R-6.2).

## 3. Audio I/O (R-1)

**Recording** (`device.py`)
- `sounddevice.InputStream(samplerate=fs, channels=1, dtype='int16', callback=...)`; callback appends chunks to a `queue.Queue`; Stop closes the stream and concatenates. This allows arbitrary length without preallocating.
- Always capture int16 from the device, and for 8-bit requests convert after capture (devices rarely provide native 8-bit).
- On `PortAudioError` for unsupported rate → error dialog (R-1.7).

**Sample conversion** (`wavio.py`)
- 16-bit: `int16 = clip(round(x*32768), -32768, 32767)`; load: `x = int16/32768`.
- 8-bit unsigned: `u8 = clip(round(x*128 + 128), 0, 255)`; load: `x = (u8-128)/128`. Silence = 128.
- Write with stdlib `wave` (`setnchannels(1)`, `setsampwidth(bits//8)`, `setframerate(fs)`, `writeframes(bytes)`). WAV stores 16-bit as little-endian signed and 8-bit as unsigned, matching the requirement automatically; use `astype('<i2')` for 16-bit.
- Reading: `wave.open`, `getsampwidth()` 1 → `uint8`, 2 → `<i2`; reject other widths / multichannel (or average channels, with a warning).

**Playback**: `sd.play(float32_samples, fs)`; Stop → `sd.stop()`. Play the *float* samples at the signal's own `fs` (so sub-sampled audio plays at fs/M and sounds lower/aliased).

## 4. Transform (R-2) — `dsp/basis.py`

### 4.1 Reference matrix

```python
def basis_matrix(N):
    assert N % 2 == 0
    n = np.arange(N)
    U = np.empty((N, N))
    U[0] = 1/np.sqrt(N)
    for k in range(1, N//2):
        U[k] = np.sqrt(2/N) * np.cos(2*np.pi*k*n/N)
    U[N//2] = np.cos(np.pi*n) / np.sqrt(N)
    for k in range(N//2+1, N):
        U[k] = np.sqrt(2/N) * np.sin(2*np.pi*(N-k)*n/N)
    return U
```

- `forward(block, U) = U @ block`, `inverse(X, U) = U.T @ X`.
- Cache matrices per N (`functools.lru_cache`). Vectorized across blocks: `X = blocks @ U.T` where `blocks` is shape (B, N).
- Memory: N² × 8 bytes → 1024: 8 MB, 4096: 128 MB, 8192: 512 MB. Hence the FFT path.

### 4.2 FFT-equivalent (fast path)

With `F = np.fft.rfft(block)`:
- `X[0] = Re F[0] / √N`
- `X[j] = √(2/N) · Re F[j]` (1 ≤ j ≤ N/2−1)
- `X[N/2] = Re F[N/2] / √N`
- `X[N−j] = −√(2/N) · Im F[j]` (1 ≤ j ≤ N/2−1), since `Σ x sin(θ) = −Im Σ x e^{−jθ}`.

Inverse: rebuild `F` from those and `irfft`. **The FFT path is the production implementation everywhere** (Lab 2.pdf 7a requires it; at N = 16 384 the matrix would be 2 GB). The matrix is used only in `test_basis.py` (N ≤ 1024) to assert the two agree (R-2.6). Batch form: `np.fft.rfft(blocks, axis=1)` handles all blocks in one call.

### 4.3 Index helpers

```python
def freq_of_index(k, N, fs):   # frequency in Hz that coefficient k represents
    j = k if k <= N//2 else N - k
    return j * fs / N
def pair_indices(N):           # j=1..N/2-1 -> (j, N-j)
```

## 5. Spectrogram (R-3) — `dsp/spectrum.py`

1. `pad = (-len(x)) % N`; `x = np.pad(x, (0, pad))`; reshape to `(B, N)`.
2. `X = transform_blocks(blocks)` (B × N).
3. Power array `P` (B × (N/2+1)):
   - `P[:,0] = X[:,0]²`
   - `P[:,j] = X[:,j]² + X[:,N-j]²` for j = 1…N/2−1
   - `P[:,N/2] = X[:,N/2]²`
4. `dB = 10*log10(max(P, eps) / P.max())`, `dB = np.maximum(dB, floor)` (R-3.4, 3.5).
5. Return `dB`, `times = (b*N + N/2)/fs` (block centres), `freqs = np.arange(N/2+1)*fs/N`, and `k = arange(N/2+1)`.

**Plotting** (`plots.py`): `imshow`/`pcolormesh` of `dB.T` with `origin='lower'`, extent `[0, duration, 0, fs/2]`, `vmin=floor`, `vmax=0`, `cmap=LinearSegmentedColormap.from_list('bluered', [(0,0,1),(1,0,0)])`, colour bar "dB rel. max". Colour bar linearly blends blue→red as required (the RGB midpoint is purple; that is what a straight fade gives).
Single-block view: line plot `dB[b]` vs `freqs`, with a `secondary_xaxis` mapping Hz → k.

Large spectrograms: `pcolormesh` on thousands of blocks is slow; use `imshow` (fast) with `interpolation='nearest'`.

## 6. Resampling (R-4) — `dsp/resample.py`

```python
def subsample(x, M):  return x[::M]               # no filtering, by design
def upsample(y, M):   return scipy.signal.resample_poly(y, up=M, down=1, window=('kaiser', 8.0))
```

- `resample_poly` implements zero-stuffing + polyphase FIR low-pass (cutoff π/M, gain M) — the textbook interpolator. The default filter length scales with `M`.
- Result: `Signal(fs=fs_sub*M)`. Length is `len(y)*M`, which may differ from the original length by < M samples; trim/pad to the original length when comparing.
- Saving subsampled signals: same 8/16-bit rule at rate `fs/M`. Non-standard rates (e.g. 2 kHz) are valid in WAV; some players may reject them, but the app's own player handles them.

## 7. Block low-pass filter (R-5) — `dsp/blockfilter.py`

```python
def lowpass_blocks(x, fs, N, fc):
    jc = int(np.floor(fc * N / fs))
    blocks = pad_and_reshape(x, N)
    X = transform_blocks(blocks)
    for j in range(jc+1, N//2+1):          # all frequencies above the cutoff
        X[:, j] = 0
        if j < N//2: X[:, N-j] = 0         # sine partner (none at Nyquist)
    y = inverse_blocks(X).reshape(-1)[:len(x)]
    return y
```

Vectorised version: build a boolean mask over the N coefficient indices once (`freq_index(k) <= jc`) and multiply `X * mask`. Both sine and cosine of every kept frequency (including DC) survive (R-5.3). Output length trimmed to input length (R-5.4).

## 7b. Tone generator and chains (R-5b, R-5c)

```python
def tone(f, dur, fs, amp=0.8):  return amp*np.sin(2*np.pi*f*np.arange(int(dur*fs))/fs)
LAB_TONES = [500, 1000, 2500, 3000, 5000, 7000]   # fs=16000, 16-bit, 5 s
```
- Tones are written through the same `wavio` 16-bit path. Frequencies land exactly on bins only if `f·N/fs` is an integer (e.g. N = 1024, fs = 16 k: 500 Hz = bin 32); others show slight spectral leakage—mention in the report if visible.
- Chains: every operation returns a new `Signal` stored in `AppState`, and every tab's source combo lists all stored signals, so "filter → subsample" is simply picking `filtered` as the Resample source. A "Filter + Subsample" button runs both stages for the presets (M=2/fc 4000, M=4/2000, M=5/1600; N = 16384).
- **Compare view**: spectrogram tab can show two signals stacked with one shared dB scale (vmin = floor, vmax = 0). Note each uses its *own* max for 0 dB (R-3.4); state this in the plot title.
- Frequency axis for subsampled signals goes to `fs/M / 2`; to compare with the original, use the up-sampled version (same fs).

## 8. UI design (R-6) — file-based layout

Modelled on the instructor-style reference screenshot: one window, `ttk.Notebook` with tabs **Lab 2** and **misc**, and a timestamped **Log** panel at the bottom. Every part works on WAV *files* chosen with Browse buttons (no hidden in-memory state), so each stage's output is a file that can be played, graphed or fed to the next part. Spectrographs open in their own window (matplotlib toolbar = Save PNG; spectrogram / block-spectrum modes with block slider). Stacked inputs share the same dB scale.

| Section | Controls | Behaviour |
|---|---|---|
| Part 1: Audio capture | rate (8k/16k/48k), bits (8/16), seconds (0 = until Stop), Save to, Play file, Start/Stop, Play, Stop, progress bar | records to the Save-to path as WAV; Play file auto-fills |
| Part 2: Spectrograph | WAV file, transform size N, dB floor, Graph | spectrograph window |
| Part 3: Subsampling | Input, Output, M, Start, "also up-sample by M" checkbox, Play file, Play, Spectrograph | output at fs/M (no filter); optional `<output>_up.wav` at original fs; Spectrograph shows input vs output (vs up) |
| Part 4: Block filtering | Input, Output, cutoff Hz, Block N (default 16384), Start, "simulate part 3 down/up sampling" checkbox, Play file, Play, Spectrograph | low-pass per block; if simulate is checked: filter, then sub-sample by Part 3's M, plus `_up.wav` |
| misc tab | tone generator (freq, seconds, rate, bits, Save to), lab-set generator (folder) | writes WAV files |

Code: everything lives in `ui/app.py` (`App`, `SpecWindow`); plotting in `ui/plots.py`.

**Threading**: record callback runs in PortAudio thread (only enqueue). Heavy DSP in `threading.Thread`; results pushed back via `root.after(...)` polling a `queue.Queue` — never touch tk widgets from worker threads. Matplotlib embedded via `FigureCanvasTkAgg`.

**Validation** per R-6.3 in each tab before launching work; errors via `messagebox.showerror`.

## 9. Testing plan (maps to R-7)

`pytest` on `dsp/` and `wavio`: 
- `test_basis`: orthonormality, `u_2` / `u_{N-2}` vs analytic cos/sin, perfect reconstruction, matrix vs FFT.
- `test_spectrum`: 1 kHz sine → peak at bin `1000*N/fs`; phase-shifted sine gives equal power; max dB = 0; floor clipping.
- `test_resample`: aliasing frequency of M = 4 decimation; upsample length/rate.
- `test_blockfilter`: noise → energy above `fc` ≈ 0; output length equals input; kept bins unchanged.
- `test_wavio`: round-trip 16-bit exact; 8-bit within 1 LSB; header sample width / signedness checks.
Manual: record, play back, view each spectrogram with a speech clip and a swept tone.

Extra tests: `test_tonegen` (six files, 5 s, peak bin); `test_alias` (5 kHz tone at 16 kHz, ÷2 → peak at 3 kHz); filter-then-subsample on a 1 kHz + 7 kHz mix leaves no alias.

## 9b. Deliverable workflow (report PDF)

The app produces evidence; the student writes the report. Steps: toolbar "Save figure" → PNG per experiment (parts b–g), WAVs saved alongside, then assemble a single PDF in lab order (a–g), each image preceded by "below is the graph that shows …" and the requested explanations. `experiments/run_lab_experiments.py` (optional) regenerates every PNG/WAV in one run for reproducibility; it does not write the explanations.

## 10. Build order

1. `dsp/basis.py` + tests (the foundation, and it validates the slide's definition).
2. `audio/wavio.py` + tests.
3. `dsp/spectrum.py` + plot helper; script-only demo on a synthetic chirp.
4. `dsp/resample.py`, `dsp/blockfilter.py`, `dsp/tonegen.py` + tests.
5. `audio/device.py` (record/play).
6. UI tabs, wired in order: Record → Spectrogram → Resample → Filter.
7. Run acceptance table T-1…T-8; polish.

## 11. Risks and notes

- **8 kHz capture** may be refused by Windows (WASAPI shared mode only supports the mixer rate). Mitigation: try `WasapiSettings(auto_convert=True)` in sounddevice, or use the MME host API which resamples. Don't silently substitute a different rate (R-1.7).
- **Block-edge discontinuities** in filtered output are expected (no overlap-add); document in UI help text.
- **N odd / N too small** rejected; N must be even for the Nyquist basis vector.
- **Subsample aliasing is intentional**: show a note in UI so it is not mistaken for a bug.
- **Slide sign convention**: the sine rows use `sin(2π(N−k)n/N)` (positive sine). That is the negative of the DFT's imaginary part, which only matters if comparing raw coefficients to `np.fft`; power is unaffected. §4.2 accounts for this.
