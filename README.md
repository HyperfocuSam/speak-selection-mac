# Speak Selection 🔊

Highlight text anywhere on macOS, press a hotkey (or right-click), and hear it read aloud
in a natural voice. Uses **ElevenLabs** as the primary voice and **MiniMax** as an automatic
fallback (MiniMax also handles Chinese / Cantonese well).

**Languages:** English · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md)

---

## What it does

- Read selected text aloud from any app with a Raycast hotkey or the right-click menu.
- Read the clipboard aloud (the reliable path inside terminals).
- Auto-detects language: English uses a clear English voice; Chinese / Cantonese text is
  spoken with a Cantonese-capable voice.
- Caches audio per text, so re-reading the same passage is instant and free.
- Stop playback any time with a second hotkey.

## Requirements

- macOS (uses the built-in `afplay`, `pbpaste`, `osascript`).
- Python 3 — the system one at `/usr/bin/python3` is enough. **No `pip install` needed.**
- At least one API key: ElevenLabs and/or MiniMax.
- Optional: [Raycast](https://raycast.com) for global hotkeys.

## Get an API key

You only need one of these (you can add both):

- **ElevenLabs** (primary voice): sign up at <https://elevenlabs.io>, then Profile → API key.
- **MiniMax** (fallback voice, strong Chinese/Cantonese): sign up at <https://www.minimax.io>
  and create an API key.

## Install

```bash
git clone https://github.com/HyperfocuSam/speak-selection-mac.git
cd speak-selection-mac
./install.sh
```

`install.sh` makes the scripts runnable, creates your `.env`, and installs the right-click
Quick Action. Then add your key(s):

```bash
open .env        # paste your ELEVENLABS_API_KEY and/or MINIMAX_API_KEY
```

### Add the Raycast hotkeys (optional but recommended)

1. Raycast → **Settings → Extensions → Script Commands → Add Script Directory**.
2. Choose the `raycast` folder inside this repo.
3. Three commands appear — assign each a hotkey:
   - **Speak Selection** (e.g. `⌥S`)
   - **Speak Clipboard** (e.g. `⌥C`)
   - **Stop Speaking** (e.g. `⌥.`)
4. On first use, macOS asks to grant **Raycast** Accessibility permission (needed so it can
   copy your selection). Approve it once in System Settings → Privacy & Security → Accessibility.

## Usage

**From any normal app (browser, Notes, Mail, etc.):**
Highlight text → press the **Speak Selection** hotkey → it reads aloud.
Or: highlight → right-click → **Services → Speak Selection**.

**Inside a terminal:**
Auto-capture is blocked by macOS in terminals, so copy the text yourself (**⌘C**), then press
the **Speak Clipboard** hotkey. This works everywhere and needs no permission.

**Stop:** press the **Stop Speaking** hotkey.

**Command line:**

```bash
python3 speak_selection.py "text to read"     # speak given text
python3 speak_selection.py --clipboard        # speak the clipboard (works in terminals)
echo "piped text" | python3 speak_selection.py
python3 speak_selection.py --stop             # stop playback
python3 speak_selection.py --provider minimax "hi"   # force a provider
python3 speak_selection.py --no-play "hi"            # synthesize only
```

## Configuration

Set these in `.env` (all optional except the keys):

| Variable | Default | Meaning |
|----------|---------|---------|
| `ELEVENLABS_API_KEY` | — | ElevenLabs key (primary voice) |
| `MINIMAX_API_KEY` | — | MiniMax key (fallback voice) |
| `SPEAK_EL_VOICE_ID` | `21m00Tcm4TlvDq8ikWAM` | ElevenLabs voice id |
| `SPEAK_EL_MODEL` | `eleven_flash_v2_5` | ElevenLabs model (flash = low latency) |
| `SPEAK_MM_MODEL` | `speech-2.8-hd` | MiniMax model |
| `SPEAK_SPEED` | `1.0` | Speech speed (0.5–2.0) |
| `SPEAK_CAPTURE_DELAY` | `0.2` | Pause before ⌘C on auto-capture |

## How it works

1. **Get text** from a CLI arg, the clipboard (`--clipboard`), stdin, or an auto ⌘C + `pbpaste`
   (with your clipboard restored afterward).
2. **Synthesize** — try ElevenLabs, then MiniMax. A 401 from a provider is cached so it is
   skipped until the key changes. Chinese/Cantonese text uses the right voice automatically.
3. **Play** with `afplay`. A new readout interrupts the previous one; `--stop` ends it.

Audio is cached in `~/Library/Caches/speak_selection/` (safe to delete anytime).

## Security — your keys stay private

- Keys live only in `.env`, which is in `.gitignore` and **never committed**.
- Only `.env.example` (placeholders, no real keys) is in the repo.
- The script reads keys from your local `.env` / environment at runtime — nothing is sent
  anywhere except the TTS provider you chose.

If you fork or publish your own copy, double-check `git status` does not list `.env` before
pushing.

## Troubleshooting

- **"Can't read the selection" / nothing happens in a terminal** — terminals block the
  synthetic ⌘C. Use **Speak Clipboard** (copy first, then trigger), or grant your terminal
  Accessibility permission.
- **No sound** — confirm a valid key is in `.env`; test with
  `python3 speak_selection.py "test"`.
- **ElevenLabs not used** — if its key returned 401 once, it is cached as bad. After fixing
  the key in `.env`, it re-activates automatically (or run
  `rm ~/Library/Caches/speak_selection/elevenlabs_failed_keyhash`).
- **Right-click item missing** — System Settings → Keyboard → Keyboard Shortcuts → Services →
  Text, tick **Speak Selection**.

## License

MIT — see [LICENSE](LICENSE).
