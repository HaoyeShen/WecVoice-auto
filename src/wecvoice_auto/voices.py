"""Voice presets and Edge TTS parameter handling.

The default preset is ``arona``: a free Microsoft Edge voice tuned to sound
like a cheerful, soft-spoken anime assistant.  It is an *approximation* of
Arona from Blue Archive, not an official voice model and not a clone of the
character's voice actress.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional

DEFAULT_VOICE = "arona"

_RATE_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?%$")
_PITCH_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?Hz$")
_VOLUME_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?%$")
_EDGE_NAME_RE = re.compile(r"^[a-z]{2,3}-[A-Za-z]{2,}(?:-[A-Za-z]+)*-[A-Za-z0-9]+Neural$")


@dataclass(frozen=True)
class VoiceProfile:
    """A complete recipe for one voice.

    ``voice`` is the Edge TTS short name (for example
    ``zh-CN-XiaoyiNeural``).  ``rate``/``pitch``/``volume`` use the same
    ``+10%`` / ``-5Hz`` syntax as Edge TTS.
    """

    id: str
    label: str
    voice: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    language: str = "zh-CN"
    description: str = ""
    engine: str = "edge"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "voice": self.voice,
            "rate": self.rate,
            "pitch": self.pitch,
            "volume": self.volume,
            "language": self.language,
            "description": self.description,
            "engine": self.engine,
        }


PRESETS: Dict[str, VoiceProfile] = {
    "arona": VoiceProfile(
        id="arona",
        label="阿洛娜（近似）",
        voice="zh-CN-XiaoyiNeural",
        rate="+5%",
        pitch="+12Hz",
        volume="+0%",
        description="清爽、稍微上扬的少女音，阿洛娜风格近似，非官方原声。",
    ),
    "arona-happy": VoiceProfile(
        id="arona-happy",
        label="阿洛娜·元气",
        voice="zh-CN-XiaoyiNeural",
        rate="+12%",
        pitch="+20Hz",
        volume="+5%",
        description="语速更快、音调更高的元气版本。",
    ),
    "arona-soft": VoiceProfile(
        id="arona-soft",
        label="阿洛娜·轻声",
        voice="zh-CN-XiaoyiNeural",
        rate="-4%",
        pitch="+8Hz",
        volume="-5%",
        description="放慢语速、降低音量的夜间版本。",
    ),
    "plana": VoiceProfile(
        id="plana",
        label="普拉娜（近似）",
        voice="zh-CN-XiaoxiaoNeural",
        rate="-5%",
        pitch="+0Hz",
        description="平静、柔和的声线，适合冷淡一点的角色。",
    ),
    "xiaoyi": VoiceProfile(
        id="xiaoyi",
        label="晓伊·少女",
        voice="zh-CN-XiaoyiNeural",
        description="Edge TTS 自带少女音，不加修饰。",
    ),
    "xiaoxiao": VoiceProfile(
        id="xiaoxiao",
        label="晓晓·温柔",
        voice="zh-CN-XiaoxiaoNeural",
        rate="-2%",
        description="Edge TTS 自带温柔女声。",
    ),
    "yunxi": VoiceProfile(
        id="yunxi",
        label="云希·少年",
        voice="zh-CN-YunxiNeural",
        language="zh-CN",
        description="年轻男声。",
    ),
    "yunjian": VoiceProfile(
        id="yunjian",
        label="云健·旁白",
        voice="zh-CN-YunjianNeural",
        description="低沉男声，适合旁白。",
    ),
    "xiaobei": VoiceProfile(
        id="xiaobei",
        label="晓北·东北",
        voice="zh-CN-liaoning-XiaobeiNeural",
        description="东北口音女声。",
    ),
    "xiaoni": VoiceProfile(
        id="xiaoni",
        label="晓妮·陕西",
        voice="zh-CN-shaanxi-XiaoniNeural",
        description="陕西口音女声。",
    ),
    "nanami": VoiceProfile(
        id="nanami",
        label="七海·日语",
        voice="ja-JP-NanamiNeural",
        language="ja-JP",
        description="日语女声；阿洛娜的台词是日语时可以试试。",
    ),
    "arona-jp": VoiceProfile(
        id="arona-jp",
        label="阿洛娜·日语近似",
        voice="ja-JP-NanamiNeural",
        rate="+3%",
        pitch="+10Hz",
        language="ja-JP",
        description="日语少女音，风格近似。",
    ),
}


def list_presets(language: Optional[str] = None) -> List[VoiceProfile]:
    """Return presets in declaration order, optionally filtered by language."""
    values = list(PRESETS.values())
    if language:
        values = [item for item in values if item.language == language]
    return values


def _validate(name: str, value: str, pattern: re.Pattern) -> str:
    text = str(value).strip()
    if not pattern.match(text):
        raise ValueError(
            f"{name} 的格式不对：{text!r}；示例：rate='+10%', pitch='+5Hz', volume='+0%'"
        )
    return text


def resolve_voice(
    voice: Optional[str] = None,
    *,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    volume: Optional[str] = None,
) -> VoiceProfile:
    """Resolve a preset id, or a raw Edge voice name, into a profile.

    Unknown preset ids that *look* like Edge voice names are accepted, so a
    user can pass ``zh-CN-XiaoxiaoNeural`` directly without editing the
    package.
    """
    reference = (voice or DEFAULT_VOICE).strip()
    if not reference:
        reference = DEFAULT_VOICE

    preset = PRESETS.get(reference)
    if preset is not None:
        profile = preset
    elif _EDGE_NAME_RE.match(reference):
        profile = VoiceProfile(
            id=reference,
            label=reference,
            voice=reference,
            description="自定义 Edge TTS 音色。",
        )
    else:
        known = "、".join(PRESETS)
        raise ValueError(f"未知音色：{reference!r}。内置音色：{known}")

    changes = {}
    if rate is not None:
        changes["rate"] = _validate("rate", rate, _RATE_RE)
    if pitch is not None:
        changes["pitch"] = _validate("pitch", pitch, _PITCH_RE)
    if volume is not None:
        changes["volume"] = _validate("volume", volume, _VOLUME_RE)
    if changes:
        profile = replace(profile, **changes)
    return profile


def iter_presets() -> Iterable[VoiceProfile]:
    return PRESETS.values()
