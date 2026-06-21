#!/bin/bash
# Stop any in-progress read-aloud.
#
# Raycast Script Command metadata
# @raycast.schemaVersion 1
# @raycast.title Stop Speaking
# @raycast.mode silent
# @raycast.packageName Text to Speech
# @raycast.icon 🔇
# @raycast.description Stops the current read-aloud playback.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/speak_selection.py" --stop
