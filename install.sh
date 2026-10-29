#!/bin/bash
# One-shot installer for Speak Selection.
#  - makes the Raycast scripts executable
#  - creates your .env from the example (if missing)
#  - installs the right-click "Speak Selection" Quick Action with the correct path
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

echo "Repo: $DIR"

# 1. Raycast scripts executable
chmod +x "$DIR"/raycast/*.sh
echo "✓ Raycast scripts are executable"

# 1b. Native voice menu (hover submenus). Needs swiftc (Xcode Command Line Tools);
#     without it the picker falls back to a plain list dialog.
if command -v swiftc >/dev/null 2>&1; then
  swiftc -O "$DIR/voice_menu.swift" -o "$DIR/voice_menu" && echo "✓ Built the voice menu"
else
  echo "• swiftc not found — voice picker will use a plain list (xcode-select --install to upgrade)"
fi
if ! command -v ffplay >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/ffplay ]; then
  echo "• Optional: brew install ffmpeg — long passages then start playing in ~1s (streaming)"
fi

# 2. .env
if [ ! -f "$DIR/.env" ]; then
  cp "$DIR/.env.example" "$DIR/.env"
  echo "✓ Created .env — open it and add at least one API key:"
  echo "    $DIR/.env"
else
  echo "✓ .env already exists (left untouched)"
fi

# 3. Right-click Quick Action
SVC="$HOME/Library/Services/SpeakSelection.workflow"
rm -rf "$SVC"
cp -R "$DIR/workflow/SpeakSelection.workflow" "$SVC"
# bake the real repo path into the action's shell command
/usr/bin/sed -i '' "s|__REPO__|$DIR|g" "$SVC/Contents/document.wflow"
/System/Library/CoreServices/pbs -update 2>/dev/null || true
echo "✓ Installed right-click Quick Action -> ~/Library/Services/"

cat <<EOF

Next steps:
  1. Add your API key(s) to:  $DIR/.env
  2. (Optional) Raycast hotkeys:
       Raycast -> Settings -> Extensions -> Script Commands -> Add Script Directory
       Choose:  $DIR/raycast
       Then assign hotkeys to "Speak Selection", "Speak Clipboard", "Stop Speaking",
       and "Speak Selection (Pick Voice)" (e.g. ⌘⌥C) for the voice menu.
  3. Try it now:
       echo "Hello from Speak Selection" | /usr/bin/python3 "$DIR/speak_selection.py"

Done.
EOF
