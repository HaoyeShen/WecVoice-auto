"""Environment diagnostics for ``wecvoice doctor``."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from typing import List, Optional

from .audio import default_input, find_device, list_devices
from .config import Config
from .devices import check_microphone_permission, get_default_capture
from .wechat import WeChatWindow


@dataclass
class Check:
    level: str  # "ok" | "warn" | "fail"
    title: str
    detail: str = ""

    @property
    def icon(self) -> str:
        return {"ok": "[OK]", "warn": "[!]", "fail": "[X]"}.get(self.level, "[?]")


def _wechat_version() -> str:
    try:
        import winreg
    except ImportError:
        return ""
    candidates = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in candidates:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        try:
            for index in range(winreg.QueryInfoKey(root)[0]):
                try:
                    sub_name = winreg.EnumKey(root, index)
                    sub = winreg.OpenKey(root, sub_name)
                    try:
                        name, _ = winreg.QueryValueEx(sub, "DisplayName")
                    except OSError:
                        continue
                    if "微信" in str(name) or "WeChat" in str(name):
                        try:
                            version, _ = winreg.QueryValueEx(sub, "DisplayVersion")
                            return str(version)
                        except OSError:
                            return "已安装"
                except OSError:
                    continue
        finally:
            try:
                winreg.CloseKey(root)
            except OSError:
                pass
    return ""


def run_checks(config: Optional[Config] = None) -> List[Check]:
    cfg = config or Config.load()
    checks: List[Check] = []

    checks.append(Check("ok", "Python", f"{sys.version.split()[0]} ({platform.architecture()[0]})"))
    if sys.platform != "win32":
        checks.append(Check("fail", "操作系统", "本库只支持 Windows 10/11"))
    else:
        checks.append(Check("ok", "操作系统", f"{platform.system()} {platform.release()}"))

    try:
        import edge_tts  # noqa: F401
        checks.append(Check("ok", "Edge TTS", "已安装（免费，需要联网）"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("fail", "Edge TTS", f"未安装：{exc}"))

    try:
        devices = list_devices()
        outputs = [d for d in devices if d.kind == "output"]
        inputs = [d for d in devices if d.kind == "input"]
        checks.append(Check("ok", "音频设备", f"{len(outputs)} 个播放 / {len(inputs)} 个录音"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("fail", "音频设备", str(exc)))

    try:
        output = find_device(cfg.output_device, "output")
        checks.append(Check("ok", "虚拟播放端", f"[{output.index}] {output.name}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check(
            "fail", "虚拟播放端",
            f"{cfg.output_device!r} 不存在：{exc}\n"
            "请安装 VB-Audio Virtual Cable：https://vb-audio.com/Cable/（安装后重启）",
        ))

    try:
        capture = find_device(cfg.input_device, "input")
        checks.append(Check("ok", "虚拟录音端", f"[{capture.index}] {capture.name}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check(
            "fail", "虚拟录音端",
            f"{cfg.input_device!r} 不存在：{exc}\n"
            "VB-CABLE 安装包会同时创建 CABLE Input 和 CABLE Output。",
        ))

    try:
        current = default_input()
        name = current.name if current else "（未知）"
        if cfg.input_device.lower() in name.lower():
            checks.append(Check("ok", "默认录音设备", name))
        elif cfg.switch_default_input:
            checks.append(Check(
                "warn", "默认录音设备",
                f"当前是 {name!r}；发送时会自动切到 {cfg.input_device!r}。"
                "如果微信录到静音，请把 CABLE Output 设为默认后重启微信。",
            ))
        else:
            checks.append(Check(
                "fail", "默认录音设备",
                f"当前是 {name!r}，但 switch_default_input=False，微信会录到真实麦克风。",
            ))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("warn", "默认录音设备", str(exc)))

    try:
        current_capture = get_default_capture()
        if current_capture:
            checks.append(Check("ok", "Windows 默认麦克风", current_capture.name))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("warn", "Windows 默认麦克风", f"读取失败：{exc}"))

    allowed, detail = check_microphone_permission()
    if allowed is False:
        checks.append(Check(
            "fail", "微信麦克风权限",
            f"{detail}；请在 Windows 设置 → 隐私 → 麦克风 中允许桌面应用访问。",
        ))
    elif allowed is True:
        checks.append(Check("ok", "微信麦克风权限", detail))
    else:
        checks.append(Check("warn", "微信麦克风权限", detail))

    try:
        window = WeChatWindow()
        if window.find():
            checks.append(Check("ok", "微信窗口", f"{window.title!r}，句柄 {window.hwnd}"))
        else:
            checks.append(Check(
                "fail", "微信窗口",
                "没有找到微信主窗口；请登录微信 4.1.9+ 并打开主界面。",
            ))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("warn", "微信窗口", str(exc)))

    version = _wechat_version()
    if version:
        checks.append(Check("ok", "微信版本", version))
    else:
        checks.append(Check("warn", "微信版本", "未从注册表读到版本；需要 4.1.9 及以上（原生发语音）"))

    if cfg.trigger == "alt":
        checks.append(Check("ok", "触发方式", "按住 Alt 说话（推荐）"))
    else:
        checks.append(Check("warn", "触发方式", "按住界面语音按钮（依赖 UIA 控件树）"))

    return checks


def format_report(checks: List[Check]) -> str:
    lines = ["WecVoice-auto 环境诊断", "=" * 24]
    for check in checks:
        lines.append(f"{check.icon} {check.title}：{check.detail}")
    failures = sum(1 for item in checks if item.level == "fail")
    warnings = sum(1 for item in checks if item.level == "warn")
    lines.append("-" * 24)
    lines.append(f"结果：{len(checks)} 项检查，{failures} 个失败，{warnings} 个提醒")
    return "\n".join(lines)
