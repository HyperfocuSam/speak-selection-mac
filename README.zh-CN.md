# Speak Selection 🔊（朗读选中文字）

在 macOS 上选中任意文字，按一个快捷键（或右键），即可用自然的语音听出来。主要语音使用
**ElevenLabs**，并以 **MiniMax** 作为自动后备（MiniMax 对中文／粤语的处理也很好）。

**语言：** [English](README.md) · [繁體中文](README.zh-TW.md) · 简体中文

---

## 功能简介

- 在任意应用中选中文字，用 Raycast 快捷键或右键菜单朗读出来。
- 直接朗读剪贴板内容（在终端里最可靠的方式）。
- 自动识别语言：英文用清晰的英文语音；中文／粤语则用支持粤语的语音朗读。
- 按文字内容缓存音频，重复朗读同一段文字时即时完成、不再消耗额度。
- 随时可用另一个快捷键停止播放。
- **根据任务选择语音**：在光标处弹出的菜单中选择声音：主音、助手以及悬停组（内容朗读、教练、思想库、备份）。最后一次选择将用于普通快捷键。该菜单是一个可以编辑的 `voices.json` 文件。
- **流式传输**：支持 ElevenLabs 音频流式播放（需安装 `ffplay`），即使是长篇文章也能在约一秒内开始朗读。

## 系统要求

- macOS（使用内置的 `afplay`、`pbpaste`、`osascript`）。
- Python 3 — 用系统自带的 `/usr/bin/python3` 即可，**无需 `pip install`**。
- 至少一个 API 密钥：ElevenLabs 或 MiniMax（两个都加也可以）。
- 可选：[Raycast](https://raycast.com)，用于设置全局快捷键。
- 可选：`ffmpeg` (`brew install ffmpeg`) 用于流式播放。
- 可选：Xcode Command Line Tools (`xcode-select --install`)，以便 `install.sh` 可以构建原生语音菜单。如果没有它们，选择器将显示为普通的列表对话框。

## 获取 API 密钥

以下两者择其一即可（也可两个都加）：

- **ElevenLabs**（主要语音）：到 <https://elevenlabs.io> 注册，然后在 Profile → API key 获取。
- **MiniMax**（后备语音，中文／粤语表现好）：到 <https://www.minimax.io> 注册并创建 API 密钥。

## 安装

```bash
git clone https://github.com/HyperfocuSam/speak-selection-mac.git
cd speak-selection-mac
./install.sh
```

`install.sh` 会把脚本设为可执行、创建你的 `.env`，并安装右键的 Quick Action。
之后填入你的密钥：

```bash
open .env        # 粘贴 ELEVENLABS_API_KEY 或 MINIMAX_API_KEY
```

### 设置 Raycast 快捷键（可选，但推荐）

1. Raycast → **Settings → Extensions → Script Commands → Add Script Directory**。
2. 选择本项目内的 `raycast` 文件夹。
3. 会出现命令，分别指派快捷键：
   - **Speak Selection**（例如 `⌥S`）
   - **Speak Clipboard**（例如 `⌥C`）
   - **Speak Selection (Pick Voice)**（例如 `⌘⌥C`）—— 先弹出语音菜单，然后朗读
   - **Speak Clipboard (Pick Voice)**（可选）
   - **Stop Speaking**（例如 `⌥.`）
4. 首次使用时，macOS 会要求授予 **Raycast** 辅助功能（Accessibility）权限（这样它才能复制
   你选中的文字）。到「系统设置 → 隐私与安全性 → 辅助功能」批准一次即可。

## 使用方法

**在普通应用中（浏览器、备忘录、邮件等）：**
选中文字 → 按 **Speak Selection** 快捷键 → 即开始朗读。
或：选中文字 → 右键 → **服务（Services）→ Speak Selection**。

**在终端中：**
macOS 在终端里会拦截自动复制，所以请自己按 **⌘C** 复制文字，再按 **Speak Clipboard**
快捷键。这种方式在任何地方都有效，而且不需要任何权限。

**选择语音：** 按 **Pick Voice** 快捷键。在光标处会弹出一个菜单；悬停在组上查看其语音，点击其中一个即可朗读。该语音将作为普通快捷键的默认值，直到你选择另一个为止。

**停止：** 按 **Stop Speaking** 快捷键。

**命令行：**

```bash
python3 speak_selection.py "要朗读的文字"      # 朗读指定文字
python3 speak_selection.py --clipboard         # 朗读剪贴板（终端适用）
echo "管道输入的文字" | python3 speak_selection.py
python3 speak_selection.py --stop              # 停止播放
python3 speak_selection.py --provider minimax "hi"   # 指定使用某个供应商
python3 speak_selection.py --no-play "hi"            # 只生成、不播放
python3 speak_selection.py --pick                    # 语音菜单，然后朗读选择内容
python3 speak_selection.py --voice zara "hi"         # 使用指定 key 的语音
python3 speak_selection.py --list-voices             # 列出语音 key
```

## 配置项

在 `.env` 中设置（除密钥外其余均为可选）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ELEVENLABS_API_KEY` | — | ElevenLabs 密钥（主要语音） |
| `MINIMAX_API_KEY` | — | MiniMax 密钥（后备语音） |
| `SPEAK_EL_VOICE_ID` | — | 可选的额外语音 ID；作为“Custom voice”添加到菜单并作为默认值使用 |
| `SPEAK_EL_MODEL` | `eleven_v4` | ElevenLabs 模型（多语言，表现力最强；`eleven_flash_v2_5` 为最低延迟） |
| `SPEAK_MM_MODEL` | `speech-2.8-hd` | MiniMax 模型 |
| `SPEAK_SPEED` | `1.0` | 语速（0.5–2.0） |
| `SPEAK_CAPTURE_DELAY` | `0.6` | 自动复制前的延迟（秒，需长于热键修饰键的释放时间，例如 ⌥S 的 ⌥，否则会变成 ⌘⌥C 而复制不到内容） |

### 你自己的语音菜单 — `voices.json`

每个顶级条目要么是一个语音，要么是一个悬停组：

```json
{
  "default": "ada",
  "menu": [
    {"key": "ada", "id": "oW8bn5YtBB89X2nJ0DT9", "label": "Main COS - Ada (F)"},
    {"group": "Coach", "items": [
      {"key": "samara", "id": "19STyYD15bswVz51nqLf", "label": "Mental Support - (F)"}
    ]}
  ]
}
```

`id` 是任何 ElevenLabs 语音 ID，包括来自公共 Voice Library 的语音（从语音页面复制 ID）。通过 API 使用 Voice Library 语音可能需要付费的 ElevenLabs 套餐。内置菜单根据任务对语音进行命名（main, assistants, finance, coaches, strategist, negotiator, readers）；你可以根据需要重新命名它们。

## 工作原理

1. **获取文字**：来自命令行参数、剪贴板（`--clipboard`）、stdin，或自动 ⌘C ＋ `pbpaste`
   （事后会还原你原本的剪贴板内容）。
2. **生成语音**：先试 ElevenLabs，再试 MiniMax。某供应商返回 401 会被记住并跳过，直到密钥
   更换为止。中文／粤语文字会自动使用合适的语音。
3. **播放**：如果可用，则通过 `ffplay` 流式传输并下载；否则在准备好后使用 `afplay` 播放。新的朗读会打断上一段；`--stop` 可结束播放。

音频缓存放在 `~/Library/Caches/speak_selection/`（随时可删除）。

## 安全性 — 你的密钥不会外泄

- 密钥只存在于 `.env`，而 `.env` 已列入 `.gitignore`，**永远不会被提交（commit）**。
- 项目中只有 `.env.example`（占位字符串，没有真实密钥）。
- 脚本只在运行时从你本机的 `.env`／环境变量读取密钥 — 除了你选择的 TTS 供应商之外，
  不会把数据发送到任何地方。

如果你 fork 或自行发布副本，推送前请再次确认 `git status` 没有列出 `.env`。

## 故障排查

- **「Can't read the selection」／在终端没反应** — 终端会拦截自动 ⌘C。请改用
  **Speak Clipboard**（先复制，再触发），或为你的终端授予辅助功能权限。
- **没有声音** — 确认 `.env` 中有有效密钥；用 `python3 speak_selection.py "test"` 测试。
- **没有使用 ElevenLabs** — 如果其密钥曾返回 401，会被记为失效。在 `.env` 更新密钥后会自动
  重新启用（或执行 `rm ~/Library/Caches/speak_selection/elevenlabs_failed_keyhash`）。
- **右键菜单没有该项** — 系统设置 → 键盘 → 键盘快捷键 → 服务 → 文本，勾选
  **Speak Selection**。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。
