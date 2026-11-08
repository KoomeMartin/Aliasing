# Requirements v2 — Audio Capture, Spectrogram, Sub/Up-sampling & Block Filtering

Complements `Requirements_v1_.md`. v1 stays the source of intent; v2 makes each item testable, fixes ambiguities, and adds the transform definition from the slide.
IDs (R-x.y) are referenced by `Design.md`.

## 0. Scope and platform

- R-0.1 Python 3.10+ desktop app with a **tkinter** UI.
- R-0.2 Libraries: `numpy`, `scipy` (resampling only), `matplotlib` (embedded in tkinter), `sounddevice` (capture/playback), stdlib `wave`.
- R-0.3 Long operations (record, transform, filter) must not freeze the UI (worker thread plus progress/status bar).

## 1. Capture, storage, playback  (v1 §i)

- R-1.1 Record from the default input device for an arbitrary, user-controlled duration (Start/Stop buttons; elapsed-time display).
- R-1.2 Selectable sampling rate: **8 000, 16 000, 48 000 Hz** (more may be added).
- R-1.3 Selectable bit depth: **8 and 16** bits per sample.
  - 16-bit: **signed** integer (int16, range −32768..32767).
  - 8-bit: **unsigned** byte (uint8, range 0..255, silence = 128). This is the WAV-standard convention.
- R-1.4 Save as `.wav` (PCM, mono; channel count fixed at 1 for this lab).
- R-1.5 Open an existing `.wav` (8- or 16-bit PCM) and play it back; stop-playback control.
- R-1.6 Internally, audio is held as `float64` in [−1, 1) for processing. Convert to/from the file format only at I/O boundaries (8-bit: `(x*127.5)+127.5` style mapping documented in Design; 16-bit: scale by 32768 with clipping).
- R-1.7 If the device rejects the requested rate, show a clear error (do not silently record at another rate).

## 2. Transform definition  (new — from the slide)

The transform is the **real orthonormal Fourier basis** of size N (N = block size, must be **even**). Row `u_k` of the matrix U is:

| k | u_k[n], n = 0..N−1 |
|---|---|
| 0 | `1/√N` |
| 1 … N/2−1 | `√(2/N) · cos(2π k n / N)` |
| N/2 | `(1/√N) · cos(π n)` |
| N/2+1 … N−1 | `√(2/N) · sin(2π (N−k) n / N)` |

- R-2.1 Forward: `X = U x`. Inverse: `x = Uᵀ X` (U is orthonormal, so `U Uᵀ = I`).
- R-2.2 **Frequency of each coefficient** (cycles/sample → Hz via sampling rate fs):
  - k = 0 → 0 Hz (DC); 
  - k = 1…N/2 → cosine at `f_k = k·fs/N`; 
  - k = N/2+1…N−1 → **sine** at `f = (N−k)·fs/N`.
  - Example (slide): `u_2` is a cosine at 2/N cycles/sample; `u_{N−2}` is a **sine at the same frequency**.
- R-2.3 The cosine/sine pair for frequency index `j` (1 ≤ j ≤ N/2−1) is `(X[j], X[N−j])`.
  DC (j = 0) and Nyquist (j = N/2) have **no sine partner**.
- R-2.4 **Power at frequency j**: `P[j] = X[j]² + X[N−j]²` for 1 ≤ j ≤ N/2−1; `P[0] = X[0]²`; `P[N/2] = X[N/2]²`.
  This gives N/2+1 power values for j = 0…N/2 (this satisfies v1 §iv "k = 0,1,…,N/2").
- R-2.5 Must have a self-test: `U Uᵀ ≈ I` (max error < 1e-10) and perfect reconstruction of a random block, run for every block size used.
- R-2.6 **The lab requires exactly this orthonormal transform, implemented efficiently with an FFT** (Lab 2.pdf, item 7a). The FFT path is the **production implementation** used by the spectrogram and filter. The explicit matrix is kept only as a test reference for small N; the two must agree within 1e-9.
- R-2.7 Must remain fast for block sizes up to and beyond 16 384 (the lab's filtering experiment uses 16,284 [sic]; see §9).

## 3. Spectrogram  (v1 §ii, §iv)

- R-3.1 Split the signal into consecutive **non-overlapping blocks** of N samples; N is user-selectable (default 1024; allowed: even integers, suggested presets 256…8192).
- R-3.2 Last partial block is zero-padded to N.
- R-3.3 Per block, compute `P[j]` per R-2.4 (both sine and cosine terms included).
- R-3.4 Convert to dB relative to the **global maximum power over the whole spectrogram**: `dB = 10·log10(P / P_max)` (so max = 0 dB). Guard against `P = 0` with a tiny epsilon.
- R-3.5 **Noise floor**: default −45 dB, user-adjustable. Values below the floor are clipped to the floor.
- R-3.6 Colour map: linear fade **pure blue at the floor (−45 dB) → pure red at 0 dB**. A custom 2-colour map; not `jet`/`viridis`. Show a colour bar labelled in dB.
- R-3.7 Axes: **x = time (s)**, **y = frequency (Hz)** 0 … fs/2, colour = dB. Coefficient k maps to frequency `(k/N)·fs` (Lab 2.pdf item 6); plots show actual Hz, not k.
  *Clarification of v1:* the lab says "dB on the y-axis relative to the highest power"; a spectrogram needs frequency on y, so dB is encoded by colour and by the colour bar. A single-block "power vs frequency" line plot with dB on y is also provided (R-3.8) to satisfy the literal wording. **Confirm with the instructor's example image (page 1 of the PDF) which is intended.**
- R-3.8 Optional spectrum view: select a block → plot `dB vs Hz` for that block, annotated with the coefficient index k on a secondary/top axis (k = 0…N/2).
- R-3.9 Spectrogram can be generated for: the original, the sub-sampled, the up-sampled and the filtered signals.

## 4. Sub-sampling and up-sampling  (v1 §iii)

- R-4.1 User picks integer factor M ≥ 2. Sub-sample = `y[n] = x[nM]`. **No anti-alias filter before decimation** (aliasing is the point of the exercise).
- R-4.2 New sampling rate = fs/M. Save as `.wav` at that rate, play back, and spectrogram it (frequency axis uses fs/M).
- R-4.3 Up-sample the sub-sampled signal by the **same factor M** with a standard high-quality multirate method: zero-insertion followed by a low-pass anti-imaging FIR (Kaiser/windowed-sinc, cutoff = fs_sub/2, gain M), i.e. `scipy.signal.resample_poly(y, M, 1)`.
- R-4.4 Up-sampled signal returns to the original rate fs; can be saved, played, and shown in a spectrogram.
- R-4.5 Reject M that would leave fewer than N samples, with a message.
- R-4.6 UI should let the user compare original vs. up-sampled spectrograms (aliasing and lost high band should be visible).

## 5. Block-by-block low-pass filtering  (v1 §v)

- R-5.1 User enters a cutoff frequency `fc` in Hz (0 < fc ≤ fs/2); uses the same block size N as the spectrogram.
- R-5.2 Map cutoff to a coefficient index: `j_c = floor(fc·N/fs)`.
- R-5.3 For each block: forward transform → zero every coefficient whose frequency index `j > j_c` (**both** `X[j]` and `X[N−j]`) → keep both sine and cosine for `j ≤ j_c` (DC always kept) → inverse transform.
- R-5.4 Concatenate blocks; trim the zero-padding so output length equals input length.
- R-5.5 Output can be saved as `.wav`, played, and spectrogrammed (above `fc` the spectrogram must sit at the noise floor).
- R-5.6 Note for users: independent block processing causes small discontinuities at block edges; expected for this lab (no overlap-add).

## 5b. Tone generator  (new — Lab 2.pdf "second tab" suggestion)

- R-5b.1 Generate pure sine tones: frequency (Hz), duration (s), fs, bit depth, amplitude (default 0.8 of full scale, no clipping).
- R-5b.2 A "batch" button creates the lab set: **500, 1000, 2500, 3000, 5000, 7000 Hz**, 16 kHz sampling, 16-bit, 5 s, saved as `tone_<f>Hz_16k_16bit.wav` in a chosen folder.
- R-5b.3 Generated tones load into the app like any other signal (spectrogram, subsample, filter, play).

## 5c. Processing chains (new — Lab 2.pdf parts f/g)

- R-5c.1 Operations compose: any output (filtered, subsampled, upsampled) can be the input of the next. Needed for "filter first, then subsample" (part g).
- R-5c.2 Convenience pipeline: *block low-pass(fc, N) → subsample(M) → (optional) upsample(M)* in one action, saving each stage.
- R-5c.3 Lab filtering presets: M=2 → fc 4 kHz; M=4 → fc 2 kHz; M=5 → fc 1.6 kHz, block size 16 384 (see §9).
- R-5c.4 Every stage can be played and spectrogrammed so filtered vs unfiltered subsampling can be compared by ear and by eye. Side-by-side/stacked spectrogram view (two signals, shared colour scale) is desirable.

## 6. UI requirements

- R-6.1 Panels/tabs: **Record / Load**, **Tone Generator**, **Spectrogram**, **Resample**, **Filter**.
- R-6.2 Always show the "active signal" (name, fs, bit depth, duration) and let the user choose which stored signal (original / sub-sampled / up-sampled / filtered) is the input to each operation.
- R-6.3 Validate all inputs (N even and ≥ 8, M integer ≥ 2, fc in range, noise floor < 0) with readable error dialogs.
- R-6.4 Save-as dialogs default to `.wav`.

## 7. Acceptance tests

| ID | Test | Pass criteria |
|---|---|---|
| T-1 | Synthetic 1 kHz sine at fs = 8 kHz, N = 1024 | Spectrogram has one red line at 1000 Hz ± fs/N; rest ≈ floor |
| T-2 | Same sine with phase shifted by 90° | Power at that bin is unchanged (shows sine+cosine combined) |
| T-3 | Basis check | U Uᵀ = I; `u_2` is cosine at 2/N, `u_{N−2}` is sine at 2/N |
| T-4 | 16-bit round trip | Save then load → identical samples; 8-bit file header says unsigned 8-bit |
| T-5 | Sub-sample by M = 4 of a 3 kHz tone at 16 kHz | Tone aliases to the expected frequency (1 kHz at fs 4 kHz); no filter used |
| T-6 | Up-sample by M | Output rate = original; length ≈ M × sub length; images removed |
| T-7 | Low-pass fc = 1 kHz on white noise | Spectrogram above 1 kHz at floor; below unchanged; output length = input |
| T-8 | Transform equivalence | Matrix and FFT implementations agree within 1e-9 |
| T-9 | 5000 Hz tone at 16 kHz, subsample ÷2, no filter | Spectrogram line at 3000 Hz (alias), fs = 8 kHz |
| T-10 | Tone batch | Six files exist, 16 kHz, 16-bit, 5.0 s, correct peak frequency in each |
| T-11 | Filter then subsample vs subsample only on a two-tone (1 kHz + 7 kHz) signal | Filtered path has no alias line; unfiltered has one |
| T-12 | N = 16 384, 10 s music at 48 kHz | Spectrogram and filter finish in a few seconds (FFT path) |

## 8. Lab deliverable and experiments (Lab 2.pdf)

Besides the app, the submission is **one PDF**, results in the order below, each preceded by a label such as "below is the graph that shows …", with short explanations where asked. The app must make each of these easy to produce (screenshots/Save Figure as PNG are required: R-8.0).

- R-8.0 Every plot has a **Save figure (PNG)** button (matplotlib toolbar is enough) so images can go into the report.
- a) Generate the six tones (R-5b.2).
- b) Spectrogram of the **2500 Hz** tone; explain.
- c) Spectrogram of the **5000 Hz** tone; explain.
- d) Subsample 5000 Hz tone by 2 (new fs 8 kHz → Nyquist 4 kHz, so 5 kHz aliases to 3 kHz); spectrogram; is it expected? Do the files sound the same?
- e) Record **10 s of continuous music** with bass and treble; include the clip and its spectrogram; relate what is seen to what is heard.
- f) Subsample the music by **2, 4, 5** (no filter): describe sound and spectrograms.
- g) Low-pass the music then subsample: 4 kHz → ÷2, 2 kHz → ÷4, 1.6 kHz → ÷5, block size 16 384; compare with (f) by ear; state a preference.

(The PDF writes "2500 kHz" and "5000 kHz" in b–d; these are clearly Hz, since 5 kHz at fs = 16 kHz is the intended example.)

Report text (PNG captions, explanations) is written by the student; the app only needs to produce the evidence.

## 9. Known inconsistencies in the source documents

- "Block size of 16,284" in part g: probably a typo for **16 384 (2^14)**. 16 284 is even, so the transform works either way. Make N a free entry, default to 16 384, and note this in the report.
- "2500 kHz / 5000 kHz" should read Hz (above).
- The PDF's page 1 contains an example screenshot; its text cannot be extracted, so UI/plot layout details from it are not captured here.

## 10. Open questions / assumptions

1. Mono only (assumed).
2. Should 8-bit playback/save apply dithering? (assumed no).
3. Block overlap for spectrogram (assumed none, per "block by block").
4. Is `.wav` capture sample rate 8 kHz possible on the user's device? Some Windows drivers refuse 8 kHz; see Design risks.
