# Changelog

All notable changes to this project are documented here.  The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.0.2] - 2026-10-31

### Fixed

- Hold the **right Alt** (`VK_RMENU` + `KEYEVENTF_EXTENDEDKEY`) instead of the
  left Alt. WeChat 4.2 only recognises the right Alt for hold-to-talk.
- Use `SendInput` with the complete `INPUT` union (40 bytes on 64-bit Windows).
  The previous 32-byte structure made Windows reject every synthetic key, so
  WeChat never entered recording mode and no voice bubble appeared.
- Verify that WeChat is the foreground window right before pressing Alt; abort
  with a clear error instead of sending the keystroke to another window.
- Added a regression test for the right-Alt scancode/extended flags.

## [0.0.1] - 2026-10-31

### Changed

- All runtime output is now English: CLI help and messages, the `doctor`
  report, error messages, log lines, and built-in voice labels/descriptions.
  Chinese is kept only where it is functional (WeChat window/chat matching)
  or supplied by the user (chat names, message text).

## [0.0.0] - 2026-10-31

First public preview.

### Added

- Send real WeChat voice bubbles on Windows 10/11 with WeChat 4.1.9+ by
  holding the native Alt voice shortcut while TTS audio plays into a virtual
  audio cable.
- Free Edge TTS synthesis (no API key), decoded to 48 kHz mono PCM with
  `miniaudio`.
- 12 built-in voice presets, including the default `arona` approximation
  (晓伊 + pitch/rate tuning), plus arbitrary Edge voice names and per-call
  rate/pitch/volume overrides.
- Automatic Windows default-recording-device switching through
  `IPolicyConfig`, with restore-after-send.
- Sentence-aware text cleanup and splitting, sticker/URL stripping, and a
  60-second guard.
- `wecvoice` CLI: `doctor`, `devices`, `voices`, `say`, `send`, `config`.
- Preview mode that only plays audio locally.
- Injectable TTS, player, window and routing objects for tests and bot
  integration.
- Environment doctor covering audio endpoints, default microphone, WeChat
  window/version and microphone privacy consent.
- Unit tests for text, voices, config, audio helpers, TTS decoding, sender
  ordering and CLI.
