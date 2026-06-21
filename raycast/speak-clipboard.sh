#!/bin/bash
# Read the current clipboard aloud. Reliable everywhere (incl. terminals) — copy
# the text yourself (Cmd+C) first, then run this. Needs no Accessibility permission.
#
# Raycast Script Command metadata
# @raycast.schemaVersion 1
# @raycast.title Speak Clipboard
# @raycast.mode silent
# @raycast.packageName Text to Speech
# @raycast.icon 📋
# @raycast.description Reads whatever you last copied aloud (ElevenLabs/MiniMax).

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/speak_selection.py" --clipboard
