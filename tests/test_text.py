from __future__ import annotations

import numpy as np

from wecvoice_auto.text import (
    clean_text,
    estimate_duration,
    normalize_voice_text,
    split_text,
)


def test_clean_removes_sticker_and_markdown():
    raw = "老师早上好！[sticker:挥手] **今天**也要加油哦 https://example.com"
    assert clean_text(raw) == "老师早上好！ 今天也要加油哦"


def test_clean_keeps_urls_when_asked():
    raw = "看这里 https://example.com/x"
    assert "https://example.com/x" in clean_text(raw, keep_urls=True)


def test_clean_strips_voice_tag():
    assert clean_text("晚安[voice]") == "晚安"


def test_split_short_text_returns_single_chunk():
    assert split_text("老师晚安。", max_chars=120) == ["老师晚安。"]


def test_split_long_text_respects_limit_and_sentences():
    text = "第一句话。" * 40
    chunks = split_text(text, max_chars=40)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 40 for chunk in chunks)
    assert "".join(chunks) == text


def test_split_hard_wraps_single_long_sentence():
    text = "啊" * 100
    chunks = split_text(text, max_chars=30)
    assert [len(chunk) for chunk in chunks] == [30, 30, 30, 10]


def test_split_empty_text():
    assert split_text("   ", max_chars=10) == []


def test_estimate_duration_grows_with_text():
    assert estimate_duration("你好") < estimate_duration("你好" * 20)


def test_normalize_voice_text_collapses_lines():
    assert normalize_voice_text("  第一行\n\n第二行  ") == "第一行 第二行"


def test_audio_clip_creation():
    from wecvoice_auto.tts import AudioClip

    clip = AudioClip(np.zeros(4800, dtype=np.float32))
    assert abs(clip.duration - 0.1) < 1e-6
