#!/usr/bin/env python3
"""Speak the highlighted / selected (or copied) text aloud on macOS.

Pipeline:  get text -> TTS (ElevenLabs v4 primary, MiniMax fallback) -> play.

Zero dependencies: uses only the Python standard library + macOS built-ins
(afplay, pbpaste, osascript). Works on the system Python at /usr/bin/python3.
Optional extras, used when present:
  - ffplay (brew install ffmpeg): ElevenLabs audio plays while it streams in,
    so a long passage starts in ~1s instead of after the whole file renders.
  - voice_menu (built by install.sh with swiftc): the voice picker becomes a
    native pop-up menu at the pointer with hover submenus. Without it, a plain
    list dialog is used.

Text input priority:
  1. command-line argument(s)
  2. --clipboard               (read the current clipboard; best for terminals)
  3. stdin                     (e.g. from the right-click Quick Action)
  4. auto-capture the current selection via Cmd+C -> pbpaste

Usage:
    python3 speak_selection.py "some text"      # speak given text
    python3 speak_selection.py --clipboard      # speak the clipboard
    echo "text" | python3 speak_selection.py    # speak piped text
    python3 speak_selection.py                  # speak the current selection
    python3 speak_selection.py --stop           # stop playback
    python3 speak_selection.py --provider minimax "hi"   # force a provider
    python3 speak_selection.py --pick           # choose a voice from the menu
    python3 speak_selection.py --voice zara "hi"         # pick a voice by key
    python3 speak_selection.py --list-voices    # show the voice keys

Voices and the picker menu live in voices.json (edit it to make your own menu).
A pick is remembered and becomes the voice for the plain hotkeys.

Configuration lives in a `.env` file next to this script (see .env.example).
A provider key that returns 401 is remembered so it is skipped until the key changes.
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
CACHE_DIR = Path(os.path.expanduser("~/Library/Caches/speak_selection"))
AUDIO_CACHE = CACHE_DIR / "audio"
PIDFILE = CACHE_DIR / "afplay.pid"   # holds the process-GROUP id of the player
LAST_VOICE = CACHE_DIR / "last_voice"
EL_FAILED_MARKER = CACHE_DIR / "elevenlabs_failed_keyhash"

HERE = Path(__file__).resolve().parent
VOICES_FILE = HERE / "voices.json"
VOICE_MENU_BIN = HERE / "voice_menu"

EL_ENDPOINT = ("https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
               "?output_format=mp3_44100_128")
EL_MODEL = os.environ.get("SPEAK_EL_MODEL", "eleven_v4")   # most expressive; multilingual
FFPLAY = shutil.which("ffplay") or (
    "/opt/homebrew/bin/ffplay" if Path("/opt/homebrew/bin/ffplay").exists() else None)

MM_ENDPOINT = "https://api.minimax.io/v1/t2a_v2"
MM_MODEL = os.environ.get("SPEAK_MM_MODEL", "speech-2.8-hd")
# English: a pleasant timber blend. Chinese/Cantonese: a proven Yue-capable combo.
MM_EN_TIMBER = [
    {"voice_id": "Lively_Girl", "weight": 70},
    {"voice_id": "English_Graceful_Lady", "weight": 30},
]
MM_CJK_VOICE = "Chinese (Mandarin)_Warm_Bestie"

MAX_CHARS = 9500  # MiniMax hard cap is 10k; leave headroom.


def load_voices():
    """voices.json -> (VOICES {key: (voice_id, label)}, MENU, default key).
    MENU entries are a key (top-level item) or (group label, [keys]) (hover submenu).
    SPEAK_EL_VOICE_ID still works: it adds a "custom" voice and makes it the default."""
    voices, menu, default = {}, [], "custom"
    if VOICES_FILE.exists():
        doc = json.loads(VOICES_FILE.read_text())
        default = doc.get("default", default)
        for entry in doc.get("menu", []):
            if "group" in entry:
                keys = []
                for v in entry.get("items", []):
                    voices[v["key"]] = (v["id"], v["label"])
                    keys.append(v["key"])
                menu.append((entry["group"], keys))
            else:
                voices[entry["key"]] = (entry["id"], entry["label"])
                menu.append(entry["key"])
    custom = os.environ.get("SPEAK_EL_VOICE_ID", "").strip()
    if custom or not voices:
        voices["custom"] = (custom or "21m00Tcm4TlvDq8ikWAM", "Custom voice (SPEAK_EL_VOICE_ID)")
        menu.insert(0, "custom")
        default = "custom"
    if default not in voices:
        default = next(iter(voices))
    return voices, menu, default


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_dotenv():
    """Load KEY=VALUE pairs from a .env next to this script (and the cwd)."""
    here = Path(__file__).resolve()
    for p in [here.parent / ".env", Path.cwd() / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def notify(msg, title="Speak Selection"):
    """Best-effort desktop notice; never fatal."""
    try:
        subprocess.Popen(
            ["osascript", "-e",
             f"display notification {json.dumps(msg)} with title {json.dumps(title)}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    print(f"{title}: {msg}", file=sys.stderr)


def is_cjk(text):
    for ch in text:
        o = ord(ch)
        if (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or
                0xF900 <= o <= 0xFAFF or 0x3000 <= o <= 0x303F):
            return True
    return False


def _http_post(url, headers, body_bytes):
    """POST and return (status_code, body_bytes, error_str)."""
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read(), None
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None
    except urllib.error.URLError as e:
        return None, b"", str(e.reason)
    except Exception as e:  # pragma: no cover - defensive
        return None, b"", str(e)


# --------------------------------------------------------------------------- #
# Text capture
# --------------------------------------------------------------------------- #
def get_selection(delay=0.2):
    """Capture the current selection by copying it, then restore the clipboard.

    Empties the clipboard first so we can tell 'nothing was selected' apart
    from 'the selection happens to equal the old clipboard'. If the synthetic
    Cmd+C is blocked (no Accessibility permission for the triggering app, e.g.
    a terminal), say so and suggest the clipboard path instead.
    """
    old = _run(["pbpaste"]).stdout
    # Wait FIRST, so the hotkey's own modifiers (e.g. the Option of Option+S) are
    # released before we synthesize Cmd+C — otherwise macOS sees Cmd+Option+C and
    # copies nothing. Defer clearing the clipboard to just before the copy so the
    # brief "empty" window (which a near-simultaneous Speak Clipboard could read) is
    # as short as possible.
    subprocess.run(["osascript", "-e", f"delay {delay}"])
    subprocess.run(["pbcopy"], input="", text=True)
    res = _run(
        ["osascript",
         "-e", 'tell application "System Events" to keystroke "c" using command down'])
    subprocess.run(["osascript", "-e", "delay 0.15"])
    captured = _run(["pbpaste"]).stdout
    subprocess.run(["pbcopy"], input=old, text=True)

    blocked = ("not allowed", "assistive", "accessibility", "-1719", "-25211")
    if res.returncode != 0 and any(t in res.stderr.lower() for t in blocked):
        notify("Can't read the selection — the triggering app needs Accessibility "
               "permission (System Settings > Privacy & Security > Accessibility). "
               "Or copy the text (Cmd+C) and use Speak Clipboard.")
        return ""
    return captured


def read_input(args):
    if args.text:
        return " ".join(args.text).strip()
    if args.clipboard:
        return _run(["pbpaste"]).stdout.strip()
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped
    return get_selection(delay=args.capture_delay).strip()


# --------------------------------------------------------------------------- #
# Playback control
# --------------------------------------------------------------------------- #
def stop_playback():
    if PIDFILE.exists():
        try:
            pgid = int(PIDFILE.read_text().strip())
            if pgid != os.getpgrp():
                os.killpg(pgid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        PIDFILE.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Voice choice
# --------------------------------------------------------------------------- #
def resolve_voice(choice, voices, default):
    """--voice value -> (key, voice_id). A pick is remembered as the new default,
    so the plain hotkeys and the right-click action use the last voice chosen."""
    if choice:
        key = choice.strip().lower()
        if key not in voices:
            notify(f"Unknown voice {choice!r} - using {default}.")
            key = default
        LAST_VOICE.write_text(key)
    else:
        key = LAST_VOICE.read_text().strip() if LAST_VOICE.exists() else default
        if key not in voices:
            key = default
    return key, voices[key][0]


def pick_voice_popup(voices, menu, default):
    """Pop up the voice menu at the mouse pointer (hover submenus, last pick ticked).
    Return the chosen key, or None if cancelled. Runs AFTER the selection is
    captured, so stealing focus here can't break the Cmd+C. Falls back to a flat
    list dialog if the native menu helper isn't built."""
    last = LAST_VOICE.read_text().strip() if LAST_VOICE.exists() else default
    if VOICE_MENU_BIN.exists():
        def leaf(k):
            return {"title": voices[k][1], "key": k, "checked": k == last}
        tree = [{"title": "Read it in which voice?"}]
        for entry in menu:
            if isinstance(entry, str):
                tree.append(leaf(entry))
            else:
                group, keys = entry
                tree.append({"title": group, "children": [leaf(k) for k in keys],
                             "checked": last in keys})
        res = subprocess.run([str(VOICE_MENU_BIN)], input=json.dumps(tree),
                             capture_output=True, text=True)
        if res.returncode == 0:
            chosen = res.stdout.strip()
            return chosen if chosen in voices else None
    labels = [label for _, label in voices.values()]
    preset = voices.get(last, voices[default])[1]
    items = ", ".join(json.dumps(l) for l in labels)
    script = (
        'tell application "System Events"\n'
        '  activate\n'
        f'  set r to choose from list {{{items}}} with title "Speak Selection" '
        f'with prompt "Read it in which voice?" default items {{{json.dumps(preset)}}} '
        'OK button name "Speak" cancel button name "Cancel"\n'
        'end tell\n'
        'if r is false then return ""\n'
        'return item 1 of r')
    chosen = _run(["osascript", "-e", script]).stdout.strip()
    for k, (_, label) in voices.items():
        if label == chosen:
            return k
    return None


# --------------------------------------------------------------------------- #
# TTS providers
# --------------------------------------------------------------------------- #
def _keyhash(key):
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def elevenlabs_disabled(key):
    return EL_FAILED_MARKER.exists() and EL_FAILED_MARKER.read_text().strip() == _keyhash(key)


def disable_elevenlabs(key):
    EL_FAILED_MARKER.write_text(_keyhash(key))


def tts_elevenlabs(text, out_path, speed, voice_id, player=None):
    """Stream ElevenLabs audio into out_path; if `player` (ffplay reading stdin) is
    given, feed it chunk by chunk so playback starts in ~1s."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return False, "no ELEVENLABS_API_KEY"
    if elevenlabs_disabled(key):
        return False, "key previously rejected (cached)"
    body = json.dumps({
        "text": text, "model_id": EL_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
    }).encode()
    req = urllib.request.Request(
        EL_ENDPOINT.format(voice=voice_id), data=body, method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    part = out_path.with_suffix(".part")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, part.open("wb") as fh:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                fh.write(chunk)
                if player is not None:
                    try:
                        player.stdin.write(chunk)
                        player.stdin.flush()
                    except (BrokenPipeError, OSError):
                        player = None   # playback stopped; keep caching
    except urllib.error.HTTPError as e:
        part.unlink(missing_ok=True)
        if e.code == 401:
            disable_elevenlabs(key)
            return False, "401 invalid key (now cached as bad)"
        return False, f"HTTP {e.code}: {e.read()[:160].decode('utf-8', 'replace')}"
    except (urllib.error.URLError, OSError) as e:
        part.unlink(missing_ok=True)
        return False, f"network error: {getattr(e, 'reason', e)}"
    if part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        return False, "empty audio"
    part.rename(out_path)
    return True, "elevenlabs"


def tts_minimax(text, out_path, speed):
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        return False, "no MINIMAX_API_KEY"
    voice_setting = {"speed": speed, "vol": 1.0, "pitch": 0, "emotion": "calm"}
    body = {"model": MM_MODEL, "text": text, "stream": False,
            "voice_setting": voice_setting,
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000,
                              "format": "mp3", "channel": 1}}
    if is_cjk(text):
        voice_setting["voice_id"] = MM_CJK_VOICE
        body["language_boost"] = "Chinese,Yue"   # MUST be top-level
    else:
        voice_setting["voice_id"] = ""
        body["timber_weights"] = MM_EN_TIMBER
    _, raw, err = _http_post(
        MM_ENDPOINT,
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json.dumps(body).encode())
    if err:
        return False, f"network error: {err}"
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return False, f"bad response: {raw[:160]!r}"
    if data.get("base_resp", {}).get("status_code", -1) != 0:
        return False, data.get("base_resp", {}).get("status_msg", "unknown error")
    audio = data.get("data", {}).get("audio")
    if not audio:
        return False, "no audio in response"
    out_path.write_bytes(bytes.fromhex(audio))
    return True, "minimax"


def start_stream_player():
    """ffplay reading MP3 from stdin, in this (detached) process group."""
    return subprocess.Popen(
        [FFPLAY, "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "pipe:0"],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def synthesize(text, speed, provider_pref, voice_id, live=False):
    """Return (path, provider_name, played). Tries preferred provider, then the
    other. With live=True and ffplay installed, ElevenLabs audio plays as it streams."""
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    order = ["elevenlabs", "minimax"] if provider_pref == "auto" else [provider_pref]
    notes = []
    for prov in order:
        tag = f"{prov}|{EL_MODEL}|{voice_id}" if prov == "elevenlabs" else prov
        cache_key = hashlib.sha256(f"{tag}|{speed}|{text}".encode()).hexdigest()[:24]
        out_path = AUDIO_CACHE / f"{cache_key}.mp3"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path, prov + " (cached)", False
        played = False
        if prov == "elevenlabs":
            player = start_stream_player() if (live and FFPLAY) else None
            ok, info = tts_elevenlabs(text, out_path, speed, voice_id, player)
            if player is not None:
                try:
                    player.stdin.close()
                except OSError:
                    pass
                if ok:
                    player.wait()
                else:
                    player.kill()
                played = ok
        else:
            ok, info = tts_minimax(text, out_path, speed)
        if ok:
            if prov != order[0]:
                notify(f"ElevenLabs failed ({notes[0]}) - read with {prov} instead.")
            return out_path, info, played
        notes.append(f"{prov}: {info}")
    notify("TTS failed — " + " | ".join(notes))
    sys.exit(1)


def stream_worker(text_file, speed, provider, voice_id):
    """Detached child: owns its process group (PIDFILE) so --stop kills it and the
    player together; synthesizes, plays, exits."""
    PIDFILE.write_text(str(os.getpgrp()))
    text = Path(text_file).read_text()
    Path(text_file).unlink(missing_ok=True)
    path, _, played = synthesize(text, speed, provider, voice_id, live=True)
    if not played:
        subprocess.run(["afplay", str(path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if PIDFILE.exists() and PIDFILE.read_text().strip() == str(os.getpgrp()):
        PIDFILE.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Speak the selected/copied text aloud")
    ap.add_argument("text", nargs="*", help="text to speak (optional)")
    ap.add_argument("--stop", action="store_true", help="stop current playback")
    ap.add_argument("--clipboard", action="store_true",
                    help="read the current clipboard instead of auto-capturing "
                         "the selection (reliable in terminals; needs no permission)")
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "elevenlabs", "minimax"])
    ap.add_argument("--speed", type=float, default=float(os.environ.get("SPEAK_SPEED", 1.0)))
    ap.add_argument("--capture-delay", type=float,
                    default=float(os.environ.get("SPEAK_CAPTURE_DELAY", 0.6)),
                    help="pause before Cmd+C when auto-capturing the selection "
                         "(must outlast the hotkey's own modifier release, e.g. the "
                         "Option key of Option+S, or the copy becomes Cmd+Option+C)")
    ap.add_argument("--voice", default="",
                    help="voice key from voices.json (remembered as the default)")
    ap.add_argument("--pick", action="store_true",
                    help="show the voice menu after capturing the text")
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--no-play", action="store_true", help="synthesize only")
    ap.add_argument("--worker", default="", help=argparse.SUPPRESS)
    args = ap.parse_args()

    voices, menu, default = load_voices()
    if args.list_voices:
        for k, (vid, label) in voices.items():
            print(f"{k:10} {vid}  {label}")
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if args.stop:
        stop_playback()
        return

    voice_key, voice_id = resolve_voice(args.voice, voices, default)
    if args.worker:
        stream_worker(args.worker, args.speed, args.provider, voice_id)
        return

    text = read_input(args)
    if not text:
        notify("Nothing to read. Select text then trigger, or copy it (Cmd+C) "
               "and use Speak Clipboard / --clipboard.")
        return
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        notify(f"Selection trimmed to {MAX_CHARS} characters.")

    if args.pick:
        picked = pick_voice_popup(voices, menu, default)
        if not picked:
            return
        voice_key, voice_id = resolve_voice(picked, voices, default)

    if args.no_play:
        path, prov, _ = synthesize(text, args.speed, args.provider, voice_id)
        print(f"[{prov}] voice={voice_key} {len(text)} chars -> {path}")
        return

    # Hand off to a detached worker so the trigger (Raycast / Quick Action)
    # returns at once while audio streams and plays.
    stop_playback()   # interrupt any current readout
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    for stale in AUDIO_CACHE.glob("*.part"):   # left by a stream cut off by --stop
        stale.unlink(missing_ok=True)
    text_file = CACHE_DIR / f"pending-{os.getpid()}.txt"
    text_file.write_text(text)
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(text_file),
         "--voice", voice_key, "--speed", str(args.speed), "--provider", args.provider],
        start_new_session=True, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"voice={voice_key} model={EL_MODEL} {len(text)} chars -> playing")


if __name__ == "__main__":
    main()
