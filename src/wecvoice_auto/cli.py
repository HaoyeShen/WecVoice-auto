"""Command line interface: ``wecvoice``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .audio import format_device_table, list_devices, play_clip
from .config import Config, default_config_path
from .doctor import format_report, run_checks
from .errors import WecVoiceError
from .sender import VoiceSender
from .text import clean_text
from .tts import EdgeTTS, list_edge_voices
from .voices import list_presets, resolve_voice


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_config(path: Optional[str]) -> Config:
    return Config.load(path)


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_checks(_load_config(args.config))
    if args.json:
        _print_json([
            {"level": c.level, "title": c.title, "detail": c.detail} for c in checks
        ])
    else:
        print(format_report(checks))
    return 1 if any(c.level == "fail" for c in checks) else 0


def _cmd_devices(args: argparse.Namespace) -> int:
    devices = list_devices()
    if args.json:
        _print_json([d.to_dict() for d in devices])
        return 0
    print(format_device_table())
    return 0


def _cmd_voices(args: argparse.Namespace) -> int:
    if args.online:
        voices = list_edge_voices(args.locale)
        if args.json:
            _print_json(voices)
            return 0
        for voice in voices:
            print(
                f"{voice.get('ShortName', ''):<36} {voice.get('Locale', ''):<8} "
                f"{voice.get('Gender', ''):<7} {voice.get('FriendlyName', '')}"
            )
        return 0

    presets = list_presets()
    if args.json:
        _print_json([p.to_dict() for p in presets])
        return 0
    print(f"{'ID':<14} {'音色':<16} {'Edge 名称':<32} rate / pitch")
    print("-" * 90)
    for item in presets:
        mark = " *默认" if item.id == "arona" else ""
        print(
            f"{item.id:<14} {item.label:<16} {item.voice:<32} "
            f"{item.rate} / {item.pitch}{mark}"
        )
    print("\n提示：用 `wecvoice voices --online --locale zh` 查看 Edge 全部中文音色。")
    return 0


def _cmd_say(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    profile = resolve_voice(
        args.voice or config.voice,
        rate=args.rate if args.rate is not None else config.rate,
        pitch=args.pitch if args.pitch is not None else config.pitch,
        volume=args.volume if args.volume is not None else config.volume,
    )
    text = clean_text(args.text)
    if not text:
        print("没有可朗读的文本", file=sys.stderr)
        return 2
    engine = EdgeTTS(sample_rate=config.sample_rate, timeout=config.edge_timeout, retries=config.edge_retries)
    clip = engine.synthesize(text, profile)
    if args.save:
        target = clip.to_wav(args.save)
        print(f"已保存：{target}（{clip.duration:.2f}s，{profile.label}）")
    else:
        print(f"试听：{profile.label} / {profile.voice} / {clip.duration:.2f}s")
    play_clip(clip, args.device or config.preview_device, gain=config.gain)
    return 0


def _cmd_send(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    overrides: Dict[str, Any] = {}
    if args.no_switch:
        overrides["switch_default_input"] = False
    if args.no_restore:
        overrides["restore_default_input"] = False
    if args.no_focus:
        overrides["focus_input"] = False
    if args.max_chars:
        overrides["max_chars"] = args.max_chars
    if args.save_audio:
        overrides["save_audio"] = True
    config = config.with_overrides(**overrides)

    sender = VoiceSender(config)
    try:
        result = sender.send(
            args.text,
            chat=args.chat,
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch,
            volume=args.volume,
            trigger=args.trigger,
        )
    except WecVoiceError as exc:
        if args.json:
            _print_json({"ok": False, "error": str(exc)})
        else:
            print(f"发送失败：{exc}", file=sys.stderr)
        return 1
    if args.json:
        _print_json(result.to_dict())
    else:
        print(
            f"已发送：{result.chunks} 段，共 {result.total_seconds:.2f}s，"
            f"音色 {result.voice}"
            + (f"，会话 {result.chat}" if result.chat else "")
        )
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    path = Path(args.config) if args.config else default_config_path()
    config = Config.load(args.config)
    if args.set:
        for assignment in args.set:
            if "=" not in assignment:
                print(f"格式应为 key=value：{assignment}", file=sys.stderr)
                return 2
            key, raw = assignment.split("=", 1)
            key = key.strip()
            if key not in config.to_dict():
                print(f"未知配置项：{key}", file=sys.stderr)
                return 2
            current = config.to_dict()[key]
            value: Any = raw.strip()
            if isinstance(current, bool):
                value = value.lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                value = int(value)
            elif isinstance(current, float):
                value = float(value)
            elif current is None and value.lower() in ("none", "null", ""):
                value = None
            setattr(config, key, value)
        config.validate()
        saved = config.save(args.config)
        print(f"已保存：{saved}")
        return 0
    if args.show:
        print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"配置文件：{path}")
        print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wecvoice",
        description="用免费 Edge TTS + 微信原生语音键，发送真正的微信语音消息。",
    )
    parser.add_argument("--version", action="version", version=f"WecVoice-auto {__version__}")
    parser.add_argument("--config", help="配置文件路径（默认 %%APPDATA%%/WecVoice-auto/config.json）")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查音频、微信、TTS 环境")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)

    devices = subparsers.add_parser("devices", help="列出音频设备")
    devices.add_argument("--json", action="store_true")
    devices.set_defaults(func=_cmd_devices)

    voices = subparsers.add_parser("voices", help="列出内置音色或 Edge 在线音色")
    voices.add_argument("--online", action="store_true", help="从 Edge 拉取在线音色列表")
    voices.add_argument("--locale", default=None, help="按语言过滤，例如 zh、ja")
    voices.add_argument("--json", action="store_true")
    voices.set_defaults(func=_cmd_voices)

    say = subparsers.add_parser("say", help="只在本机试听，不发送到微信")
    say.add_argument("text")
    say.add_argument("--voice")
    say.add_argument("--rate")
    say.add_argument("--pitch")
    say.add_argument("--volume")
    say.add_argument("--device", help="播放设备（默认系统扬声器）")
    say.add_argument("--save", help="保存为 WAV 文件")
    say.set_defaults(func=_cmd_say)

    send = subparsers.add_parser("send", help="发送语音到当前打开的微信会话")
    send.add_argument("text")
    send.add_argument("--chat", help="目标会话名（用于校验；不会自动切换会话）")
    send.add_argument("--voice")
    send.add_argument("--rate")
    send.add_argument("--pitch")
    send.add_argument("--volume")
    send.add_argument("--trigger", choices=("alt", "button"), default=None)
    send.add_argument("--max-chars", type=int, default=None)
    send.add_argument("--no-switch", action="store_true", help="不自动切换默认录音设备")
    send.add_argument("--no-restore", action="store_true", help="发送后不恢复原默认录音设备")
    send.add_argument("--no-focus", action="store_true", help="不点击输入框")
    send.add_argument("--save-audio", action="store_true", help="保留生成的 WAV")
    send.add_argument("--json", action="store_true")
    send.set_defaults(func=_cmd_send)

    config = subparsers.add_parser("config", help="查看或修改配置")
    config.add_argument("--show", action="store_true")
    config.add_argument("--set", action="append", metavar="KEY=VALUE")
    config.set_defaults(func=_cmd_config)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130
    except WecVoiceError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2
