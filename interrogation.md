# Interrogation — questions asked to Claude and the answers (relevant parts only)

Format: my question, then the answer that shaped the requirements, design or analysis. Chit-chat, tool errors and UI cosmetics are left out.

---

## Q1. Is the transform matrix on the slide concrete enough to build from?

**Yes.** The slide defines a real orthonormal basis, an N×N matrix U (N = block size, must be **even**):

| k | row u_k |
|---|---|
| 0 | `1/√N` (DC) |
| 1 … N/2−1 | `√(2/N)·cos(2πkn/N)` |
| N/2 | `cos(πn)/√N` (Nyquist) |
| N/2+1 … N−1 | `√(2/N)·sin(2π(N−k)n/N)` |

- 1 + (N/2−1) + 1 + (N/2−1) = N rows, each of unit norm, so forward is `X = U·x` and inverse is `x = Uᵀ·X`.
- The sines run from high index to low frequency: index N−2 is the sine at the same frequency as the cosine at index 2. That is exactly the slide's `u_2` (cosine) / `u_{N−2}` (sine) example, both at 2/N cycles per sample.
- Coefficient k corresponds to frequency `(k/N)·Fs` for k ≤ N/2; a sine at index N−j has frequency `(j/N)·Fs`.
- Consequence for the code: power at frequency j is `X[j]² + X[N−j]²` (cosine and sine together). DC and Nyquist have no sine partner.

*Effect:* became requirements R-2.1 – R-2.5 and test `test_slide_u2_and_uN2`.

## Q2. What does `Lab 2.pdf` require that my first requirements missed, and what is ambiguous?

Added in `Requirements_v2.md`:
- The transform must be the class transform **implemented with an FFT** (item 7a).
- A tone generator for the six lab tones; chained operations (filter, then sub-sample); an optional up-sampling step for easy comparison.
- Deliverable: one PDF, results in lab order, each introduced with "below is the graph that shows…", plus explanations.

Ambiguities, and how they were resolved:
- **"dB on the y-axis"** versus a spectrogram needing frequency on y: dB is shown as colour (with a colour bar). A single-block "dB vs Hz" view is also provided so dB can be read on a y-axis. *To confirm against the instructor's example image (page 1 of the PDF).*
- **"2500 kHz / 5000 kHz"** in parts b–d: read as Hz (5 kHz is the intended aliasing example at 16 kHz sampling).
- **"Block size 16,284"** in part g: probably a typo for 16,384 (2¹⁴). The transform works for any even N, so N is a free entry, default 16,384.

## Q3. Why use the FFT instead of the explicit matrix?

The lab asks for it, and it is also needed for size: a 16,384×16,384 matrix of doubles is about 2 GB. The FFT version computes exactly the same coefficients:
- cosine coefficient = `√(2/N)·Re F[j]`, sine coefficient = `−√(2/N)·Im F[j]` (the sign comes from the slide using +sin while the DFT uses e^(−jθ)); DC and Nyquist are scaled by `1/√N`.
- The explicit matrix is kept only as a **test reference**; test `test_basis_orthonormal_and_fft_matches_matrix` checks they agree to 1e-9 and that U·Uᵀ = I.

## Q4. How are sine and cosine combined, and why does it matter?

The power at a frequency is the sum of squares of its cosine and sine coefficients. If only the cosine were used, a tone's measured power would depend on its phase (a pure sine would nearly vanish at a block start). Test `test_sine_peak_and_phase_independence` shows a sine, a cosine and a 1-radian-shifted tone have the same power.

## Q5. When I sub-sample without filtering the audio sounds bad; when I filter first it sounds good. Why?

**It is aliasing.**

- A sample rate can only represent frequencies up to **half** that rate (the Nyquist limit). Higher frequencies cannot be recorded as themselves; without a filter they are recorded as a *different, lower* frequency. (Like a wheel filmed by a slow camera appearing to spin slowly or backwards.)
- Keeping every M-th sample divides the sample rate by M, so the Nyquist limit drops to `Fs/(2M)`. Anything above it **folds back** into the representable range.
- **Lab example:** 5000 Hz tone at 16 kHz, sub-sampled by 2 → new rate 8 kHz, limit 4 kHz. 5000 Hz folds to `8000 − 5000 = 3000 Hz`: a tone that was never in the original, visible as a line at 3 kHz in the spectrograph.
- **Music:** the same happens to hundreds of frequencies at once. The treble above the new limit lands on top of the real bass and mid notes, so the result sounds harsh/metallic; the spectrograph shows extra lines and mirrored copies of the high content in the wrong places.
- **Why filtering first works:** a low-pass filter at the new Nyquist removes the frequencies that would fold back, *before* samples are thrown away. What remains fits under the new limit, so nothing aliases. The cost is lost treble (duller sound) — but clean instead of corrupted. You cannot keep those high frequencies at the lower rate: the only choice is to remove them cleanly or let them corrupt the rest.
- **Rule of thumb:** before reducing the rate by M, low-pass at `(Fs/M)/2`. For a 16 kHz recording this gives the lab's presets: ÷2 → 4 kHz, ÷4 → 2 kHz, ÷5 → 1.6 kHz.

*Report sentence:* "Sub-sampling without filtering makes frequencies above the new Nyquist limit alias to lower frequencies, corrupting the signal. Low-pass filtering first removes them, so the result contains no aliases; it loses high-frequency content but sounds clean."

*Check:* test `test_alias_5k_sub2` (peak at 3 kHz) and `test_filter_then_subsample_removes_alias` (5 kHz tone is gone after filtering at 3.9 kHz, so nothing is left to alias).

## Q6. Why do the spectrographs show a smear at the very end, and slight artefacts after filtering?

- The last partial block is **zero-padded** to the block size; the abrupt cut spreads energy over neighbouring frequencies, so the final column looks smeared.
- Block-by-block filtering treats blocks independently (no overlap-add), so small discontinuities at block edges are expected. This follows the lab's definition ("repeat this for every block").


