"""High level sender that ties TTS, audio routing and WeChat together."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audio import play_clip
from .config import Config
from .devices import AudioRouting
from .errors import VoiceSendError, VoiceTooLongError
from .input import HoldToTalk, release_all
from .text import split_text
from .tts import AudioClip, EdgeTTS
from .voices import resolve_voice
from .wechat import WeChatWindow

log = logging.getLogger("wecvoice.sender")


@dataclass
class SendResult:
    ok: bool
    chat: str = ""
    voice: str = ""
    chunks: int = 0
    durations: List[float] = field(default_factory=list)
    message: str = ""
    preview: bool = False

    @property
    def total_seconds(self) -> float:
        return round(sum(self.durations), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "chat": self.chat,
            "voice": self.voice,
            "chunks": self.chunks,
            "durations": self.durations,
            "total_seconds": self.total_seconds,
            "message": self.message,
            "preview": self.preview,
        }


class VoiceSender:
    """Send text as a real WeChat voice message.

    Parameters
    ----------
    config:
        Runtime settings.  Defaults to :meth:`Config.load`.
    tts:
        Anything with ``synthesize(text, profile) -> AudioClip``.  Injectable
        for tests.
    window:
        Anything with ``ensure/activate/focus_input/current_chat/voice_button``.
    player:
        Callable ``(clip, device, gain) -> None``.  Injectable for tests.
    routing_factory:
        Callable ``(config) -> context manager``.  Injectable for tests.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        tts: Any = None,
        window: Any = None,
        player: Any = None,
        routing_factory: Any = None,
    ) -> None:
        self.config = config or Config.load()
        self.tts = tts or EdgeTTS(
            sample_rate=self.config.sample_rate,
            timeout=self.config.edge_timeout,
            retries=self.config.edge_retries,
        )
        self.window = window or WeChatWindow()
        self.player = player or self._default_player
        self.routing_factory = routing_factory or AudioRouting

    # ------------------------------------------------------------------ public
    def send(
        self,
        text: str,
        *,
        chat: Optional[str] = None,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None,
        preview: bool = False,
        trigger: Optional[str] = None,
    ) -> SendResult:
        """Speak ``text`` and send it to the open WeChat conversation.

        ``preview=True`` only plays the clip on the default speakers, which is
        useful for auditioning a voice without touching WeChat.
        """
        profile = resolve_voice(
            voice or self.config.voice,
            rate=rate if rate is not None else self.config.rate,
            pitch=pitch if pitch is not None else self.config.pitch,
            volume=volume if volume is not None else self.config.volume,
        )
        chunks = split_text(text, max_chars=self.config.max_chars)
        if not chunks:
            raise VoiceSendError("清理后没有可朗读的文本（可能只有表情包标签或链接）")

        clips: List[AudioClip] = []
        for chunk in chunks:
            clip = self.tts.synthesize(chunk, profile)
            if clip.duration > self.config.max_seconds:
                raise VoiceTooLongError(
                    f"这一段语音有 {clip.duration:.1f} 秒，超过微信 60 秒上限；"
                    "请把 max_chars 调小，或缩短文本。"
                )
            clips.append(clip)
            if self.config.save_audio:
                self._save_clip(clip, len(clips))

        if preview:
            device = self.config.preview_device
            for clip in clips:
                self.player(clip, device, self.config.gain)
            return SendResult(
                ok=True,
                chat=chat or "",
                voice=profile.id,
                chunks=len(clips),
                durations=[round(c.duration, 2) for c in clips],
                message="试听完成（未发送到微信）",
                preview=True,
            )

        active_trigger = trigger or self.config.trigger
        self.window.ensure()
        if self.config.activate_window:
            if not self.window.activate():
                raise VoiceSendError(
                    "无法把微信窗口切到前台，已取消发送（避免按键落到别的窗口）。"
                    "请手动点一下微信聊天窗口后重试。"
                )
        current_chat = ""
        if self.config.verify_chat:
            current_chat = self.window.ensure_chat(chat)
        if self.config.focus_input:
            if not self.window.focus_input(click_fallback=self.config.click_input_fallback):
                log.warning("没能聚焦微信输入框，仍尝试按住 Alt 说话")

        button = None
        if active_trigger == "button":
            button = self.window.voice_button()
            if button is None:
                raise VoiceSendError(
                    "没有找到微信语音按钮。请把 trigger 设为 'alt'，"
                    "或确认微信 4.1.9+ 的语音按钮在界面中可见。"
                )

        durations: List[float] = []
        routing = self.routing_factory(self.config)
        try:
            with routing:
                for index, clip in enumerate(clips, start=1):
                    log.info(
                        "发送第 %d/%d 段：%s，%.1f 秒",
                        index, len(clips), profile.label, clip.duration,
                    )
                    self._send_one(clip, active_trigger, button)
                    durations.append(round(clip.duration, 2))
                    if index < len(clips):
                        time.sleep(max(0.4, self.config.settle_seconds))
                time.sleep(self.config.settle_seconds)
        except Exception:
            release_all()
            raise

        return SendResult(
            ok=True,
            chat=chat or current_chat,
            voice=profile.id,
            chunks=len(clips),
            durations=durations,
            message=f"已发送 {len(clips)} 条语音",
        )

    def preview(self, text: str, **kwargs: Any) -> SendResult:
        return self.send(text, preview=True, **kwargs)

    # ----------------------------------------------------------------- internal
    def _send_one(self, clip: AudioClip, trigger: str, button) -> None:
        # Press first, then play: WeChat opens the recorder on key down, so the
        # first few hundred milliseconds of audio must not happen before it.
        with HoldToTalk(trigger, button, press_delay=self.config.lead_seconds):
            self.player(clip, self.config.output_device, self.config.gain)
            time.sleep(self.config.tail_seconds)

    @staticmethod
    def _default_player(clip: AudioClip, device: Optional[str], gain: float) -> None:
        play_clip(clip, device, gain=gain, blocking=True)

    def _save_clip(self, clip: AudioClip, index: int) -> None:
        base = Path(self.config.audio_dir) if self.config.audio_dir else Path.cwd() / "wecvoice-audio"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = base / f"{stamp}-{index:02d}.wav"
        try:
            clip.to_wav(target)
            log.info("已保存音频：%s", target)
        except Exception as exc:  # noqa: BLE001
            log.warning("保存音频失败：%s", exc)

    def check_devices(self) -> Dict[str, Any]:
        """Quick static check used by the CLI doctor."""
        from .audio import default_input, find_device

        report: Dict[str, Any] = {}
        try:
            output = find_device(self.config.output_device, "output")
            report["output"] = output.to_dict()
        except Exception as exc:  # noqa: BLE001
            report["output_error"] = str(exc)
        try:
            capture = find_device(self.config.input_device, "input")
            report["capture"] = capture.to_dict()
        except Exception as exc:  # noqa: BLE001
            report["capture_error"] = str(exc)
        current = default_input()
        report["default_input"] = current.name if current else ""
        return report
