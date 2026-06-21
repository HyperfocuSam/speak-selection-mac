# Speak Selection 🔊（朗讀選取文字）

在 macOS 上選取任何文字，按一個快捷鍵（或右鍵），即可用自然的語音聽出來。主要語音使用
**ElevenLabs**，並以 **MiniMax** 作為自動後備（MiniMax 對中文／粵語的處理也很好）。

**語言：** [English](README.md) · 繁體中文 · [简体中文](README.zh-CN.md)

---

## 功能簡介

- 在任何應用程式中選取文字，用 Raycast 快捷鍵或右鍵選單朗讀出來。
- 直接朗讀剪貼簿內容（在終端機內最可靠的方式）。
- 自動辨識語言：英文用清晰的英文語音；中文／粵語則用支援粵語的語音朗讀。
- 按文字內容快取音訊，重複朗讀同一段文字即時完成、不再耗用額度。
- 隨時可用另一個快捷鍵停止播放。

## 系統需求

- macOS（使用內建的 `afplay`、`pbpaste`、`osascript`）。
- Python 3 — 用系統內建的 `/usr/bin/python3` 即可，**無需 `pip install`**。
- 至少一個 API 金鑰：ElevenLabs 或 MiniMax（兩個都加也可以）。
- 選用：[Raycast](https://raycast.com)，用來設定全域快捷鍵。

## 取得 API 金鑰

以下兩者擇其一即可（也可兩個都加）：

- **ElevenLabs**（主要語音）：到 <https://elevenlabs.io> 註冊，然後在 Profile → API key 取得。
- **MiniMax**（後備語音，中文／粵語表現佳）：到 <https://www.minimax.io> 註冊並建立 API 金鑰。

## 安裝

```bash
git clone https://github.com/HyperfocuSam/speak-selection-mac.git
cd speak-selection-mac
./install.sh
```

`install.sh` 會把指令稿設為可執行、建立你的 `.env`，並安裝右鍵的 Quick Action。
之後加入你的金鑰：

```bash
open .env        # 貼上 ELEVENLABS_API_KEY 或 MINIMAX_API_KEY
```

### 設定 Raycast 快捷鍵（選用，但建議）

1. Raycast → **Settings → Extensions → Script Commands → Add Script Directory**。
2. 選擇本專案內的 `raycast` 資料夾。
3. 會出現三個指令，分別指派快捷鍵：
   - **Speak Selection**（例如 `⌥S`）
   - **Speak Clipboard**（例如 `⌥C`）
   - **Stop Speaking**（例如 `⌥.`）
4. 首次使用時，macOS 會要求授予 **Raycast** 輔助使用（Accessibility）權限（這樣它才能複製
   你選取的文字）。到「系統設定 → 私隱與安全性 → 輔助使用」批准一次即可。

## 使用方法

**在一般應用程式中（瀏覽器、備忘錄、郵件等）：**
選取文字 → 按 **Speak Selection** 快捷鍵 → 即開始朗讀。
或：選取文字 → 右鍵 → **服務（Services）→ Speak Selection**。

**在終端機內：**
macOS 在終端機中會阻擋自動複製，所以請自己按 **⌘C** 複製文字，再按 **Speak Clipboard**
快捷鍵。這個方式在任何地方都有效，而且不需要任何權限。

**停止：** 按 **Stop Speaking** 快捷鍵。

**命令列：**

```bash
python3 speak_selection.py "要朗讀的文字"      # 朗讀指定文字
python3 speak_selection.py --clipboard         # 朗讀剪貼簿（終端機適用）
echo "管道輸入的文字" | python3 speak_selection.py
python3 speak_selection.py --stop              # 停止播放
python3 speak_selection.py --provider minimax "hi"   # 指定使用某個供應商
python3 speak_selection.py --no-play "hi"            # 只生成、不播放
```

## 設定項目

在 `.env` 中設定（除了金鑰外其餘皆為選用）：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ELEVENLABS_API_KEY` | — | ElevenLabs 金鑰（主要語音） |
| `MINIMAX_API_KEY` | — | MiniMax 金鑰（後備語音） |
| `SPEAK_EL_VOICE_ID` | `21m00Tcm4TlvDq8ikWAM` | ElevenLabs 語音 id |
| `SPEAK_EL_MODEL` | `eleven_flash_v2_5` | ElevenLabs 模型（flash＝低延遲） |
| `SPEAK_MM_MODEL` | `speech-2.8-hd` | MiniMax 模型 |
| `SPEAK_SPEED` | `1.0` | 語速（0.5–2.0） |
| `SPEAK_CAPTURE_DELAY` | `0.2` | 自動複製前的延遲（秒） |

## 運作原理

1. **取得文字**：來自命令列參數、剪貼簿（`--clipboard`）、stdin，或自動 ⌘C ＋ `pbpaste`
   （事後會還原你原本的剪貼簿內容）。
2. **生成語音**：先試 ElevenLabs，再試 MiniMax。某供應商回傳 401 會被記住並跳過，直到金鑰
   更換為止。中文／粵語文字會自動使用合適的語音。
3. **播放**：用 `afplay`。新的朗讀會中斷前一段；`--stop` 可結束播放。

音訊快取放在 `~/Library/Caches/speak_selection/`（隨時可刪除）。

## 安全性 — 你的金鑰不會外洩

- 金鑰只存在於 `.env`，而 `.env` 已列入 `.gitignore`，**永遠不會被提交（commit）**。
- 專案中只有 `.env.example`（佔位字串，沒有真實金鑰）。
- 指令稿只在執行時從你本機的 `.env`／環境變數讀取金鑰 — 除了你選擇的 TTS 供應商之外，
  不會把資料送到任何地方。

如果你 fork 或自行發佈副本，推送前請再次確認 `git status` 沒有列出 `.env`。

## 疑難排解

- **「Can't read the selection」／在終端機沒反應** — 終端機會阻擋自動 ⌘C。請改用
  **Speak Clipboard**（先複製，再觸發），或為你的終端機授予輔助使用權限。
- **沒有聲音** — 確認 `.env` 中有有效金鑰；用 `python3 speak_selection.py "test"` 測試。
- **沒有使用 ElevenLabs** — 如果其金鑰曾回傳 401，會被記為失效。在 `.env` 更新金鑰後會自動
  重新啟用（或執行 `rm ~/Library/Caches/speak_selection/elevenlabs_failed_keyhash`）。
- **右鍵選單沒有該項目** — 系統設定 → 鍵盤 → 鍵盤快捷鍵 → 服務 → 文字，勾選
  **Speak Selection**。

## 授權

MIT — 詳見 [LICENSE](LICENSE)。
