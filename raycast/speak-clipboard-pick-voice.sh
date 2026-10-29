#!/bin/bash
# Read the clipboard aloud, choosing the voice from the menu first.
#
# Raycast Script Command metadata
# @raycast.schemaVersion 1
# @raycast.title Speak Clipboard (Pick Voice)
# @raycast.mode silent
# @raycast.packageName Text to Speech
# @raycast.icon 🔊
# @raycast.description Pops up the voice menu, then reads your clipboard aloud.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/speak_selection.py" --clipboard --pick
