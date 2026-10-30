from __future__ import annotations

import numpy as np
import pytest

from wecvoice_auto.config import Config
from wecvoice_auto.errors import ChatMismatchError, VoiceSendError, VoiceTooLongError
from wecvoice_auto.sender import VoiceSender
from wecvoice_auto.tts import AudioClip


class FakeTTS:
    def __init__(self, events, seconds=1.0):
        self.events = events
        self.seconds = seconds

    def synthesize(self, text, profile):
        self.events.append(("tts", text, profile.id))
        samples = np.zeros(int(48000 * self.seconds), dtype=np.float32)
        return AudioClip(samples=samples, sample_rate=48000, text=text)


class FakeWindow:
    def __init__(self, events, chat="文件传输助手", fail_chat=False):
        self.events = events
        self.chat = chat
        self.fail_chat = fail_chat

    def ensure(self):
        self.events.append("ensure")

    def activate(self):
        self.events.append("activate")
        return True

    def ensure_chat(self, chat):
        self.events.append(("ensure_chat", chat))
        if self.fail_chat:
            raise ChatMismatchError("wrong chat")
        return self.chat

    def focus_input(self, click_fallback=True):
        self.events.append(("focus", click_fallback))
        return True

    def voice_button(self):
        return None


class FakeRouting:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("routing_enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append("routing_exit")


class FakeHold:
    def __init__(self, trigger, button, press_delay=0.0):
        self.events = []
        self.trigger = trigger
        self.button = button
        self.press_delay = press_delay
        FakeHold.last = self

    def __enter__(self):
        self.events.append(("down", self.trigger, self.press_delay))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append("up")


def make_sender(events, *, chat="文件传输助手", fail_chat=False, seconds=1.0, config=None):
    config = config or Config(max_chars=20, max_seconds=55)
    return VoiceSender(
        config,
        tts=FakeTTS(events, seconds=seconds),
        window=FakeWindow(events, chat=chat, fail_chat=fail_chat),
        player=lambda clip, device, gain: events.append(("play", device, round(clip.duration, 2))),
        routing_factory=lambda cfg: FakeRouting(events),
    )


def test_send_orders_actions(monkeypatch):
    events = []
    monkeypatch.setattr("wecvoice_auto.sender.HoldToTalk", FakeHold)
    monkeypatch.setattr("wecvoice_auto.sender.release_all", lambda: events.append("release_all"))
    sender = make_sender(events)
    result = sender.send("老师早上好！", chat="文件传输助手")

    assert result.ok
    assert result.chunks == 1
    names = [item if isinstance(item, str) else item[0] for item in events]
    assert names.index("ensure") < names.index("activate") < names.index("ensure_chat")
    assert names.index("routing_enter") < names.index("play") < names.index("routing_exit")
    assert events[-1] == "routing_exit"
    assert FakeHold.last.trigger == "alt"
    assert FakeHold.last.press_delay == sender.config.lead_seconds


def test_preview_does_not_touch_wechat(monkeypatch):
    events = []
    monkeypatch.setattr("wecvoice_auto.sender.HoldToTalk", FakeHold)
    sender = make_sender(events)
    result = sender.send("你好", preview=True)
    assert result.preview is True
    assert "ensure" not in events
    assert any(isinstance(item, tuple) and item[0] == "play" for item in events)


def test_chat_mismatch_aborts_before_routing(monkeypatch):
    events = []
    monkeypatch.setattr("wecvoice_auto.sender.HoldToTalk", FakeHold)
    sender = make_sender(events, fail_chat=True)
    with pytest.raises(ChatMismatchError):
        sender.send("你好", chat="别人")
    assert "routing_enter" not in events


def test_too_long_clip_raises(monkeypatch):
    events = []
    monkeypatch.setattr("wecvoice_auto.sender.HoldToTalk", FakeHold)
    sender = make_sender(events, seconds=60.0)
    with pytest.raises(VoiceTooLongError):
        sender.send("很长的话", preview=True)


def test_button_trigger_requires_button(monkeypatch):
    events = []
    monkeypatch.setattr("wecvoice_auto.sender.HoldToTalk", FakeHold)
    sender = make_sender(events)
    with pytest.raises(VoiceSendError):
        sender.send("你好", trigger="button")


def test_empty_text_raises(monkeypatch):
    events = []
    monkeypatch.setattr("wecvoice_auto.sender.HoldToTalk", FakeHold)
    sender = make_sender(events)
    with pytest.raises(VoiceSendError):
        sender.send("[sticker:挥手] https://example.com")
