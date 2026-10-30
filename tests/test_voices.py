from __future__ import annotations

import pytest

from wecvoice_auto.voices import DEFAULT_VOICE, PRESETS, list_presets, resolve_voice


def test_default_voice_is_arona():
    assert DEFAULT_VOICE == "arona"
    assert PRESETS["arona"].voice == "zh-CN-XiaoyiNeural"


def test_resolve_default():
    profile = resolve_voice()
    assert profile.id == "arona"
    assert profile.pitch == "+12Hz"


def test_override_rate_pitch_volume():
    profile = resolve_voice("arona", rate="+10%", pitch="+2Hz", volume="-5%")
    assert (profile.rate, profile.pitch, profile.volume) == ("+10%", "+2Hz", "-5%")


def test_resolve_raw_edge_voice():
    profile = resolve_voice("zh-CN-XiaoxiaoNeural")
    assert profile.voice == "zh-CN-XiaoxiaoNeural"
    assert profile.id == "zh-CN-XiaoxiaoNeural"


def test_resolve_unknown_name_raises():
    with pytest.raises(ValueError):
        resolve_voice("not-a-voice")


def test_bad_rate_format_raises():
    with pytest.raises(ValueError):
        resolve_voice("arona", rate="fast")


def test_list_presets_order_and_filter():
    assert list_presets()[0].id == "arona"
    japanese = list_presets("ja-JP")
    assert japanese and all(item.language == "ja-JP" for item in japanese)


def test_every_preset_has_edge_voice_name():
    for item in PRESETS.values():
        assert item.voice.endswith("Neural"), item
        assert item.rate.endswith("%")
        assert item.pitch.endswith("Hz")
