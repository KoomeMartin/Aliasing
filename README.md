# Lab 2 — Aliasing Investigator

This README is a **guide to the submission**: where each requirement, design decision, result and piece of analysis lives, and how to run things.
Task (from `Lab 2.pdf`): build a Python/tkinter app with Claude (capture, spectrograph, sub-sampling, block filtering), then use it to investigate aliasing.

## 1. Where to find what

| You want to see… | Go to |
|---|---|
| **Requirements** (what the app must do) | `Requirements_v1_.md` (my first draft), `Requirements_v2.md` (refined, testable, traceable IDs R-x.y, acceptance tests T-1…T-12) |
| **Design** (how it is built) | `Design.md` |
| **Interrogation** (the questions I asked Claude and the answers, only the relevant ones) | `interrogation.md` |
| **The app / source code** | `main.py` (start here), `ui/` (tkinter UI), `dsp/` (transform, spectrogram, resampling, filter, tones), `audio/` (WAV I/O, mic/playback) |
| **Tests** | `tests/test_dsp.py` (15 unit tests), `tests/smoke_ui.py` (drives the real UI) |
| **Results — tones, parts a–d** | `out/` (see §3) |
| **Results — music, parts e–g** | `Music/` (see §3) |
| **Analysis / explanations of the results** | `latex/main.tex` (report source; results a to g in handout order, each introduced by "below is the graph that shows…"), figures in `latex/images/`. Build notes in `latex/README.md`. The compiled PDF (`latex/main.pdf`) is produced by running `pdflatex`. A short conceptual explanation of aliasing is also in `interrogation.md` (Q5). |
| The assignment itself | `Lab 2.pdf` |

## 2. How to run

    pip install -r requirements.txt
    python main.py                          # the app (tab "Lab 2": Parts 1-4; tab "misc": tone generator)
    python -m pytest tests -q               # unit tests
    python tests/smoke_ui.py                # UI smoke test (writes screenshots to out/smoke/)
    python experiments/run_lab_experiments.py [music.wav]   # regenerates parts a-d (and e-g if a clip is given) into out/

App parts: **1** capture/playback (8/16/48 kHz, 8-bit unsigned / 16-bit signed, .wav) · **2** spectrograph (block size N and dB floor adjustable) · **3** sub-sampling by M with **no** filter, optional up-sampling · **4** block-by-block low-pass (optionally followed by Part 3's sub-sampling).

## 3. Results map — lab parts a–g

Naming note: file names are kept as produced (including the "spectograph" spelling in `Music/`).

| Lab part | What | Files |
|---|---|---|
| a | Six pure tones (500, 1000, 2500, 3000, 5000, 7000 Hz), 16 kHz, 16-bit, 5 s | `out/tones/tone_<f>Hz_16k_16bit.wav` |
| b | Spectrograph of the 2500 Hz tone | `out/b_tone2500.png` |
| c | Spectrograph of the 5000 Hz tone | `out/c_tone5000.png` |
| d | 5000 Hz tone sub-sampled by 2 (no filter) and its spectrograph | `out/d_tone5000_sub2.wav`, `out/d_tone5000_sub2.png` |
| e | 10 s music clip (16 kHz, 16-bit) and its spectrograph | `Music/music_play.wav`; report figure `latex/images/e_music_spectrograph.png` (the older `Music/Music_play_spectograph.png` was made from an earlier recording and does not match the current WAV) |
| f | Music sub-sampled by 2, 4, 5 **without** filtering (→ 8000, 4000, 3200 Hz) | `Music/music_play_subsample_f2.wav`, `…_f4.wav`, `…_f5.wav` and spectrographs `Music/Music_play_spectograph_f2.png`, `…_f4.png`, `…_f5.png` |
| g | Music **low-passed first** (4 kHz, 2 kHz, 1.6 kHz), then sub-sampled by 2, 4, 5 | low-passed full-rate files: `Music/music_play_filter_4.wav`, `…_2.wav`, `…_1.6.wav` (spectrographs `Music/Music_play_filter_4khz.png`, `…_2khz.png`, `…_1.6khz.png`); after sub-sampling: `Music/music_play_subsample_f2_after_filter_4.wav`, `…_f4_after_filter_2.wav`, `…_f5_after_filter_1.6.wav` (spectrographs `Music/Music_play_spectograph_f2_after_filter_4khz.png`, `…_f4_after_filter_2khz.png`, `…_f5_after_filter_1.6khz.png`) |

Listen-and-compare questions (d, e, f, g) are answered in `latex/main.tex`.

## 4. Requirements ↔ implementation ↔ verification

| `Lab 2.pdf` requirement | Implemented in | Verified by |
|---|---|---|
| 1. Python + tkinter | `main.py`, `ui/app.py` | `tests/smoke_ui.py` |
| 2. Capture arbitrary length; 8/16/48 kHz; 16-bit signed, 8-bit unsigned; uncompressed .wav | `audio/device.py`, `audio/wavio.py`, Part 1 | WAV round-trip + header checks in `test_dsp.py`; live microphone capture is hardware-dependent and not automated (recorded clip: `Music/music_play.wav`) |
| 3. Playback | `audio/device.py`, Play buttons | manual (audio output) |
| 4. Spectrograph: block-by-block, variable block size, class transform, dB rel. max, blue→red, −45 dB floor, sine+cosine combined | `dsp/basis.py`, `dsp/spectrum.py`, `ui/plots.py` | orthonormality, phase-independent power, floor clipping tests |
| 5. Sub-sample every M-th with **no** filter; write wav, play, spectrograph; up-sample with standard multirate filter | `dsp/resample.py`, Part 3 | 5 kHz tone ÷2 aliases to 3 kHz test; up-sample rate/length test |
| 6. Coefficient k ↔ frequency (k/N)·Fs; plots in real Hz | `dsp/basis.py` (`freq_of_index`), `ui/plots.py` | peak-bin tests; axes are in Hz |
| 7. Block-by-block low-pass, keep **both** sine and cosine below cutoff; **FFT-based orthonormal transform** | `dsp/blockfilter.py`, `dsp/basis.py` (`forward_blocks`/`inverse_blocks`) | FFT result equals the explicit matrix to 1e-9; kept coefficients unchanged, nothing above cutoff; N = 16,384 on 10 s audio runs in seconds |
| Experiments a–g | app + `experiments/run_lab_experiments.py` | outputs listed in §3 |
| Requirements document (v1 → v2), design, interrogation | `Requirements_*.md`, `Design.md`, `interrogation.md` | — |

## 5. Status

- Done: app, tests, requirements v1/v2, design, interrogation (this round), evidence for parts a–g.
- Done in source form: the results report (`latex/main.tex`). Pending: compile it to PDF and add listening notes you confirm yourself.
- Known limitations: last partial block is zero-padded (a small smear at the end of spectrographs); block-wise filtering has no overlap, so slight block-edge artefacts are expected; 8 kHz microphone capture may be refused by some Windows drivers (the app reports an error rather than silently using another rate).
