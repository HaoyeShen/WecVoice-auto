"""Integrate WecVoice-auto into a reply pipeline.

The important part is ordering: send (or decide) the text reply first, then
turn *short* replies into voice.  WeChat voice bubbles are capped at 60s and
long TTS clips sound unnatural, so keep voice replies to a sentence or two.
"""

from __future__ import annotations

import logging

from wecvoice_auto import VoiceSender
from wecvoice_auto.errors import WecVoiceError

log = logging.getLogger("bot.voice")
voice = VoiceSender()


def maybe_send_voice(reply_text: str, chat: str, *, want_voice: bool = True) -> bool:
    """Send ``reply_text`` as a voice message when appropriate.

    Returns ``True`` when a voice bubble was sent.  Never raises: a voice
    failure must not break the normal text reply path.
    """
    if not want_voice:
        return False
    if len(reply_text) > 120:
        log.info("回复太长（%d 字），跳过语音", len(reply_text))
        return False
    try:
        result = voice.send(reply_text, chat=chat)
        log.info("语音已发送：%s", result.to_dict())
        return result.ok
    except WecVoiceError as exc:
        log.warning("语音发送失败，保留文字回复：%s", exc)
        return False
