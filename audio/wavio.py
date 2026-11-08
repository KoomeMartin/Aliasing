"""WAV I/O. 16-bit = signed little-endian int16; 8-bit = unsigned byte."""
import wave

import numpy as np


def to_pcm(x, bits):
    x = np.asarray(x, float)
    if bits == 16:
        return np.clip(np.round(x * 32768), -32768, 32767).astype("<i2")
    if bits == 8:
        return np.clip(np.round(x * 128 + 128), 0, 255).astype("u1")
    raise ValueError("bits must be 8 or 16")


def from_pcm(a, bits):
    if bits == 16:
        return np.asarray(a, "<i2").astype(float) / 32768
    if bits == 8:
        return (np.asarray(a, "u1").astype(float) - 128) / 128
    raise ValueError("bits must be 8 or 16")


def write_wav(path, x, fs, bits=16):
    pcm = to_pcm(x, bits)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(bits // 8)
        w.setframerate(int(fs))
        w.writeframes(pcm.tobytes())


def read_wav(path):
    """Returns (float samples in [-1,1), fs, bits). Multichannel -> mean."""
    with wave.open(path, "rb") as w:
        ch, width, fs, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width not in (1, 2):
        raise ValueError("only 8- and 16-bit PCM WAV files are supported")
    bits = width * 8
    x = from_pcm(np.frombuffer(raw, "u1" if bits == 8 else "<i2"), bits)
    if ch > 1:
        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x, fs, bits
