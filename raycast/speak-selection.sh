#!/bin/bash
# Read the currently highlighted text aloud (ElevenLabs primary, MiniMax fallback).
#
# Raycast Script Command metadata
# @raycast.schemaVersion 1
# @raycast.title Speak Selection
# @raycast.mode silent
# @raycast.packageName Text to Speech
# @raycast.icon 🔊
# @raycast.description Reads your highlighted text aloud via ElevenLabs/MiniMax.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/speak_selection.py"
