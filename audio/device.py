"""Microphone capture (arbitrary length) and playback via sounddevice."""
import queue

import numpy as np
import sounddevice as sd


class Recorder:
    def __init__(self, fs):
        self.fs = int(fs)
        self._q = queue.Queue()
        self._n = 0
        self._stream = None

    def start(self):
        def cb(indata, frames, t, status):
            self._q.put(indata[:, 0].copy())
            self._n += frames
        # raises sd.PortAudioError if the device rejects this rate (no silent fallback)
        sd.check_input_settings(samplerate=self.fs, channels=1, dtype="int16")
        self._stream = sd.InputStream(samplerate=self.fs, channels=1,
                                      dtype="int16", callback=cb)
        self._stream.start()

    def elapsed(self):
        return self._n / self.fs

    def stop(self):
        self._stream.stop()
        self._stream.close()
        chunks = []
        while not self._q.empty():
            chunks.append(self._q.get())
        pcm = np.concatenate(chunks) if chunks else np.zeros(0, "int16")
        return pcm.astype(float) / 32768


def play(x, fs):
    sd.stop()
    sd.play(np.asarray(x, "float32"), int(fs))


def stop():
    sd.stop()
