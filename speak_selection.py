#!/usr/bin/env python3
"""Speak the highlighted / selected (or copied) text aloud on macOS.

Pipeline:  get text -> TTS (ElevenLabs primary, MiniMax fallback) -> play.

Zero dependencies: uses only the Python standard library + macOS built-ins
(afplay, pbpaste, osascript). Works on the system Python at /usr/bin/python3.

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

Configuration lives in a `.env` file next to this script (see .env.example).
A provider key that returns 401 is remembered so it is skipped until the key changes.
"""
import argparse
import hashlib
import json
import os
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
PIDFILE = CACHE_DIR / "afplay.pid"
EL_FAILED_MARKER = CACHE_DIR / "elevenlabs_failed_keyhash"

EL_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
EL_VOICE_ID = os.environ.get("SPEAK_EL_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")   # Rachel
EL_MODEL = os.environ.get("SPEAK_EL_MODEL", "eleven_flash_v2_5")            # low latency

MM_ENDPOINT = "https://api.minimax.io/v1/t2a_v2"
MM_MODEL = os.environ.get("SPEAK_MM_MODEL", "speech-2.8-hd")
# English: a pleasant timber blend. Chinese/Cantonese: a proven Yue-capable combo.
MM_EN_TIMBER = [
    {"voice_id": "Lively_Girl", "weight": 70},
    {"voice_id": "English_Graceful_Lady", "weight": 30},
]
MM_CJK_VOICE = "Chinese (Mandarin)_Warm_Bestie"

MAX_CHARS = 9500  # MiniMax hard cap is 10k; leave headroom.


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
    subprocess.run(["pbcopy"], input="", text=True)
    res = _run(
        ["osascript",
         "-e", f"delay {delay}",
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
            pid = int(PIDFILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        PIDFILE.unlink(missing_ok=True)


def play(path):
    stop_playback()  # interrupt any current readout
    proc = subprocess.Popen(["afplay", str(path)], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PIDFILE.write_text(str(proc.pid))


# --------------------------------------------------------------------------- #
# TTS providers
# --------------------------------------------------------------------------- #
def _keyhash(key):
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def elevenlabs_disabled(key):
    return EL_FAILED_MARKER.exists() and EL_FAILED_MARKER.read_text().strip() == _keyhash(key)


def disable_elevenlabs(key):
    EL_FAILED_MARKER.write_text(_keyhash(key))


def tts_elevenlabs(text, out_path, speed):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return False, "no ELEVENLABS_API_KEY"
    if elevenlabs_disabled(key):
        return False, "key previously rejected (cached)"
    body = json.dumps({
        "text": text, "model_id": EL_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
    }).encode()
    status, data, err = _http_post(
        EL_ENDPOINT.format(voice=EL_VOICE_ID),
        {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        body)
    if err:
        return False, f"network error: {err}"
    if status == 401:
        disable_elevenlabs(key)
        return False, "401 invalid key (now cached as bad)"
    if status != 200 or not data:
        return False, f"HTTP {status}: {data[:160].decode('utf-8', 'replace')}"
    out_path.write_bytes(data)
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


def synthesize(text, speed, provider_pref):
    """Return (path, provider_name). Tries preferred provider, then the other."""
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    order = ["elevenlabs", "minimax"] if provider_pref == "auto" else [provider_pref]
    notes = []
    for prov in order:
        cache_key = hashlib.sha256(f"{prov}|{speed}|{text}".encode()).hexdigest()[:24]
        out_path = AUDIO_CACHE / f"{cache_key}.mp3"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path, prov + " (cached)"
        fn = tts_elevenlabs if prov == "elevenlabs" else tts_minimax
        ok, info = fn(text, out_path, speed)
        if ok:
            return out_path, info
        notes.append(f"{prov}: {info}")
    notify("TTS failed — " + " | ".join(notes))
    sys.exit(1)


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
                    default=float(os.environ.get("SPEAK_CAPTURE_DELAY", 0.2)),
                    help="pause before Cmd+C when auto-capturing the selection")
    ap.add_argument("--no-play", action="store_true", help="synthesize only")
    args = ap.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if args.stop:
        stop_playback()
        return

    text = read_input(args)
    if not text:
        notify("Nothing to read. Select text then trigger, or copy it (Cmd+C) "
               "and use Speak Clipboard / --clipboard.")
        return
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        notify(f"Selection trimmed to {MAX_CHARS} characters.")

    path, prov = synthesize(text, args.speed, args.provider)
    print(f"[{prov}] {len(text)} chars -> {path}")
    if not args.no_play:
        play(path)


if __name__ == "__main__":
    main()
