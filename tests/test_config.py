from __future__ import annotations

import json

import pytest

from wecvoice_auto.config import Config


def test_defaults():
    config = Config()
    assert config.voice == "arona"
    assert config.output_device == "CABLE Input"
    assert config.input_device == "CABLE Output"
    assert config.switch_default_input is True
    assert config.trigger == "alt"


def test_validate_rejects_bad_trigger():
    with pytest.raises(ValueError):
        Config(trigger="mouse")


def test_validate_rejects_bad_seconds():
    with pytest.raises(ValueError):
        Config(max_seconds=80)


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(voice="plana", max_chars=60, gain=0.8)
    saved = config.save(path)
    assert saved == path
    loaded = Config.load(path)
    assert loaded.voice == "plana"
    assert loaded.max_chars == 60
    assert abs(loaded.gain - 0.8) < 1e-9


def test_unknown_key_is_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"voice": "yunxi", "nonsense": 1}), encoding="utf-8")
    config = Config.load(path)
    assert config.voice == "yunxi"
    assert getattr(config, "_unknown_keys") == ["nonsense"]


def test_with_overrides():
    config = Config().with_overrides(voice="xiaoyi", max_chars=80, rate=None)
    assert config.voice == "xiaoyi"
    assert config.max_chars == 80
    assert config.rate is None


def test_load_missing_file_returns_defaults(tmp_path):
    assert Config.load(tmp_path / "missing.json").voice == "arona"
