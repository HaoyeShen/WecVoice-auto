"""Keyboard and mouse primitives for WeChat's hold-to-talk gesture."""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from typing import Optional

from .errors import VoiceSendError

log = logging.getLogger("wecvoice.input")

VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

_user32 = ctypes.windll.user32
_user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
_user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
_user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]


def alt_down() -> None:
    _user32.keybd_event(VK_MENU, 0, 0, 0)


def alt_up() -> None:
    _user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)


def left_down() -> None:
    _user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)


def left_up() -> None:
    _user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def click_at(x: int, y: int) -> None:
    _user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    left_down()
    time.sleep(0.04)
    left_up()


class HoldToTalk:
    """Hold Alt (or the voice button) while audio is played.

    Used as a context manager::

        with HoldToTalk("alt"):
            play(clip)
    """

    def __init__(self, trigger: str = "alt", button=None, *, press_delay: float = 0.0) -> None:
        if trigger not in ("alt", "button"):
            raise ValueError("trigger 必须是 'alt' 或 'button'")
        self.trigger = trigger
        self.button = button
        self.press_delay = max(0.0, float(press_delay))
        self._pressed = False
        self._rect: Optional[tuple] = None

    def _button_rect(self) -> Optional[tuple]:
        if self.button is None:
            return None
        try:
            box = self.button.BoundingRectangle
            if box is None or box.width() <= 0 or box.height() <= 0:
                return None
            return (box.left, box.top, box.right, box.bottom)
        except Exception:  # noqa: BLE001
            return None

    def __enter__(self) -> "HoldToTalk":
        if self.trigger == "alt":
            alt_down()
            self._pressed = True
        else:
            rect = self._button_rect()
            if rect is None:
                raise VoiceSendError(
                    "trigger='button' 但没有找到微信语音按钮；可以改用 trigger='alt'。"
                )
            self._rect = rect
            x = (rect[0] + rect[2]) // 2
            y = (rect[1] + rect[3]) // 2
            _user32.SetCursorPos(x, y)
            time.sleep(0.08)
            left_down()
            self._pressed = True
        if self.press_delay:
            time.sleep(self.press_delay)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.trigger == "alt":
                alt_up()
            else:
                left_up()
        finally:
            self._pressed = False
            time.sleep(0.05)


def release_all() -> None:
    """Best-effort cleanup after a crash while a key/button was held."""
    try:
        alt_up()
    except Exception:  # noqa: BLE001
        pass
    try:
        left_up()
    except Exception:  # noqa: BLE001
        pass
