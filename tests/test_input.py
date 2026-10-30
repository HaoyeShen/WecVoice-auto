from __future__ import annotations

import pytest

from wecvoice_auto import input as keyinput
from wecvoice_auto.errors import VoiceSendError


def test_alt_uses_right_alt_and_extended_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(
        keyinput,
        "_key_event",
        lambda vk, scan, flags: calls.append((vk, scan, flags)) or True,
    )

    assert keyinput.alt_down() is True
    assert keyinput.alt_up() is True

    assert len(calls) == 2
    down, up = calls
    assert down[0] == keyinput.VK_RMENU
    assert down[1] == 0x38
    assert down[2] & keyinput.KEYEVENTF_EXTENDEDKEY
    assert up[0] == keyinput.VK_RMENU
    assert up[2] & keyinput.KEYEVENTF_EXTENDEDKEY
    assert up[2] & keyinput.KEYEVENTF_KEYUP


def test_rejected_alt_raises_clear_error(monkeypatch):
    monkeypatch.setattr(keyinput, "_key_event", lambda *args: False)
    with pytest.raises(VoiceSendError):
        with keyinput.HoldToTalk("alt"):
            pass
