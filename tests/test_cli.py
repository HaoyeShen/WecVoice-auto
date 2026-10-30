from __future__ import annotations

import json

from wecvoice_auto.cli import build_parser, main
from wecvoice_auto.wechat import _same_chat, clean_chat_name


def test_parser_accepts_send_options():
    parser = build_parser()
    args = parser.parse_args(["send", "你好", "--chat", "文件传输助手", "--voice", "arona"])
    assert args.command == "send"
    assert args.chat == "文件传输助手"


def test_voices_command(capsys):
    assert main(["voices"]) == 0
    out = capsys.readouterr().out
    assert "arona" in out
    assert "zh-CN-XiaoyiNeural" in out


def test_config_set_and_show(tmp_path, capsys):
    path = tmp_path / "config.json"
    assert main(["--config", str(path), "config", "--set", "voice=plana"]) == 0
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["voice"] == "plana"
    assert main(["--config", str(path), "config", "--show"]) == 0
    out = capsys.readouterr().out
    assert '"voice": "plana"' in out


def test_clean_chat_name_strips_placeholder():
    assert clean_chat_name("文件传输助手按住鼠标 语音输入文字") == "文件传输助手"
    assert clean_chat_name("群聊（3）长按鼠标 语音输入") == "群聊（3）"


def test_same_chat_aliases():
    assert _same_chat("文件传输助手", "File Transfer")
    assert _same_chat("阿洛娜", "阿洛娜")
    assert not _same_chat("阿洛娜", "老师")
