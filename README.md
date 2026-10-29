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
- **Pick a voice per job** from a pop-up menu at your pointer: a main voice, assistants,
  and hover groups (Content Readout, Coach, Think Tank, Backups). Your last pick is
  remembered for the plain hotkeys. The menu is a plain `voices.json` you can edit.
- **Streams** ElevenLabs audio (when `ffplay` is installed), so even a long article starts
  speaking in about a second.

## Requirements

- macOS (uses the built-in `afplay`, `pbpaste`, `osascript`).
- Python 3 — the system one at `/usr/bin/python3` is enough. **No `pip install` needed.**
- At least one API key: ElevenLabs and/or MiniMax.
- Optional: [Raycast](https://raycast.com) for global hotkeys.
- Optional: `ffmpeg` (`brew install ffmpeg`) for streaming playback.
- Optional: Xcode Command Line Tools (`xcode-select --install`) so `install.sh` can build the
  native voice menu. Without them the picker is a plain list dialog.

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
3. The commands appear — assign each a hotkey:
   - **Speak Selection** (e.g. `⌥S`)
   - **Speak Clipboard** (e.g. `⌥C`)
   - **Speak Selection (Pick Voice)** (e.g. `⌘⌥C`) — voice menu first, then reads
   - **Speak Clipboard (Pick Voice)** (optional)
   - **Stop Speaking** (e.g. `⌥.`)
4. On first use, macOS asks to grant **Raycast** Accessibility permission (needed so it can
   copy your selection). Approve it once in System Settings → Privacy & Security → Accessibility.

> **Most reliable selection capture — use the Quick Action.** The Raycast **Speak Selection**
> hotkey works by synthesizing ⌘C, which some apps (and some launch contexts) silently ignore —
> you get "Nothing to read" even with text selected, and Accessibility being granted does **not**
> fix it. The robust path reads your selection directly through macOS Services: **System Settings
> → Keyboard → Keyboard Shortcuts → Services → Text**, tick **Speak Selection**, and assign it a
> key (e.g. ⌥S). No synthetic copy, no Accessibility needed. Keep **Speak Clipboard** on Raycast
> (⌥C) — it reads the clipboard directly and is rock-solid. You can always fall back to
> **⌘C → Speak Clipboard**.

## Usage

**From any normal app (browser, Notes, Mail, etc.):**
Highlight text → press the **Speak Selection** hotkey → it reads aloud.
Or: highlight → right-click → **Services → Speak Selection**.

**Inside a terminal:**
Auto-capture is blocked by macOS in terminals, so copy the text yourself (**⌘C**), then press
the **Speak Clipboard** hotkey. This works everywhere and needs no permission.

**Choose a voice:** press the **Pick Voice** hotkey. A menu opens at your pointer; hover a
group to see its voices, click one, and it reads. That voice stays the default for the
plain hotkeys until you pick another.

**Stop:** press the **Stop Speaking** hotkey.

**Command line:**

```bash
python3 speak_selection.py "text to read"     # speak given text
python3 speak_selection.py --clipboard        # speak the clipboard (works in terminals)
echo "piped text" | python3 speak_selection.py
python3 speak_selection.py --stop             # stop playback
python3 speak_selection.py --provider minimax "hi"   # force a provider
python3 speak_selection.py --no-play "hi"            # synthesize only
python3 speak_selection.py --pick                    # voice menu, then read the selection
python3 speak_selection.py --voice zara "hi"         # use a voice by its key
python3 speak_selection.py --list-voices             # list voice keys
```

## Configuration

Set these in `.env` (all optional except the keys):

| Variable | Default | Meaning |
|----------|---------|---------|
| `ELEVENLABS_API_KEY` | — | ElevenLabs key (primary voice) |
| `MINIMAX_API_KEY` | — | MiniMax key (fallback voice) |
| `SPEAK_EL_VOICE_ID` | — | Optional extra voice id; added to the menu as "Custom voice" and used as the default |
| `SPEAK_EL_MODEL` | `eleven_v4` | ElevenLabs model (multilingual, most expressive; `eleven_flash_v2_5` = lowest latency) |
| `SPEAK_MM_MODEL` | `speech-2.8-hd` | MiniMax model |
| `SPEAK_SPEED` | `1.0` | Speech speed (0.5–2.0) |
| `SPEAK_CAPTURE_DELAY` | `0.6` | Pause before ⌘C on auto-capture (must outlast your hotkey's own modifier release, e.g. the ⌥ of ⌥S) |

### Your own voice menu — `voices.json`

Each top-level entry is either one voice or a hover group:

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

`id` is any ElevenLabs voice id, including voices from the public Voice Library (copy the
id from the voice's page). Using Voice Library voices through the API may need a paid
ElevenLabs plan. The shipped menu names voices by the job they do (main, assistants,
finance, coaches, strategist, negotiator, readers); rename them to suit you.

## How it works

1. **Get text** from a CLI arg, the clipboard (`--clipboard`), stdin, or an auto ⌘C + `pbpaste`
   (with your clipboard restored afterward).
2. **Synthesize** — try ElevenLabs, then MiniMax. A 401 from a provider is cached so it is
   skipped until the key changes. Chinese/Cantonese text uses the right voice automatically.
3. **Play** — streamed through `ffplay` while it downloads when available, otherwise with
   `afplay` once ready. A new readout interrupts the previous one; `--stop` ends it.

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
- **"Nothing to read" even though text is selected** — the synthetic ⌘C didn't land in the
  app (common when triggered from Raycast; Accessibility being on does not guarantee it).
  Either raise `SPEAK_CAPTURE_DELAY`, or — most reliable — assign a shortcut to the **Speak
  Selection** Quick Action (System Settings → Keyboard → Keyboard Shortcuts → Services → Text),
  which reads the selection directly with no synthetic copy. Or just ⌘C then **Speak Clipboard**.
- **No sound** — confirm a valid key is in `.env`; test with
  `python3 speak_selection.py "test"`.
- **ElevenLabs not used** — if its key returned 401 once, it is cached as bad. After fixing
  the key in `.env`, it re-activates automatically (or run
  `rm ~/Library/Caches/speak_selection/elevenlabs_failed_keyhash`).
- **Right-click item missing** — System Settings → Keyboard → Keyboard Shortcuts → Services →
  Text, tick **Speak Selection**.

## License

MIT — see [LICENSE](LICENSE).
