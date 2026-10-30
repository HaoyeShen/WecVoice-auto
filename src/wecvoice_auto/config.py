"""Configuration object for WecVoice-auto.

The config is deliberately plain: a JSON file plus a dataclass.  It is stored
in ``%APPDATA%\\WecVoice-auto\\config.json`` by default, and every field can be
overridden per call.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Dict, Optional

from .voices import DEFAULT_VOICE

ENV_CONFIG = "WECVOICE_CONFIG"


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "WecVoice-auto" / "config.json"
    return Path.home() / ".wecvoice-auto" / "config.json"


@dataclass
class Config:
    """Runtime settings for :class:`wecvoice_auto.VoiceSender`."""

    # Voice
    voice: str = DEFAULT_VOICE
    rate: Optional[str] = None
    pitch: Optional[str] = None
    volume: Optional[str] = None
    max_chars: int = 120
    max_seconds: float = 55.0
    sample_rate: int = 48000

    # Audio routing
    output_device: str = "CABLE Input"
    input_device: str = "CABLE Output"
    switch_default_input: bool = True
    restore_default_input: bool = True
    preview_device: Optional[str] = None
    gain: float = 1.0

    # WeChat / UI automation
    trigger: str = "alt"  # "alt" or "button"
    lead_seconds: float = 0.35
    tail_seconds: float = 0.30
    settle_seconds: float = 1.1
    activate_window: bool = True
    focus_input: bool = True
    verify_chat: bool = True
    click_input_fallback: bool = True

    # Debug
    save_audio: bool = False
    audio_dir: Optional[str] = None
    edge_timeout: float = 30.0
    edge_retries: int = 2

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.trigger not in ("alt", "button"):
            raise ValueError("trigger 只能是 'alt' 或 'button'")
        if self.max_chars <= 0:
            raise ValueError("max_chars 必须大于 0")
        if not (1.0 <= self.max_seconds <= 59.5):
            raise ValueError("max_seconds 必须在 1 到 59.5 之间")
        if not (8000 <= self.sample_rate <= 192000):
            raise ValueError("sample_rate 不合理")
        if not (0.0 < self.gain <= 4.0):
            raise ValueError("gain 必须在 0 到 4 之间")
        if self.lead_seconds < 0 or self.tail_seconds < 0:
            raise ValueError("lead_seconds / tail_seconds 不能为负数")

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "Config":
        """Load config from ``path`` (or the default location)."""
        config_path = Path(path) if path else Path(os.environ.get(ENV_CONFIG) or default_config_path())
        if not config_path.is_file():
            return cls()
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"配置文件读取失败：{config_path}（{exc}）") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"配置文件格式不对：{config_path}")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Config":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(raw) - allowed)
        values = {key: value for key, value in raw.items() if key in allowed}
        config = cls(**values)
        if unknown:
            setattr(config, "_unknown_keys", unknown)
        return config

    def save(self, path: Optional[str | Path] = None) -> Path:
        """Write the config as pretty JSON, creating parent directories."""
        config_path = Path(path) if path else Path(os.environ.get(ENV_CONFIG) or default_config_path())
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return config_path

    def with_overrides(self, **kwargs: Any) -> "Config":
        """Return a copy with non-``None`` values applied."""
        clean = {key: value for key, value in kwargs.items() if value is not None}
        return replace(self, **clean)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
