from __future__ import annotations

import numpy as np

from wecvoice_auto import audio


def test_resample_changes_length():
    samples = np.sin(np.linspace(0, 6.28, 48000)).astype(np.float32)
    out = audio.resample_linear(samples, 48000, 16000)
    assert len(out) == 16000
    assert out.dtype == np.float32


def test_resample_same_rate_is_identity():
    samples = np.ones(10, dtype=np.float32)
    assert np.array_equal(audio.resample_linear(samples, 48000, 48000), samples)


def test_prepare_channels_mono_and_stereo():
    samples = np.array([0.1, 0.2], dtype=np.float32)
    assert audio._prepare_channels(samples, 1).shape == (2,)
    stereo = audio._prepare_channels(samples, 2)
    assert stereo.shape == (2, 2)
    assert np.allclose(stereo[:, 0], stereo[:, 1])


def test_find_device_prefers_closest_name(monkeypatch):
    fake = [
        audio.DeviceInfo(0, "Speakers (Realtek)", "output", 2, 48000, 0),
        audio.DeviceInfo(1, "CABLE Input (VB-Audio Virtual Cable)", "output", 2, 48000, 0),
    ]
    monkeypatch.setattr(audio, "list_devices", lambda kind=None: fake)
    found = audio.find_device("CABLE Input", "output")
    assert found.index == 1


def test_find_device_raises_with_available_list(monkeypatch):
    fake = [audio.DeviceInfo(0, "Speakers", "output", 2, 48000, 0)]
    monkeypatch.setattr(audio, "list_devices", lambda kind=None: fake)
    try:
        audio.find_device("CABLE Input", "output")
    except Exception as exc:
        assert "CABLE Input" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected AudioDeviceError")
