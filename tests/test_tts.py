from __future__ import annotations

import io
import math
import wave

import numpy as np

from wecvoice_auto.tts import AudioClip, decode_mp3, trim_silence


def _wav_bytes(seconds: float = 0.5, rate: int = 24000, freq: float = 440.0) -> bytes:
    frames = int(seconds * rate)
    data = b"".join(
        int(16000 * math.sin(2 * math.pi * freq * i / rate)).to_bytes(2, "little", signed=True)
        for i in range(frames)
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(data)
    return buffer.getvalue()


def test_decode_and_resample_wav():
    clip = decode_mp3(_wav_bytes(), sample_rate=48000)
    assert clip.sample_rate == 48000
    assert 0.4 < clip.duration < 0.8
    assert clip.samples.dtype == np.float32


def test_trim_silence_keeps_pad():
    samples = np.zeros(48000, dtype=np.float32)
    samples[20000:30000] = 0.5
    trimmed = trim_silence(samples, sample_rate=48000)
    assert trimmed.size < samples.size
    assert trimmed.size > 10000


def test_audio_clip_wav_roundtrip(tmp_path):
    clip = AudioClip(np.zeros(4800, dtype=np.float32), sample_rate=48000)
    target = clip.to_wav(tmp_path / "clip.wav")
    assert target.is_file()
    with wave.open(str(target), "rb") as handle:
        assert handle.getframerate() == 48000
        assert handle.getnframes() == 4800
