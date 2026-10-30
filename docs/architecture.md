# 架构与实现细节

## 1. 为什么是“虚拟声卡 + Alt”

微信 4.1.9 起，Windows 版可以在聊天框的发送按钮旁按住语音键，或**按住右侧 `Alt`（AltGr）**说话，松开后发送，最长 60 秒。
微信 4.2 明确只响应**右侧 Alt**，左侧 Alt 无效。
这意味着只要让微信“听到”我们想说的内容，微信自己就会完成 SILK 编码、上传和气泡渲染，不需要协议层。

Windows 没有“给某个应用单独指定麦克风”的公开能力（只有输出端的 per-app 路由），所以必须把**系统默认录音设备**临时切到虚拟声卡的录音端。

```
 ┌────────────┐   PCM 48k   ┌──────────────────┐
 │ Edge TTS   │────────────►│ CABLE Input      │  (render)
 └────────────┘             └────────┬─────────┘
                                     │ VB-CABLE 内部回环
                            ┌────────▼─────────┐
                            │ CABLE Output     │  (capture)
                            └────────┬─────────┘
                                     │ default mic
 ┌────────────┐   Alt down  ┌────────▼─────────┐   Alt up   ┌──────────┐
 │ WecVoice   │────────────►│ WeChat recorder  │───────────►│ 语音气泡 │
 └────────────┘             └──────────────────┘            └──────────┘
```

## 2. 一次发送的时序

```
t=0.00  SetForegroundWindow(wechat)
t=0.05  click chat input (UIA, fallback: coordinates)
t=0.20  ensure chat name == target (UIA)
t=0.25  set default capture = CABLE Output
t=0.60  keybd_event(Alt down)
t=0.95  sd.play(clip)            # lead_seconds = 0.35
t=0.95+d  playback finished
t=1.25+d  keybd_event(Alt up)    # tail_seconds = 0.30
t=1.25+d+settle  restore default capture
```

`lead_seconds` 是给微信打开录音器的时间。太短会吃掉第一个字；太长会让气泡比音频长。
`tail_seconds` 是给录音缓冲的时间。太短会吃掉最后一个字。

气泡时长 ≈ `lead + audio + tail`，比音频本身长约 0.65 秒，这是正常的。

## 3. 关键模块

### `tts.py`

- `edge_tts.Communicate(...).stream()` 直接拿 MP3 字节，不落临时文件。
- `miniaudio.decode(..., nchannels=1, sample_rate=48000)` 解码并重采样。
- 静音修剪保留 80ms 自然垫音，避免“突然开始/突然结束”。
- 同步 API 内部用 `asyncio.run`；如果调用方已有事件循环，则把协程丢到子线程运行。

### `audio.py`

- 用 `sounddevice`（PortAudio）枚举和播放。
- 设备名子串匹配，优先“完全相等 → 前缀 → 包含”。
- 设备不接受 48k 时线性重采样到设备默认采样率。
- 单声道自动复制成立体声，兼容只接受 2 声道的端点。

### `devices.py`

- `pycaw` 枚举 Windows 音频端点、读取默认麦克风。
- `AudioUtilities.SetDefaultDevice` 调用未公开的 PolicyConfig COM（CLSID
  `{870af99c-...}`），对 `eConsole` / `eMultimedia` / `eCommunications`
  三个角色都设置默认设备；旧版 pycaw 缺少该 helper 时退回直接调用
  `IPolicyConfig.SetDefaultEndpoint`。
- 这是声音控制面板使用的同一套未公开接口，Win10/11 稳定，但不是微软文档化 API。

### `wechat.py`

- 先用 `EnumWindows` + 类名/标题找主窗口（`mmui::MainWindow`，兼容
  `Qt*` 壳窗口），不依赖 UIA 是否已“热激活”。
- UIA 只用于三件可选的事：读当前会话名、聚焦输入框、找语音按钮。
- 冷启动的微信 4.x 可能只暴露 `Qt51514QWindowIcon` 空壳（Qt accessibility
  gate 未打开），此时：
  - 会话校验被跳过并打 warning；
  - 输入框聚焦退回坐标点击（`click_input_fallback`）；
  - `trigger="alt"` 仍然可用，因为 Alt 是窗口级快捷键。
- 不做内存补丁、不写微信数据库。

### `input.py`

- `keybd_event(VK_RMENU, 0x38, KEYEVENTF_EXTENDEDKEY)` 产生右侧 Alt 的
  `WM_SYSKEYDOWN/UP`，与真人按右 Alt 一致；微信 4.2 只认右 Alt。
- `HoldToTalk` 是上下文管理器，`__exit__` 一定释放按键/鼠标，异常也不会卡住 Alt。
- `release_all()` 作为进程级兜底。

## 4. 为什么不用别的方案

| 方案 | 不采用的原因 |
|---|---|
| 发送 `.silk` 文件 | 对方看到的是文件卡片，不是语音气泡 |
| 协议 Hook（WeChatFerry） | 需要降级微信 3.9.x + 注入 DLL，封号风险高 |
| 手机/模拟器自动化 | 需要第二台设备，工程量大，账号多端冲突 |
| 微信数据库写入 | 4.x 加密库，写入不同步到服务器，且极易损坏 |
| 截图/OCR 找按钮 | 违反“不截屏”的隐私边界，且不稳定 |

## 5. 已知风险

1. **微信改版**：语音按钮或 Alt 行为变化会破坏发送；`wecvoice doctor` 和
   `trigger="button"` 是排查入口。
2. **音频设备缓存**：微信可能在启动时缓存录音设备；如果切换后仍录到真实
   麦克风，重启微信。
3. **驱动安装**：VB-CABLE 需要管理员权限和重启；本库不会自动安装驱动。
4. **并发**：同一时刻只能有一个发送流程；多线程调用需要调用方加锁。
5. **账号风险**：任何 UI 自动化都可能触发风控；控制频率，不要群发。

## 6. 测试策略

- 纯函数（文本清理/切分、音色参数、配置、重采样、静音修剪）直接单测。
- 发送编排用 fake TTS / fake window / fake routing / fake player，验证
  “先开录音再播放、播完再松开、异常也恢复设备”的顺序，不碰真实微信。
- 真实端到端需要 VB-CABLE + 登录的微信，属于手动验收，不在 CI 中运行。
